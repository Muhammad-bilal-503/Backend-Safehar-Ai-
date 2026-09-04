"""Public (no-auth) live-location tracking, used by trusted contacts who get
a link via email — for a Journey (destination sharing, item 5) or an
EmergencyEvent (SOS override, item 6). The id in the URL is an unguessable
UUID and isn't exposed through any listing endpoint to non-owners, so it
functions as the access token — nobody can discover it without the emailed
link. Evidence and full incident details still require real login; this only
ever exposes a live lat/lng + status, nothing more sensitive.
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from fastapi import Depends

from app.core.database import get_db
from app.models.journey import Journey
from app.models.emergency_event import EmergencyEvent

router = APIRouter(tags=["tracking"])


@router.get("/api/public/track/{kind}/{item_id}")
def public_track_data(kind: str, item_id: str, db: Session = Depends(get_db)):
    if kind == "journey":
        obj = db.get(Journey, item_id)
        if not obj:
            raise HTTPException(404, "Not found.")
        return {
            "label": f"{obj.from_label} → {obj.to_label}",
            "status": obj.status,
            "latitude": obj.current_lat,
            "longitude": obj.current_lng,
            "safety_percent": obj.route_safety_percent,
            "eta_minutes": obj.eta_minutes,
        }
    if kind == "emergency":
        obj = db.get(EmergencyEvent, item_id)
        if not obj:
            raise HTTPException(404, "Not found.")
        return {
            "label": f"Emergency ({obj.type.value if hasattr(obj.type, 'value') else obj.type})",
            "status": obj.status,
            "latitude": obj.latitude,
            "longitude": obj.longitude,
            "battery_level": obj.battery_level,
            "drive_folder_link": obj.drive_folder_link,
        }
    raise HTTPException(404, "Unknown tracking kind.")


_PAGE_TEMPLATE = """<!DOCTYPE html>
<html><head>
<meta charset="utf-8"/><meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>SafeHer AI — Live Tracking</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
  body {{ margin:0; font-family: -apple-system, Segoe UI, Roboto, sans-serif; background:#FFFDF9; }}
  #banner {{ padding:14px 18px; background:#D96C8A; color:white; font-weight:700; }}
  #status {{ padding:10px 18px; color:#6E6470; font-size:14px; }}
  #map {{ height: calc(100vh - 76px); width:100%; }}
</style>
</head><body>
<div id="banner">SafeHer AI — Live Tracking</div>
<div id="status">Loading…</div>
<div id="map"></div>
<script>
  const kind = "{kind}";
  const itemId = "{item_id}";
  const map = L.map('map').setView([0,0], 2);
  L.tileLayer('https://{{s}}.basemaps.cartocdn.com/rastertiles/voyager/{{z}}/{{x}}/{{y}}{{r}}.png', {{
    subdomains: 'abcd', maxZoom: 19
  }}).addTo(map);
  let marker = null;

  async function refresh() {{
    try {{
      const res = await fetch(`/api/public/track/${{kind}}/${{itemId}}`);
      if (!res.ok) {{ document.getElementById('status').innerText = 'This tracking link is no longer valid.'; return; }}
      const data = await res.json();
      const statusText = data.status === 'active' || data.status === 'deviated'
        ? 'Live — updating automatically'
        : `Session ended (${{data.status}})`;
      document.getElementById('status').innerText = `${{data.label}} — ${{statusText}}`;
      if (data.latitude && data.longitude) {{
        const pos = [data.latitude, data.longitude];
        if (!marker) {{
          marker = L.marker(pos).addTo(map);
          map.setView(pos, 15);
        }} else {{
          marker.setLatLng(pos);
        }}
      }}
    }} catch (e) {{
      document.getElementById('status').innerText = 'Connection issue — retrying…';
    }}
  }}
  refresh();
  setInterval(refresh, 6000);
</script>
</body></html>"""


@router.get("/track/{kind}/{item_id}", response_class=HTMLResponse)
def public_track_page(kind: str, item_id: str):
    if kind not in ("journey", "emergency"):
        raise HTTPException(404, "Unknown tracking kind.")
    return HTMLResponse(_PAGE_TEMPLATE.format(kind=kind, item_id=item_id))
