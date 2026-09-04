from datetime import datetime
from pydantic import BaseModel


class EmergencyCreate(BaseModel):
    type: str = "sos"
    latitude: float | None = None
    longitude: float | None = None
    location_label: str | None = None
    battery_level: int | None = None


class EmergencyLocationUpdate(BaseModel):
    latitude: float
    longitude: float
    battery_level: int | None = None


class EmergencyStatusUpdate(BaseModel):
    status: str  # resolved | cancelled | false_alarm


class EmergencyOut(BaseModel):
    id: str
    owner_id: str
    type: str
    status: str
    location_label: str | None
    latitude: float | None
    longitude: float | None
    location_history: list
    battery_level: int | None
    started_at: datetime
    resolved_at: datetime | None
    contacts_notified: int
    evidence_recording: bool
    evidence_upload_progress: int
    evidence_photos: list
    evidence_videos: list
    evidence_clips: list
    drive_folder_link: str | None
    drive_link_sent: bool

    class Config:
        from_attributes = True
