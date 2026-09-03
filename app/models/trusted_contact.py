import uuid
from datetime import datetime, timezone
import enum

from sqlalchemy import String, Boolean, DateTime, ForeignKey, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ContactStatus(str, enum.Enum):
    pending = "pending"
    verified = "verified"
    active = "active"


class TrustedContact(Base):
    __tablename__ = "trusted_contacts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    owner_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True)

    name: Mapped[str] = mapped_column(String(120))
    relationship: Mapped[str] = mapped_column(String(64), default="")
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    avatar_color: Mapped[str] = mapped_column(String(16), default="#9B8AFB")

    status: Mapped[ContactStatus] = mapped_column(SAEnum(ContactStatus), default=ContactStatus.pending)
    online: Mapped[bool] = mapped_column(Boolean, default=False)
    location_sharing: Mapped[bool] = mapped_column(Boolean, default=False)
    is_emergency_contact: Mapped[bool] = mapped_column(Boolean, default=True)

    # set once the invited email matches a registered SafeHer user
    linked_user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
