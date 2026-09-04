"""SMTP email notifications — replaces base44 notifyEmergencyLocation / notifyJourneyContact."""
import logging

import aiosmtplib
from email.message import EmailMessage

from app.core.config import settings

logger = logging.getLogger("safeher.email")


async def send_email(to_email: str, subject: str, body_html: str) -> bool:
    if not settings.SMTP_HOST or not settings.SMTP_USERNAME:
        # No SMTP configured (local dev) — log instead of failing the request.
        logger.info("[DEV EMAIL] To: %s | Subject: %s\n%s", to_email, subject, body_html)
        return True

    message = EmailMessage()
    message["From"] = settings.SMTP_FROM
    message["To"] = to_email
    message["Subject"] = subject
    message.set_content("This email requires an HTML-capable client.")
    message.add_alternative(body_html, subtype="html")

    try:
        await aiosmtplib.send(
            message,
            hostname=settings.SMTP_HOST,
            port=settings.SMTP_PORT,
            username=settings.SMTP_USERNAME,
            password=settings.SMTP_PASSWORD,
            start_tls=True,
        )
        return True
    except Exception:
        logger.exception("Failed to send email to %s", to_email)
        return False


def maps_link(lat: float, lng: float) -> str:
    return f"https://www.google.com/maps?q={lat},{lng}"


def tracking_link(kind: str, item_id: str) -> str:
    from app.core.config import settings
    return f"{settings.PUBLIC_BASE_URL}/track/{kind}/{item_id}"


async def notify_emergency_location(user_name: str, contacts: list, lat: float, lng: float, emergency_id: str) -> dict:
    """Emails live location to all REGISTERED trusted contacts. Skips unregistered ones."""
    delivered, skipped = 0, 0
    link = maps_link(lat, lng)
    track = tracking_link("emergency", emergency_id)
    for c in contacts:
        if not c.email or c.status == "pending":
            skipped += 1
            continue
        html = f"""
        <p><strong>{user_name}</strong> has activated an SOS emergency alert on SafeHer AI.</p>
        <p>Track their live location: <a href="{track}">{track}</a></p>
        <p>(Snapshot at time of alert: <a href="{link}">{link}</a>)</p>
        <p>Please check on them or contact emergency services if needed.</p>
        """
        ok = await send_email(c.email, f"🚨 Emergency Alert from {user_name}", html)
        delivered += 1 if ok else 0
        skipped += 0 if ok else 1
    return {"delivered": delivered, "skipped": skipped, "total": len(contacts)}


async def notify_drive_evidence_link(contact, user_name: str, folder_link: str) -> bool:
    """Sent exactly once per emergency, right after the first successful
    evidence upload to the incident's Google Drive folder."""
    if not contact or not contact.email or contact.status == "pending":
        return False
    html = f"""
    <p><strong>{user_name}</strong>'s SOS evidence (photos/video/audio) is being uploaded live to a
    shared Google Drive folder as it's captured.</p>
    <p>View the folder: <a href="{folder_link}">{folder_link}</a></p>
    <p>New evidence appears automatically — you don't need to ask for a new link.</p>
    """
    return await send_email(contact.email, f"📁 Live evidence folder from {user_name}", html)


async def notify_journey_contact(user_name: str, contact, event: str, from_label: str, to_label: str, journey_id: str) -> bool:
    if not contact or not contact.email or contact.status == "pending":
        return False
    track = tracking_link("journey", journey_id)
    subjects = {
        "started": f"{user_name} started a journey — SafeHer AI",
        "deviated": f"⚠️ {user_name} has gone off their planned route",
        "arrived": f"✅ {user_name} has arrived safely",
    }
    bodies = {
        "started": f"<p>{user_name} started a journey from <strong>{from_label}</strong> to <strong>{to_label}</strong>.</p><p>Track live: <a href=\"{track}\">{track}</a></p>",
        "deviated": f"<p>{user_name}'s journey from <strong>{from_label}</strong> to <strong>{to_label}</strong> has deviated from the planned route. Please check on them.</p><p>Track live: <a href=\"{track}\">{track}</a></p>",
        "arrived": f"<p>{user_name} has arrived safely at <strong>{to_label}</strong>.</p>",
    }
    return await send_email(contact.email, subjects.get(event, "SafeHer AI update"), bodies.get(event, ""))
