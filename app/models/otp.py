import uuid
from datetime import datetime, timezone

from beanie import Document
from pydantic import Field
from pymongo import IndexModel


def _uuid() -> str:
    return str(uuid.uuid4())


class OTPCode(Document):
    """Short-lived codes used for email verification and password reset."""

    id: str = Field(default_factory=_uuid)

    email: str
    code: str
    purpose: str  # "verify_email" | "reset_password"
    used: bool = False
    expires_at: datetime
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Settings:
        name = "otp_codes"
        indexes = [
            IndexModel("email"),
        ]
