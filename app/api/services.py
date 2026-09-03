from fastapi import APIRouter, Depends, Query

from app.models.user import User
from app.api.deps import get_current_user
from app.services.overpass_service import get_nearby_emergency_services

router = APIRouter(prefix="/api/services", tags=["services"])

NATIONAL_FALLBACK = [
    {"name": "Police", "phone": "15", "type": "police"},
    {"name": "Rescue", "phone": "1122", "type": "rescue"},
    {"name": "Edhi Ambulance", "phone": "115", "type": "ambulance"},
    {"name": "Fire Brigade", "phone": "16", "type": "fire"},
    {"name": "Women Helpline", "phone": "104", "type": "helpline"},
    {"name": "Motorway Police", "phone": "130", "type": "police"},
]


@router.get("/nearby")
async def nearby_services(
    lat: float = Query(...), lng: float = Query(...), radius_m: int = Query(5000, ge=500, le=20000),
    current_user: User = Depends(get_current_user),
):
    results = await get_nearby_emergency_services(lat, lng, radius_m)
    if not results:
        return {"source": "national_fallback", "services": NATIONAL_FALLBACK}
    return {"source": "overpass", "services": results}
