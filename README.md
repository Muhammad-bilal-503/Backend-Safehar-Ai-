# SafeHer AI — Backend (FastAPI)

Python backend for the SafeHer AI personal-safety platform. Replaces the original
base44 managed backend with a self-hosted FastAPI service.

## Stack
- FastAPI + Uvicorn
- SQLAlchemy 2.0 ORM (SQLite by default, swap `DATABASE_URL` for Postgres/MySQL in prod)
- JWT auth (access + refresh tokens), OTP email verification, forgot/reset password
- WebSocket broadcast for the live Monitor dashboard
- Evidence (photos/audio/video) is uploaded as real binary files via `multipart/form-data`
  and served as static files — **no Base64 encoding/decoding anywhere in this codebase.**
- Server-side PDF incident reports (ReportLab) — no client-side jsPDF/Base64 embedding.
- OpenStreetMap Overpass proxy for nearby police/fire/hospital lookup.

## Setup
```bash
python -m venv venv
source venv/bin/activate         # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env             # fill in SMTP creds etc.
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Interactive API docs: http://localhost:8000/docs

## Notes
- On first run, tables are auto-created from the SQLAlchemy models (see `app/core/database.py`).
  For production, generate an Alembic migration instead of relying on `create_all`.
- Uploaded evidence files are written to `app/media/{photos,audio,videos}` and served at
  `/media/...`. Point `MEDIA_ROOT`/`PUBLIC_BASE_URL` at S3/Cloud Storage + a CDN for production.
- Email sending uses SMTP (`aiosmtplib`). If SMTP env vars are left blank, the service logs
  the email instead of sending it, so the rest of the app still works in local dev.
