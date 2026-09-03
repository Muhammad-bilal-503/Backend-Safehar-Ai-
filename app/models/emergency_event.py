import uuid
from datetime import datetime, timezone
import enum

from sqlalchemy import String, Float, Integer, Boolean, DateTime, ForeignKey, JSON, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


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


class EmergencyEvent(Base):
    __tablename__ = "emergency_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    owner_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True)

    type: Mapped[EmergencyType] = mapped_column(SAEnum(EmergencyType), default=EmergencyType.sos)
    status: Mapped[EmergencyStatus] = mapped_column(SAEnum(EmergencyStatus), default=EmergencyStatus.active)

    location_label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)

    # list[{latitude, longitude, timestamp}]
    location_history: Mapped[list] = mapped_column(JSON, default=list)

    battery_level: Mapped[int | None] = mapped_column(Integer, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    contacts_notified: Mapped[int] = mapped_column(Integer, default=0)
    evidence_recording: Mapped[bool] = mapped_column(Boolean, default=True)
    evidence_upload_progress: Mapped[int] = mapped_column(Integer, default=0)

    # stored as relative file paths under MEDIA_ROOT, e.g. "photos/<id>/front_....jpg"
    evidence_photos: Mapped[list] = mapped_column(JSON, default=list)
    evidence_videos: Mapped[list] = mapped_column(JSON, default=list)
    evidence_clips: Mapped[list] = mapped_column(JSON, default=list)  # audio
