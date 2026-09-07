import uuid
from datetime import datetime, timezone
import enum

from beanie import Document
from pydantic import Field
from pymongo import IndexModel


def _uuid() -> str:
    return str(uuid.uuid4())


class UserRole(str, enum.Enum):
    admin = "admin"
    user = "user"


class User(Document):
    # Overriding `id` with a plain str (instead of Beanie's default
    # PydanticObjectId) keeps the same UUID-based ids the SQLite version
    # used, so every router that does `user.id` keeps working unchanged.
    id: str = Field(default_factory=_uuid)

    full_name: str
    email: str
    hashed_password: str
    phone: str | None = None
    role: UserRole = UserRole.user
    avatar_color: str = "#D96C8A"

    is_verified: bool = False
    is_active: bool = True
    onboarding_complete: bool = False

    # google oauth
    google_sub: str | None = None

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Settings:
        name = "users"
        indexes = [
            IndexModel("email", unique=True),
        ]
