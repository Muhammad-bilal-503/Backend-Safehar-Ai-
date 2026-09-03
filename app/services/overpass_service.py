"""Nearby police/fire/hospital lookup via OpenStreetMap Overpass API, with mirror failover."""
import httpx

MIRRORS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.openstreetmap.ru/api/interpreter",
]

AMENITY_QUERY = {
    "police": 'node["amenity"="police"]',
    "hospital": 'node["amenity"="hospital"]',
    "fire": 'node["amenity"="fire_station"]',
}


def _build_query(lat: float, lng: float, radius_m: int) -> str:
    parts = "\n".join(f'{q}(around:{radius_m},{lat},{lng});' for q in AMENITY_QUERY.values())
    return f"[out:json][timeout:8];(\n{parts}\n);out center;"


async def get_nearby_emergency_services(lat: float, lng: float, radius_m: int = 5000) -> list[dict]:
    query = _build_query(lat, lng, radius_m)
    last_error = None
    for mirror in MIRRORS:
        try:
            async with httpx.AsyncClient(timeout=9.0) as client:
                resp = await client.post(mirror, data={"data": query})
                resp.raise_for_status()
                data = resp.json()
                return _normalize(data, lat, lng)
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            continue
    # All mirrors failed — return empty; caller falls back to national short-codes.
    return []


def _haversine_m(lat1, lng1, lat2, lng2) -> float:
    from math import radians, sin, cos, sqrt, atan2

    r = 6371000
    dlat, dlng = radians(lat2 - lat1), radians(lng2 - lng1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlng / 2) ** 2
    return 2 * r * atan2(sqrt(a), sqrt(1 - a))


def _bearing(lat1, lng1, lat2, lng2) -> str:
    from math import radians, degrees, sin, cos, atan2

    dlng = radians(lng2 - lng1)
    y = sin(dlng) * cos(radians(lat2))
    x = cos(radians(lat1)) * sin(radians(lat2)) - sin(radians(lat1)) * cos(radians(lat2)) * cos(dlng)
    deg = (degrees(atan2(y, x)) + 360) % 360
    dirs = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
    return dirs[round(deg / 45) % 8]


def _normalize(data: dict, lat: float, lng: float) -> list[dict]:
    out = []
    for el in data.get("elements", []):
        tags = el.get("tags", {})
        amenity = tags.get("amenity")
        if amenity not in ("police", "hospital", "fire_station"):
            continue
        elat, elng = el.get("lat"), el.get("lon")
        if elat is None or elng is None:
            continue
        dist = _haversine_m(lat, lng, elat, elng)
        out.append({
            "name": tags.get("name", amenity.replace("_", " ").title()),
            "type": "fire" if amenity == "fire_station" else amenity,
            "latitude": elat,
            "longitude": elng,
            "distance_m": round(dist),
            "direction": _bearing(lat, lng, elat, elng),
            "phone": tags.get("phone") or tags.get("contact:phone"),
        })
    out.sort(key=lambda x: x["distance_m"])
    return out[:20]
