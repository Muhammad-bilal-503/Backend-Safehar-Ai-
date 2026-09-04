"""Area safety scoring for the Maps feature. Combines nearby community-reported
incidents (recency- and severity-weighted) with a simple time-of-day factor
into a Safe / Caution / High Risk verdict with a human-readable reason.

There's no external crime-data API wired in — a real one (e.g. a regional
police open-data feed) would need a paid/regional integration that's out of
scope here — so this scores whatever incidents users report in-app via
POST /api/incidents. It degrades gracefully to a neutral "not enough data"
verdict when an area has no reports.
"""
from datetime import datetime, timezone

from app.models.incident import Incident
from app.utils.geo import haversine_m

RADIUS_M = 800
RECENT_DAYS_FULL_WEIGHT = 30
SEVERITY_WEIGHT = {"low": 8, "medium": 16, "high": 28}


def _recency_factor(reported_at: datetime) -> float:
    age_days = (datetime.now(timezone.utc) - reported_at.replace(tzinfo=timezone.utc)).days
    if age_days <= RECENT_DAYS_FULL_WEIGHT:
        return 1.0
    if age_days <= 180:
        return 0.5
    return 0.2


def nearby_incidents(incidents: list[Incident], lat: float, lng: float, radius_m: int = RADIUS_M) -> list[Incident]:
    return [i for i in incidents if haversine_m(lat, lng, i.latitude, i.longitude) <= radius_m]


def score_location(incidents: list[Incident], lat: float, lng: float) -> dict:
    nearby = nearby_incidents(incidents, lat, lng)

    score = 100.0
    for incident in nearby:
        weight = SEVERITY_WEIGHT.get(
            incident.severity.value if hasattr(incident.severity, "value") else incident.severity, 12
        )
        score -= weight * _recency_factor(incident.reported_at)

    hour = datetime.now().hour
    is_night = hour >= 22 or hour <= 5
    if is_night:
        score -= 8

    score = max(0, min(100, round(score)))

    if score >= 75:
        status = "safe"
    elif score >= 45:
        status = "caution"
    else:
        status = "high_risk"

    high_count = sum(1 for i in nearby if (i.severity.value if hasattr(i.severity, "value") else i.severity) == "high")

    if not nearby:
        reason = (
            "No incidents reported near this location in SafeHer AI."
            + (" It's currently night-time, so stay extra aware of your surroundings." if is_night else "")
        )
    elif status == "safe":
        reason = f"{len(nearby)} minor report(s) nearby, none recent or severe enough to raise concern."
    elif status == "caution":
        reason = f"{len(nearby)} incident(s) reported nearby in the last few months — stay alert, especially after dark." if not high_count else f"{len(nearby)} incident(s) nearby including {high_count} high-severity report(s)."
    else:
        reason = f"{len(nearby)} incident(s) reported nearby, including {high_count} high-severity report(s). Consider an alternate route or sharing your location."

    return {
        "status": status,
        "score": score,
        "reason": reason,
        "incident_count": len(nearby),
        "incidents": nearby,
    }
