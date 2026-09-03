from datetime import datetime
from pydantic import BaseModel


class JourneyCreate(BaseModel):
    from_label: str
    to_label: str
    from_lat: float | None = None
    from_lng: float | None = None
    to_lat: float | None = None
    to_lng: float | None = None
    expected_arrival: datetime | None = None
    trusted_contact_id: str | None = None
    notify_on_deviation: bool = True


class JourneyLocationUpdate(BaseModel):
    latitude: float
    longitude: float


class JourneyOut(BaseModel):
    id: str
    from_label: str
    to_label: str
    from_lat: float | None
    from_lng: float | None
    to_lat: float | None
    to_lng: float | None
    status: str
    expected_arrival: datetime | None
    trusted_contact_id: str | None
    trusted_contact_name: str | None
    notify_on_deviation: bool
    current_lat: float | None
    current_lng: float | None
    route_safety_percent: int
    eta_minutes: int | None
    off_route_distance_m: float
    started_at: datetime | None
    ended_at: datetime | None
    created_at: datetime

    class Config:
        from_attributes = True
