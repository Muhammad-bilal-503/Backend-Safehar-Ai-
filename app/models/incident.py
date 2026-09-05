import uuid
from datetime import datetime, timezone
import enum

from beanie import Document
from pydantic import Field


def _uuid() -> str:
    return str(uuid.uuid4())


class IncidentSeverity(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"


class Incident(Document):
    """A community-reported safety incident used to score an area's safety
    status on the map. There's no external crime-data feed wired in here —
    that would need a paid/regional data provider, which is out of scope —
    so this is fed by in-app user reports."""

    id: str = Field(default_factory=_uuid)
    reporter_id: str | None = None

    latitude: float
    longitude: float
    type: str = "other"  # theft | harassment | assault | poor_lighting | other
    severity: IncidentSeverity = IncidentSeverity.medium
    description: str | None = None

    reported_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Settings:
        name = "incidents"
