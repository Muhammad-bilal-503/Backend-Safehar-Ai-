import uuid
from datetime import datetime, timezone
import enum

from beanie import Document
from pydantic import Field
from pymongo import IndexModel


def _uuid() -> str:
    return str(uuid.uuid4())


class EmergencyType(str, enum.Enum):
    sos = "sos"
    fall_detected = "fall_detected"
    voice_distress = "voice_distress"
    manual = "manual"
    route_deviation = "route_deviation"


class EmergencyStatus(str, enum.Enum):
    active = "active"
    resolved = "resolved"
    cancelled = "cancelled"
    false_alarm = "false_alarm"


class EmergencyEvent(Document):
    id: str = Field(default_factory=_uuid)
    owner_id: str

    type: EmergencyType = EmergencyType.sos
    status: EmergencyStatus = EmergencyStatus.active

    location_label: str | None = None
    latitude: float | None = None
    longitude: float | None = None

    # list[{latitude, longitude, timestamp}]
    location_history: list = Field(default_factory=list)

    battery_level: int | None = None
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    resolved_at: datetime | None = None

    contacts_notified: int = 0
    evidence_recording: bool = True
    evidence_upload_progress: int = 0

    # Google Drive evidence folder — created immediately on SOS activation.
    # drive_link_sent tracks whether trusted contacts have already received
    # the folder link (it must only be sent once, per the spec).
    drive_folder_id: str | None = None
    drive_folder_link: str | None = None
    drive_link_sent: bool = False

    # stored as relative file paths under MEDIA_ROOT, e.g. "photos/<id>/front_....jpg"
    evidence_photos: list = Field(default_factory=list)
    evidence_videos: list = Field(default_factory=list)
    evidence_clips: list = Field(default_factory=list)  # audio

    class Settings:
        name = "emergency_events"
        indexes = [
            IndexModel("owner_id"),
        ]
