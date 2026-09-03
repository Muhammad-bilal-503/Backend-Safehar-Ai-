from datetime import datetime
from pydantic import BaseModel, EmailStr


class ContactCreate(BaseModel):
    name: str
    relationship: str = ""
    phone: str | None = None
    email: EmailStr | None = None
    is_emergency_contact: bool = True
    avatar_color: str = "#9B8AFB"


class ContactUpdate(BaseModel):
    name: str | None = None
    relationship: str | None = None
    phone: str | None = None
    email: EmailStr | None = None
    is_emergency_contact: bool | None = None
    location_sharing: bool | None = None


class ContactOut(BaseModel):
    id: str
    name: str
    relationship: str
    phone: str | None
    email: str | None
    avatar_color: str
    status: str
    online: bool
    location_sharing: bool
    is_emergency_contact: bool
    created_at: datetime

    class Config:
        from_attributes = True
