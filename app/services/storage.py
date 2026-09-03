"""Local evidence file storage. Files are streamed to disk as raw binary —
no Base64 encode/decode step anywhere in the upload or serving path."""
import os
import uuid

from fastapi import UploadFile

from app.core.config import settings

KIND_DIRS = {"photo": "photos", "video": "videos", "audio": "audio"}


async def save_evidence_file(kind: str, emergency_id: str, upload: UploadFile) -> str:
    subdir = KIND_DIRS[kind]
    ext = os.path.splitext(upload.filename or "")[1] or {"photo": ".jpg", "video": ".mp4", "audio": ".m4a"}[kind]
    folder = os.path.join(settings.MEDIA_ROOT, subdir, emergency_id)
    os.makedirs(folder, exist_ok=True)
    filename = f"{uuid.uuid4().hex}{ext}"
    dest_path = os.path.join(folder, filename)

    with open(dest_path, "wb") as f:
        while chunk := await upload.read(1024 * 1024):
            f.write(chunk)
    await upload.close()

    relative = os.path.join(subdir, emergency_id, filename).replace("\\", "/")
    return relative


def public_url(relative_path: str) -> str:
    return f"{settings.PUBLIC_BASE_URL}/media/{relative_path}"
