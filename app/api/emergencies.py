from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.user import User
from app.models.emergency_event import EmergencyEvent, EmergencyStatus, EmergencyType
from app.models.trusted_contact import TrustedContact
from app.schemas.emergency import EmergencyCreate, EmergencyLocationUpdate, EmergencyStatusUpdate, EmergencyOut
from app.api.deps import get_current_user
from app.services.email_service import notify_emergency_location, notify_drive_evidence_link
from app.services.storage import save_evidence_file, public_url
from app.services.ws_manager import manager
from app.services import drive_service

router = APIRouter(prefix="/api/emergencies", tags=["emergencies"])

_MIME = {"photo": "image/jpeg", "video": "video/mp4", "audio": "audio/mp4"}


async def _broadcast(event: EmergencyEvent, kind: str) -> None:
    await manager.broadcast({
        "kind": kind,
        "emergency": EmergencyOut.model_validate(event).model_dump(mode="json"),
    })


def _emergency_contacts(db: Session, owner_id: str) -> list[TrustedContact]:
    return (
        db.query(TrustedContact)
        .filter(TrustedContact.owner_id == owner_id, TrustedContact.is_emergency_contact == True)  # noqa: E712
        .all()
    )


@router.get("", response_model=list[EmergencyOut])
def list_emergencies(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Guardians/response teams see all events; regular users see only their own."""
    q = db.query(EmergencyEvent)
    if current_user.role != "admin":
        q = q.filter(EmergencyEvent.owner_id == current_user.id)
    return q.order_by(EmergencyEvent.started_at.desc()).all()


@router.get("/{emergency_id}", response_model=EmergencyOut)
def get_emergency(emergency_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    event = db.get(EmergencyEvent, emergency_id)
    if not event or (current_user.role != "admin" and event.owner_id != current_user.id):
        raise HTTPException(404, "Emergency not found.")
    return event


@router.post("/activate", response_model=EmergencyOut, status_code=201)
async def activate_emergency(payload: EmergencyCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    event = EmergencyEvent(
        owner_id=current_user.id,
        type=EmergencyType(payload.type),
        status=EmergencyStatus.active,
        latitude=payload.latitude,
        longitude=payload.longitude,
        location_label=payload.location_label,
        battery_level=payload.battery_level,
    )
    if payload.latitude is not None and payload.longitude is not None:
        event.location_history = [{
            "latitude": payload.latitude, "longitude": payload.longitude,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }]
    db.add(event)
    db.commit()
    db.refresh(event)

    # Create the SOS evidence folder immediately, as required — before any
    # evidence has even been captured yet. Failures here are non-fatal; the
    # evidence endpoint will retry creating it lazily if this didn't work.
    folder = drive_service.create_incident_folder(event.id, current_user.full_name)
    if folder:
        event.drive_folder_id, event.drive_folder_link = folder
        db.commit()
        db.refresh(event)

    # Emergency override: ALWAYS notify every emergency contact, regardless
    # of any destination-sharing selection on an active journey.
    contacts = _emergency_contacts(db, current_user.id)
    if payload.latitude is not None and payload.longitude is not None:
        result = await notify_emergency_location(current_user.full_name, contacts, payload.latitude, payload.longitude, event.id)
        event.contacts_notified = result["delivered"]
        db.commit()
        db.refresh(event)

    await _broadcast(event, "created")
    return event


@router.post("/{emergency_id}/location", response_model=EmergencyOut)
async def update_emergency_location(emergency_id: str, payload: EmergencyLocationUpdate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    event = _get_owned(db, emergency_id, current_user.id)
    if event.status != EmergencyStatus.active:
        raise HTTPException(400, "Emergency is not active.")
    event.latitude, event.longitude = payload.latitude, payload.longitude
    if payload.battery_level is not None:
        event.battery_level = payload.battery_level
    history = list(event.location_history or [])
    history.append({
        "latitude": payload.latitude, "longitude": payload.longitude,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    event.location_history = history
    db.commit()
    db.refresh(event)
    await _broadcast(event, "updated")
    return event


@router.post("/{emergency_id}/evidence/{kind}", response_model=EmergencyOut)
async def upload_evidence(emergency_id: str, kind: str, file: UploadFile = File(...), current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """kind: photo | video | audio. Streams the raw upload straight to disk —
    no Base64 — then forwards it into the incident's Drive folder. The Flutter
    app batches these calls into a once-a-minute cycle (see EvidenceCaptureService)."""
    if kind not in ("photo", "video", "audio"):
        raise HTTPException(400, "kind must be photo, video, or audio.")
    event = _get_owned(db, emergency_id, current_user.id)

    relative_path = await save_evidence_file(kind, event.id, file)
    url = public_url(relative_path)

    if kind == "photo":
        event.evidence_photos = [*event.evidence_photos, url]
    elif kind == "video":
        event.evidence_videos = [*event.evidence_videos, url]
    else:
        event.evidence_clips = [*event.evidence_clips, url]

    total = len(event.evidence_photos) + len(event.evidence_videos) + len(event.evidence_clips)
    event.evidence_upload_progress = min(100, total * 10)

    # Lazily create the Drive folder if activation-time creation failed earlier.
    if not event.drive_folder_id:
        folder = drive_service.create_incident_folder(event.id, current_user.full_name)
        if folder:
            event.drive_folder_id, event.drive_folder_link = folder

    import os
    from app.core.config import settings
    local_path = os.path.join(settings.MEDIA_ROOT, relative_path)
    drive_uploaded = False
    if event.drive_folder_id:
        drive_link = drive_service.upload_file_to_folder(
            event.drive_folder_id, local_path, os.path.basename(relative_path), _MIME.get(kind, "application/octet-stream")
        )
        drive_uploaded = drive_link is not None

    db.commit()
    db.refresh(event)

    # First successful Drive upload -> notify trusted contacts with the
    # folder link, exactly once for this incident.
    if drive_uploaded and not event.drive_link_sent and event.drive_folder_link:
        contacts = _emergency_contacts(db, current_user.id)
        any_sent = False
        for contact in contacts:
            if contact.email and contact.status != "pending":
                drive_service.share_folder_with_email(event.drive_folder_id, contact.email)
                sent = await notify_drive_evidence_link(contact, current_user.full_name, event.drive_folder_link)
                any_sent = any_sent or sent
        if any_sent:
            event.drive_link_sent = True
            db.commit()
            db.refresh(event)

    await _broadcast(event, "updated")
    return event


@router.post("/{emergency_id}/status", response_model=EmergencyOut)
async def set_status(emergency_id: str, payload: EmergencyStatusUpdate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    event = db.get(EmergencyEvent, emergency_id)
    if not event or (current_user.role != "admin" and event.owner_id != current_user.id):
        raise HTTPException(404, "Emergency not found.")
    try:
        event.status = EmergencyStatus(payload.status)
    except ValueError:
        raise HTTPException(400, "Invalid status.")
    if event.status != EmergencyStatus.active:
        event.resolved_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(event)
    await _broadcast(event, "updated")
    return event


def _get_owned(db: Session, emergency_id: str, owner_id: str) -> EmergencyEvent:
    event = db.get(EmergencyEvent, emergency_id)
    if not event or event.owner_id != owner_id:
        raise HTTPException(404, "Emergency not found.")
    return event
