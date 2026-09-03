from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.user import User
from app.models.emergency_event import EmergencyEvent, EmergencyStatus, EmergencyType
from app.models.trusted_contact import TrustedContact
from app.schemas.emergency import EmergencyCreate, EmergencyLocationUpdate, EmergencyStatusUpdate, EmergencyOut
from app.api.deps import get_current_user
from app.services.email_service import notify_emergency_location
from app.services.storage import save_evidence_file, public_url
from app.services.ws_manager import manager

router = APIRouter(prefix="/api/emergencies", tags=["emergencies"])


async def _broadcast(event: EmergencyEvent, kind: str) -> None:
    await manager.broadcast({
        "kind": kind,
        "emergency": EmergencyOut.model_validate(event).model_dump(mode="json"),
    })


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

    contacts = (
        db.query(TrustedContact)
        .filter(TrustedContact.owner_id == current_user.id, TrustedContact.is_emergency_contact == True)  # noqa: E712
        .all()
    )
    if payload.latitude is not None and payload.longitude is not None:
        result = await notify_emergency_location(current_user.full_name, contacts, payload.latitude, payload.longitude)
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
    """kind: photo | video | audio. Streams the raw upload straight to disk — no Base64."""
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
