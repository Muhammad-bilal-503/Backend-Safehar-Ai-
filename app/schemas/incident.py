from datetime import datetime
from pydantic import BaseModel


class IncidentCreate(BaseModel):
    latitude: float
    longitude: float
    type: str = "other"
    severity: str = "medium"
    description: str | None = None


class IncidentOut(BaseModel):
    id: str
    latitude: float
    longitude: float
    type: str
    severity: str
    description: str | None
    reported_at: datetime

    class Config:
        from_attributes = True


class SafetyStatusOut(BaseModel):
    status: str  # safe | caution | high_risk
    score: int
    reason: str
    incident_count: int
    incidents: list[IncidentOut]
