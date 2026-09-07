import uuid
from datetime import datetime, timezone
import enum

from beanie import Document
from pydantic import Field
from pymongo import IndexModel


def _uuid() -> str:
    return str(uuid.uuid4())


class JourneyStatus(str, enum.Enum):
    planned = "planned"
    active = "active"
    completed = "completed"
    deviated = "deviated"


class Journey(Document):
    id: str = Field(default_factory=_uuid)
    owner_id: str

    from_label: str
    to_label: str
    from_lat: float | None = None
    from_lng: float | None = None
    to_lat: float | None = None
    to_lng: float | None = None

    status: JourneyStatus = JourneyStatus.planned
    expected_arrival: datetime | None = None

    # Destination live-location sharing: the user can pick one or more trusted
    # contacts to share this journey with (see requirement "Destination Live
    # Location Sharing" — only these contacts receive updates for this journey,
    # separate from the emergency override which always notifies everyone).
    trusted_contact_ids: list[str] = Field(default_factory=list)
    trusted_contact_names: list[str] = Field(default_factory=list)
    notify_on_deviation: bool = True

    current_lat: float | None = None
    current_lng: float | None = None
    route_safety_percent: int = 100
    eta_minutes: int | None = None
    off_route_distance_m: float = 0.0

    # route-deviation detection state (see app/utils/geo.py)
    baseline_lat: float | None = None
    baseline_lng: float | None = None
    axis_bearing: float | None = None
    axis_locked: bool = False
    deviation_streak: int = 0

    started_at: datetime | None = None
    ended_at: datetime | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Settings:
        name = "journeys"
        indexes = [
            IndexModel("owner_id"),
        ]
