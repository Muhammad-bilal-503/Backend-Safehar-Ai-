import uuid
from datetime import datetime, timezone
import enum

from sqlalchemy import String, Float, Integer, Boolean, DateTime, ForeignKey, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class JourneyStatus(str, enum.Enum):
    planned = "planned"
    active = "active"
    completed = "completed"
    deviated = "deviated"


class Journey(Base):
    __tablename__ = "journeys"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    owner_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True)

    from_label: Mapped[str] = mapped_column(String(255))
    to_label: Mapped[str] = mapped_column(String(255))
    from_lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    from_lng: Mapped[float | None] = mapped_column(Float, nullable=True)
    to_lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    to_lng: Mapped[float | None] = mapped_column(Float, nullable=True)

    status: Mapped[JourneyStatus] = mapped_column(SAEnum(JourneyStatus), default=JourneyStatus.planned)
    expected_arrival: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    trusted_contact_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("trusted_contacts.id"), nullable=True)
    trusted_contact_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    notify_on_deviation: Mapped[bool] = mapped_column(Boolean, default=True)

    current_lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    current_lng: Mapped[float | None] = mapped_column(Float, nullable=True)
    route_safety_percent: Mapped[int] = mapped_column(Integer, default=100)
    eta_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    off_route_distance_m: Mapped[float] = mapped_column(Float, default=0.0)

    # route-deviation detection state (see app/services/geo.py)
    baseline_lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    baseline_lng: Mapped[float | None] = mapped_column(Float, nullable=True)
    axis_bearing: Mapped[float | None] = mapped_column(Float, nullable=True)
    axis_locked: Mapped[bool] = mapped_column(Boolean, default=False)
    deviation_streak: Mapped[int] = mapped_column(Integer, default=0)

    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
