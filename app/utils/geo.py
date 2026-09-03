"""Geo helpers used for live journey tracking and route-deviation detection.

Deviation logic ported from the original client-side algorithm:
- Once the traveler has moved ~30m from the journey's starting point, the
  direction of that initial movement is "locked" as the route axis.
- Every subsequent GPS fix is projected onto that axis; the perpendicular
  (cross-track) distance from the axis is the "off-route distance".
- If off-route distance exceeds 350m for 2 consecutive readings in a row,
  the journey is flagged as deviated.
"""
from math import radians, degrees, sin, cos, sqrt, atan2

EARTH_RADIUS_M = 6371000
AXIS_LOCK_DISTANCE_M = 30
DEVIATION_THRESHOLD_M = 350
DEVIATION_STREAK_REQUIRED = 2


def haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    dlat, dlng = radians(lat2 - lat1), radians(lng2 - lng1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlng / 2) ** 2
    return 2 * EARTH_RADIUS_M * atan2(sqrt(a), sqrt(1 - a))


def bearing_deg(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    dlng = radians(lng2 - lng1)
    y = sin(dlng) * cos(radians(lat2))
    x = cos(radians(lat1)) * sin(radians(lat2)) - sin(radians(lat1)) * cos(radians(lat2)) * cos(dlng)
    return (degrees(atan2(y, x)) + 360) % 360


def cross_track_distance_m(origin_lat, origin_lng, axis_bearing_deg, point_lat, point_lng) -> float:
    """Perpendicular distance of `point` from the great-circle ray starting at
    `origin` heading in direction `axis_bearing_deg`."""
    d13 = haversine_m(origin_lat, origin_lng, point_lat, point_lng) / EARTH_RADIUS_M
    brng13 = radians(bearing_deg(origin_lat, origin_lng, point_lat, point_lng))
    brng12 = radians(axis_bearing_deg)
    cross = atan2(sin(d13) * sin(brng13 - brng12), cos(d13))
    return abs(cross * EARTH_RADIUS_M)


def update_journey_tracking(journey, lat: float, lng: float) -> None:
    """Mutates `journey` in place given a new GPS fix. Call before commit()."""
    journey.current_lat, journey.current_lng = lat, lng

    if journey.baseline_lat is None:
        journey.baseline_lat, journey.baseline_lng = lat, lng
        journey.off_route_distance_m = 0.0
        return

    moved = haversine_m(journey.baseline_lat, journey.baseline_lng, lat, lng)

    if not journey.axis_locked:
        if moved >= AXIS_LOCK_DISTANCE_M:
            journey.axis_bearing = bearing_deg(journey.baseline_lat, journey.baseline_lng, lat, lng)
            journey.axis_locked = True
        journey.off_route_distance_m = 0.0
        return

    off = cross_track_distance_m(journey.baseline_lat, journey.baseline_lng, journey.axis_bearing, lat, lng)
    journey.off_route_distance_m = off

    if off > DEVIATION_THRESHOLD_M:
        journey.deviation_streak += 1
    else:
        journey.deviation_streak = 0

    if journey.deviation_streak >= DEVIATION_STREAK_REQUIRED:
        journey.status = "deviated"
        journey.route_safety_percent = max(10, 100 - int(off / 10))
    else:
        journey.route_safety_percent = max(40, 100 - int(off / 20))

    if journey.to_lat is not None and journey.to_lng is not None:
        remaining_km = haversine_m(lat, lng, journey.to_lat, journey.to_lng) / 1000
        journey.eta_minutes = max(1, round(remaining_km / 4 * 60))  # ~4 km/h walking estimate
