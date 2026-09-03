from datetime import datetime
from pydantic import BaseModel, EmailStr


class UserOut(BaseModel):
    id: str
    full_name: str
    email: EmailStr
    phone: str | None = None
    role: str
    avatar_color: str
    is_verified: bool
    onboarding_complete: bool
    created_at: datetime

    class Config:
        from_attributes = True


class UserUpdate(BaseModel):
    full_name: str | None = None
    phone: str | None = None
    avatar_color: str | None = None
    onboarding_complete: bool | None = None
