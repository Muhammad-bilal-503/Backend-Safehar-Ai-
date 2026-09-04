from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.user import User
from app.models.incident import Incident, IncidentSeverity
from app.schemas.incident import IncidentCreate, IncidentOut, SafetyStatusOut
from app.api.deps import get_current_user
from app.services.safety_intelligence import score_location, nearby_incidents

router = APIRouter(prefix="/api/incidents", tags=["incidents"])


@router.post("", response_model=IncidentOut, status_code=201)
def report_incident(payload: IncidentCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    incident = Incident(
        reporter_id=current_user.id,
        latitude=payload.latitude,
        longitude=payload.longitude,
        type=payload.type,
        severity=IncidentSeverity(payload.severity),
        description=payload.description,
    )
    db.add(incident)
    db.commit()
    db.refresh(incident)
    return incident


@router.get("/nearby", response_model=list[IncidentOut])
def list_nearby(lat: float = Query(...), lng: float = Query(...), radius_m: int = Query(1500, ge=100, le=10000),
                 current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    all_incidents = db.query(Incident).all()
    return nearby_incidents(all_incidents, lat, lng, radius_m)


@router.get("/safety-status", response_model=SafetyStatusOut)
def safety_status(lat: float = Query(...), lng: float = Query(...),
                   current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    all_incidents = db.query(Incident).all()
    return score_location(all_incidents, lat, lng)
