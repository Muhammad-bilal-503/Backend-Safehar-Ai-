import uuid
from datetime import datetime, timezone
import enum

from beanie import Document
from pydantic import Field
from pymongo import IndexModel


def _uuid() -> str:
    return str(uuid.uuid4())


class ContactStatus(str, enum.Enum):
    pending = "pending"
    verified = "verified"
    active = "active"


class TrustedContact(Document):
    id: str = Field(default_factory=_uuid)
    owner_id: str

    name: str
    relationship: str = ""
    phone: str | None = None
    email: str | None = None
    avatar_color: str = "#9B8AFB"

    status: ContactStatus = ContactStatus.pending
    online: bool = False
    location_sharing: bool = False
    is_emergency_contact: bool = True

    # set once the invited email matches a registered SafeHer user
    linked_user_id: str | None = None

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Settings:
        name = "trusted_contacts"
        indexes = [
            IndexModel("owner_id"),
        ]
