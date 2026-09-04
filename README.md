# SafeHer AI — Backend (FastAPI)

Python backend for the SafeHer AI personal-safety platform.

**Live URL:** `https://safehar-ai-f2eddne4c6gtd4ga.southindia-01.azurewebsites.net`
**Interactive docs (Swagger):** add `/docs` to the URL above — every route below is also
browsable/testable there.

## Stack
- FastAPI + Uvicorn/Gunicorn
- SQLAlchemy 2.0 ORM (SQLite by default)
- JWT auth (access + refresh tokens)
- WebSocket broadcast for the live Monitor dashboard
- Evidence files uploaded as real binary via `multipart/form-data` — no Base64
- Google Drive integration for SOS evidence folders
- OpenStreetMap Overpass proxy for nearby police/fire/hospital lookup
- Community-reported incidents + heuristic area-safety scoring for the Maps feature

## Auth — how every other request authenticates
Every route below marked **Auth: Bearer** requires this header on the request:
```
Authorization: Bearer <access_token>
```
Get `access_token` from `POST /api/auth/register` or `POST /api/auth/login` (see table below).
Access tokens expire in 60 minutes — call `POST /api/auth/refresh` with the `refresh_token`
to get a new pair without asking the user to log in again.

---

## API Reference

### Auth (`/api/auth`)

| Method | Full Path | Auth | Body / Query Params | Returns |
|---|---|---|---|---|
| POST | `/api/auth/register` | none | `full_name` (str), `email` (str), `password` (str, min 8 chars), `phone` (str, optional) | `access_token`, `refresh_token`, `token_type` |
| POST | `/api/auth/login` | none | `email` (str), `password` (str) | `access_token`, `refresh_token`, `token_type` |
| POST | `/api/auth/refresh` | none | `refresh_token` (str) | new `access_token`, `refresh_token`, `token_type` |
| GET | `/api/auth/me` | Bearer | — | current user object (see `UserOut` below) |
| POST | `/api/auth/otp/request` | none | `email` (str), `purpose` (str: `"verify_email"` or `"reset_password"`, default `"verify_email"`) | `{"message": "..."}` — emails a 6-digit code |
| POST | `/api/auth/otp/verify` | none | `email` (str), `code` (str), `purpose` (str, default `"verify_email"`) | `{"message": "..."}` |
| POST | `/api/auth/forgot-password` | none | `email` (str) | `{"message": "..."}` — always generic, doesn't reveal if the email exists |
| POST | `/api/auth/reset-password` | none | `email` (str), `code` (str), `new_password` (str, min 8 chars) | `{"message": "..."}` |

**`UserOut` object shape** (returned by `/me` and embedded elsewhere):
`id, full_name, email, phone, role ("user"|"admin"), avatar_color, is_verified, onboarding_complete, created_at`

---

### Users (`/api/users`)

| Method | Full Path | Auth | Body / Query Params | Returns |
|---|---|---|---|---|
| GET | `/api/users/me` | Bearer | — | `UserOut` (same as `/api/auth/me`) |
| PUT | `/api/users/me` | Bearer | Any subset of: `full_name`, `phone`, `avatar_color`, `onboarding_complete` (bool) | updated `UserOut` |

---

### Trusted Contacts (`/api/contacts`)

| Method | Full Path | Auth | Body / Query Params | Returns |
|---|---|---|---|---|
| GET | `/api/contacts` | Bearer | — | list of `ContactOut` |
| POST | `/api/contacts` | Bearer | `name` (str), `relationship` (str, default `""`), `phone` (str, optional), `email` (str, optional), `is_emergency_contact` (bool, default `true`), `avatar_color` (str, default `"#9B8AFB"`) | `ContactOut` |
| PUT | `/api/contacts/{contact_id}` | Bearer | Any subset of: `name`, `relationship`, `phone`, `email`, `is_emergency_contact`, `location_sharing` | `ContactOut` |
| DELETE | `/api/contacts/{contact_id}` | Bearer | — | `204 No Content` |
| POST | `/api/contacts/{contact_id}/invite` | Bearer | — | `{"message": "..."}` — emails the contact an invite |

**`ContactOut` object shape:**
`id, name, relationship, phone, email, avatar_color, status ("pending"|"verified"|"active"), online, location_sharing, is_emergency_contact, created_at`

`is_emergency_contact = true` means this person gets notified on **every SOS**, regardless of
any specific journey's contact selection (see Emergency Location Override below).

---

### Journeys — destination live-location sharing (`/api/journeys`)

| Method | Full Path | Auth | Body / Query Params | Returns |
|---|---|---|---|---|
| GET | `/api/journeys` | Bearer | — | list of `JourneyOut`, newest first |
| POST | `/api/journeys` | Bearer | `from_label` (str), `to_label` (str), `from_lat`/`from_lng`/`to_lat`/`to_lng` (float, optional), `expected_arrival` (ISO datetime, optional), `trusted_contact_ids` (list of contact id strings — **can be more than one**), `notify_on_deviation` (bool, default `true`) | `JourneyOut` |
| POST | `/api/journeys/{journey_id}/start` | Bearer | — | `JourneyOut` — emails every selected contact a "journey started" + live-tracking link |
| POST | `/api/journeys/{journey_id}/location` | Bearer | `latitude` (float), `longitude` (float) | `JourneyOut` — call this every ~10s while the journey is active |
| POST | `/api/journeys/{journey_id}/end` | Bearer | — | `JourneyOut` — emails "arrived safely" to selected contacts |

**`JourneyOut` object shape:**
`id, from_label, to_label, from_lat, from_lng, to_lat, to_lng, status ("planned"|"active"|"completed"|"deviated"), expected_arrival, trusted_contact_ids (list), trusted_contact_names (list), notify_on_deviation, current_lat, current_lng, route_safety_percent (0-100), eta_minutes, off_route_distance_m, started_at, ended_at, created_at`

Route-deviation is computed server-side on every `/location` call — if the user strays
>350m off the initial path for 2 consecutive updates, `status` flips to `"deviated"` and the
selected contacts get an automatic email.

---

### Emergencies — SOS (`/api/emergencies`)

| Method | Full Path | Auth | Body / Query Params | Returns |
|---|---|---|---|---|
| GET | `/api/emergencies` | Bearer | — | list of `EmergencyOut` (own events only, unless `role="admin"` → sees everyone's) |
| GET | `/api/emergencies/{emergency_id}` | Bearer | — | `EmergencyOut` |
| POST | `/api/emergencies/activate` | Bearer | `type` (str, default `"sos"`; also accepts `fall_detected`, `voice_distress`, `manual`, `route_deviation`), `latitude`/`longitude` (float, optional), `location_label` (str, optional), `battery_level` (int, optional) | `EmergencyOut` — creates the Drive evidence folder immediately and emails **all** `is_emergency_contact` contacts the live-tracking link |
| POST | `/api/emergencies/{emergency_id}/location` | Bearer | `latitude` (float), `longitude` (float), `battery_level` (int, optional) | `EmergencyOut` — call every ~12s while active |
| POST | `/api/emergencies/{emergency_id}/evidence/{kind}` | Bearer | **multipart/form-data**, field name `file` (the raw photo/video/audio file). `{kind}` in the URL is `photo`, `video`, or `audio` | `EmergencyOut` — file is saved locally AND pushed to the Drive folder; sends the one-time Drive-link email to contacts after the first successful Drive upload |
| POST | `/api/emergencies/{emergency_id}/status` | Bearer | `status` (str: `"resolved"`, `"cancelled"`, or `"false_alarm"`) | `EmergencyOut` — this is what "I Am Safe" calls |
| GET | `/api/emergencies/{emergency_id}/report` | Bearer | — | a PDF file (binary) — full incident report with photos, location history, evidence links |

**`EmergencyOut` object shape:**
`id, owner_id, type, status ("active"|"resolved"|"cancelled"|"false_alarm"), location_label, latitude, longitude, location_history (list of {latitude, longitude, timestamp}), battery_level, started_at, resolved_at, contacts_notified (int), evidence_recording (bool), evidence_upload_progress (0-100), evidence_photos (list of URLs), evidence_videos (list of URLs), evidence_clips (list of URLs), drive_folder_link (str or null), drive_link_sent (bool)`

---

### Nearby Emergency Services (`/api/services`)

| Method | Full Path | Auth | Body / Query Params | Returns |
|---|---|---|---|---|
| GET | `/api/services/nearby` | Bearer | `lat` (float), `lng` (float), `radius_m` (int, 500–20000, default 5000) | `{"source": "overpass"\|"national_fallback", "services": [...]}` — each service: `{name, type, latitude, longitude, distance_m, direction, phone}` |

---

### Incidents & Area Safety Intelligence (`/api/incidents`)

| Method | Full Path | Auth | Body / Query Params | Returns |
|---|---|---|---|---|
| POST | `/api/incidents` | Bearer | `latitude` (float), `longitude` (float), `type` (str, default `"other"`; suggested values: `theft`, `harassment`, `assault`, `poor_lighting`, `other`), `severity` (str: `"low"`\|`"medium"`\|`"high"`, default `"medium"`), `description` (str, optional) | `IncidentOut` |
| GET | `/api/incidents/nearby` | Bearer | `lat` (float), `lng` (float), `radius_m` (int, 100–10000, default 1500) | list of `IncidentOut` |
| GET | `/api/incidents/safety-status` | Bearer | `lat` (float), `lng` (float) | `SafetyStatusOut`: `{status: "safe"|"caution"|"high_risk", score (0-100), reason (str), incident_count (int), incidents: [IncidentOut]}` |

**Note:** there's no external crime-data API wired in (that needs a paid/regional data
source, out of scope) — scoring is based on incidents reported through this app plus a
small time-of-day factor. See `app/services/safety_intelligence.py`.

---

### AI Safety Assistant (`/api/assistant`)

| Method | Full Path | Auth | Body / Query Params | Returns |
|---|---|---|---|---|
| POST | `/api/assistant/chat` | Bearer | `message` (str), `history` (list of `{role: "user"|"assistant", content: str}`, optional — pass prior turns for context) | `{"reply": "..."}` |

---

### Public Live Tracking (no login — for trusted contacts clicking an email link)

| Method | Full Path | Auth | Body / Query Params | Returns |
|---|---|---|---|---|
| GET | `/api/public/track/{kind}/{item_id}` | **none** | `{kind}` = `"journey"` or `"emergency"`; `{item_id}` = the journey/emergency id from the email link | JSON: `{label, status, latitude, longitude, ...}` — polled every 6s by the tracking page |
| GET | `/track/{kind}/{item_id}` | **none** | same as above | a full HTML page with a live-updating map (this is the actual link sent by email) |

The `{item_id}` (a UUID) is the access token — it's never exposed via any listing endpoint
to other users, so only someone with the emailed link can view it.

---

### Realtime Monitor Feed (WebSocket)

| Protocol | Full Path | Auth | Notes |
|---|---|---|---|
| WebSocket | `wss://<host>/ws/monitor` | Bearer not required on the socket itself (the Monitor dashboard UI is where access should be gated) | Pushes a JSON message `{"kind": "created"|"updated", "emergency": EmergencyOut}` every time any `EmergencyEvent` changes. Requires **"Web sockets" = On** in Azure App Service → Configuration → General settings. |

---

## Setup
```bash
python -m venv venv
venv\Scripts\activate           # Windows PowerShell: venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env          # fill in real values for production
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Environment variables (set as Azure "Application settings" in production)
| Variable | Purpose |
|---|---|
| `SECRET_KEY` | JWT signing key — must be a long random string in production |
| `DATABASE_URL` | defaults to local SQLite; point at Postgres/MySQL for a real deployment |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM` | email notifications (contact invites, OTP codes, journey/emergency alerts). Left blank → emails are logged instead of sent. |
| `GOOGLE_DRIVE_CLIENT_JSON`, `GOOGLE_DRIVE_TOKEN_JSON` | Google Drive evidence upload — see `scripts/gdrive_auth.py` for one-time setup |
| `ANTHROPIC_API_KEY` | optional — enables full AI responses from the Assistant; without it, the assistant gives a canned safety-guidance reply |
| `PUBLIC_BASE_URL` | must be your real deployed URL (e.g. `https://safehar-ai-....azurewebsites.net`) — used to build the `/track/...` links sent by email |

## Notes
- Uploaded evidence files are written to `app/media/{photos,audio,videos}` and served at
  `/media/...`, in addition to being pushed to Google Drive when configured.
- On Azure App Service (Linux), the deployment folder (`/home/site/wwwroot`) is on
  persistent storage, so the default SQLite file and local media survive restarts —
  but not reliably across multiple scaled-out instances. Move to Postgres before scaling
  beyond a single instance.
