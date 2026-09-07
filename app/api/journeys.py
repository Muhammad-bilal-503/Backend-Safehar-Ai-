from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from beanie.operators import In

from app.models.user import User
from app.models.journey import Journey, JourneyStatus
from app.models.trusted_contact import TrustedContact
from app.schemas.journey import JourneyCreate, JourneyLocationUpdate, JourneyOut
from app.api.deps import get_current_user
from app.services.email_service import notify_journey_contact
from app.utils.geo import update_journey_tracking

router = APIRouter(prefix="/api/journeys", tags=["journeys"])


async def _resolve_contacts(owner_id: str, contact_ids: list[str]) -> list[TrustedContact]:
    if not contact_ids:
        return []
    return await TrustedContact.find(
        In(TrustedContact.id, contact_ids), TrustedContact.owner_id == owner_id
    ).to_list()


@router.get("", response_model=list[JourneyOut])
async def list_journeys(current_user: User = Depends(get_current_user)):
    return (
        await Journey.find(Journey.owner_id == current_user.id)
        .sort(-Journey.created_at)
        .to_list()
    )


@router.post("", response_model=JourneyOut, status_code=201)
async def create_journey(payload: JourneyCreate, current_user: User = Depends(get_current_user)):
    contacts = await _resolve_contacts(current_user.id, payload.trusted_contact_ids)
    data = payload.model_dump(exclude={"trusted_contact_ids"})
    journey = Journey(
        owner_id=current_user.id,
        trusted_contact_ids=[c.id for c in contacts],
        trusted_contact_names=[c.name for c in contacts],
        **data,
    )
    await journey.insert()
    return journey


@router.post("/{journey_id}/start", response_model=JourneyOut)
async def start_journey(journey_id: str, current_user: User = Depends(get_current_user)):
    journey = await _get_owned(journey_id, current_user.id)
    journey.status = JourneyStatus.active
    journey.started_at = datetime.now(timezone.utc)
    await journey.save()

    for contact in await _resolve_contacts(current_user.id, journey.trusted_contact_ids):
        await notify_journey_contact(current_user.full_name, contact, "started", journey.from_label, journey.to_label, journey.id)
    return journey


@router.post("/{journey_id}/location", response_model=JourneyOut)
async def update_location(journey_id: str, payload: JourneyLocationUpdate, current_user: User = Depends(get_current_user)):
    journey = await _get_owned(journey_id, current_user.id)
    if journey.status not in (JourneyStatus.active, JourneyStatus.deviated):
        raise HTTPException(400, "Journey is not active.")

    was_deviated = journey.status == JourneyStatus.deviated
    update_journey_tracking(journey, payload.latitude, payload.longitude)
    await journey.save()

    if journey.status == JourneyStatus.deviated and not was_deviated and journey.notify_on_deviation:
        for contact in await _resolve_contacts(current_user.id, journey.trusted_contact_ids):
            await notify_journey_contact(current_user.full_name, contact, "deviated", journey.from_label, journey.to_label, journey.id)
    return journey


@router.post("/{journey_id}/end", response_model=JourneyOut)
async def end_journey(journey_id: str, current_user: User = Depends(get_current_user)):
    journey = await _get_owned(journey_id, current_user.id)
    journey.status = JourneyStatus.completed
    journey.ended_at = datetime.now(timezone.utc)
    await journey.save()

    for contact in await _resolve_contacts(current_user.id, journey.trusted_contact_ids):
        await notify_journey_contact(current_user.full_name, contact, "arrived", journey.from_label, journey.to_label, journey.id)
    return journey


async def _get_owned(journey_id: str, owner_id: str) -> Journey:
    journey = await Journey.get(journey_id)
    if not journey or journey.owner_id != owner_id:
        raise HTTPException(404, "Journey not found.")
    return journey
