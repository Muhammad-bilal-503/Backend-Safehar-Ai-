from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.user import User
from app.models.journey import Journey, JourneyStatus
from app.models.trusted_contact import TrustedContact
from app.schemas.journey import JourneyCreate, JourneyLocationUpdate, JourneyOut
from app.api.deps import get_current_user
from app.services.email_service import notify_journey_contact
from app.utils.geo import update_journey_tracking

router = APIRouter(prefix="/api/journeys", tags=["journeys"])


def _resolve_contacts(db: Session, owner_id: str, contact_ids: list[str]) -> list[TrustedContact]:
    if not contact_ids:
        return []
    contacts = db.query(TrustedContact).filter(TrustedContact.id.in_(contact_ids), TrustedContact.owner_id == owner_id).all()
    return contacts


@router.get("", response_model=list[JourneyOut])
def list_journeys(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return (
        db.query(Journey)
        .filter(Journey.owner_id == current_user.id)
        .order_by(Journey.created_at.desc())
        .all()
    )


@router.post("", response_model=JourneyOut, status_code=201)
def create_journey(payload: JourneyCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    contacts = _resolve_contacts(db, current_user.id, payload.trusted_contact_ids)
    data = payload.model_dump(exclude={"trusted_contact_ids"})
    journey = Journey(
        owner_id=current_user.id,
        trusted_contact_ids=[c.id for c in contacts],
        trusted_contact_names=[c.name for c in contacts],
        **data,
    )
    db.add(journey)
    db.commit()
    db.refresh(journey)
    return journey


@router.post("/{journey_id}/start", response_model=JourneyOut)
async def start_journey(journey_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    journey = _get_owned(db, journey_id, current_user.id)
    journey.status = JourneyStatus.active
    journey.started_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(journey)

    for contact in _resolve_contacts(db, current_user.id, journey.trusted_contact_ids):
        await notify_journey_contact(current_user.full_name, contact, "started", journey.from_label, journey.to_label, journey.id)
    return journey


@router.post("/{journey_id}/location", response_model=JourneyOut)
async def update_location(journey_id: str, payload: JourneyLocationUpdate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    journey = _get_owned(db, journey_id, current_user.id)
    if journey.status not in (JourneyStatus.active, JourneyStatus.deviated):
        raise HTTPException(400, "Journey is not active.")

    was_deviated = journey.status == JourneyStatus.deviated
    update_journey_tracking(journey, payload.latitude, payload.longitude)
    db.commit()
    db.refresh(journey)

    if journey.status == JourneyStatus.deviated and not was_deviated and journey.notify_on_deviation:
        for contact in _resolve_contacts(db, current_user.id, journey.trusted_contact_ids):
            await notify_journey_contact(current_user.full_name, contact, "deviated", journey.from_label, journey.to_label, journey.id)
    return journey


@router.post("/{journey_id}/end", response_model=JourneyOut)
async def end_journey(journey_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    journey = _get_owned(db, journey_id, current_user.id)
    journey.status = JourneyStatus.completed
    journey.ended_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(journey)

    for contact in _resolve_contacts(db, current_user.id, journey.trusted_contact_ids):
        await notify_journey_contact(current_user.full_name, contact, "arrived", journey.from_label, journey.to_label, journey.id)
    return journey


def _get_owned(db: Session, journey_id: str, owner_id: str) -> Journey:
    journey = db.get(Journey, journey_id)
    if not journey or journey.owner_id != owner_id:
        raise HTTPException(404, "Journey not found.")
    return journey
