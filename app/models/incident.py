import uuid
from datetime import datetime, timezone
import enum

from sqlalchemy import String, Float, DateTime, ForeignKey, Enum as SAEnum, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class IncidentSeverity(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"


class Incident(Base):
    """A community-reported safety incident used to score an area's safety
    status on the map. There's no external crime-data feed wired in here —
    that would need a paid/regional data provider, which is out of scope —
    so this is fed by in-app user reports."""

    __tablename__ = "incidents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    reporter_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)

    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    type: Mapped[str] = mapped_column(String(64), default="other")  # theft | harassment | assault | poor_lighting | other
    severity: Mapped[IncidentSeverity] = mapped_column(SAEnum(IncidentSeverity), default=IncidentSeverity.medium)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    reported_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
