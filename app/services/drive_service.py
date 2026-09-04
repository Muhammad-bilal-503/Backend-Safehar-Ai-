"""Google Drive integration for SOS evidence folders.

Setup (one-time, done by the app owner, not per-user):
1. Google Cloud Console -> create a project -> enable the "Google Drive API".
2. Create an OAuth Client ID of type "Desktop app", download the JSON — this
   is the CLIENT config.
3. Run `python scripts/gdrive_auth.py` locally once. It opens a browser
   consent screen (log in with the Google account whose Drive should hold the
   evidence) and writes a token with a refresh_token.
4. Put the CLIENT json content in the `GOOGLE_DRIVE_CLIENT_JSON` env var and
   the token json content in `GOOGLE_DRIVE_TOKEN_JSON` (e.g. as Azure App
   Service "Application settings" — paste the whole JSON as the value).

Why OAuth instead of a plain service account: a bare (non-Workspace) service
account has no real Drive storage of its own and reliably hits "storage quota
exceeded" errors when creating files. Authenticating as a real Google account
via OAuth avoids that entirely and uploads land in that account's own Drive.

If Drive isn't configured, every function here degrades to a no-op / None
return instead of raising — evidence still saves to local/backend storage
either way, so a missing/broken Drive integration never breaks the SOS flow.
"""
import io
import json
import logging

from app.core.config import settings

logger = logging.getLogger("safeher.drive")

_SCOPES = ["https://www.googleapis.com/auth/drive.file"]

_drive_client = None
_drive_unavailable_logged = False


def _get_client():
    """Lazily builds and caches an authorized Drive API client, refreshing
    the token as needed. Returns None if Drive isn't configured or the
    google-api client libraries aren't installed."""
    global _drive_client, _drive_unavailable_logged

    if _drive_client is not None:
        return _drive_client

    if not settings.GOOGLE_DRIVE_TOKEN_JSON or not settings.GOOGLE_DRIVE_CLIENT_JSON:
        if not _drive_unavailable_logged:
            logger.warning("Google Drive not configured (GOOGLE_DRIVE_TOKEN_JSON / GOOGLE_DRIVE_CLIENT_JSON missing) — evidence will only be stored locally.")
            _drive_unavailable_logged = True
        return None

    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build

        token_info = json.loads(settings.GOOGLE_DRIVE_TOKEN_JSON)
        creds = Credentials.from_authorized_user_info(token_info, _SCOPES)
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
        _drive_client = build("drive", "v3", credentials=creds, cache_discovery=False)
        return _drive_client
    except Exception:
        logger.exception("Failed to initialize Google Drive client")
        return None


def create_incident_folder(emergency_id: str, owner_name: str) -> tuple[str, str] | None:
    """Creates a uniquely-named Drive folder for one SOS incident.
    Returns (folder_id, shareable_link) or None if Drive is unavailable."""
    client = _get_client()
    if client is None:
        return None
    try:
        name = f"SafeHer SOS — {owner_name} — {emergency_id[:8]}"
        folder = client.files().create(
            body={"name": name, "mimeType": "application/vnd.google-apps.folder"},
            fields="id, webViewLink",
        ).execute()
        folder_id = folder["id"]
        link = folder.get("webViewLink") or f"https://drive.google.com/drive/folders/{folder_id}"
        return folder_id, link
    except Exception:
        logger.exception("Failed to create Drive folder for emergency %s", emergency_id)
        return None


def share_folder_with_email(folder_id: str, email: str) -> bool:
    """Grants a specific trusted contact's email read access to the folder."""
    client = _get_client()
    if client is None or not folder_id:
        return False
    try:
        client.permissions().create(
            fileId=folder_id,
            body={"type": "user", "role": "reader", "emailAddress": email},
            sendNotificationEmail=False,
        ).execute()
        return True
    except Exception:
        logger.exception("Failed to share Drive folder %s with %s", folder_id, email)
        return False


def make_folder_link_shareable(folder_id: str) -> bool:
    """Fallback: 'anyone with the link can view' — used when a trusted
    contact's email isn't a Google account Drive can grant access to
    directly, so the link the app sends them still works."""
    client = _get_client()
    if client is None or not folder_id:
        return False
    try:
        client.permissions().create(
            fileId=folder_id,
            body={"type": "anyone", "role": "reader"},
        ).execute()
        return True
    except Exception:
        logger.exception("Failed to make Drive folder %s link-shareable", folder_id)
        return False


def upload_file_to_folder(folder_id: str, local_path: str, filename: str, mime_type: str) -> str | None:
    """Uploads one evidence file into the incident's Drive folder.
    Returns the file's webViewLink, or None on failure (caller should keep
    the locally-stored copy either way)."""
    client = _get_client()
    if client is None or not folder_id:
        return None
    try:
        from googleapiclient.http import MediaFileUpload

        media = MediaFileUpload(local_path, mimetype=mime_type, resumable=False)
        file = client.files().create(
            body={"name": filename, "parents": [folder_id]},
            media_body=media,
            fields="id, webViewLink",
        ).execute()
        return file.get("webViewLink")
    except Exception:
        logger.exception("Failed to upload %s to Drive folder %s", filename, folder_id)
        return None
