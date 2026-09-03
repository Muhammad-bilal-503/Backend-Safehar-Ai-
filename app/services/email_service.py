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


async def notify_emergency_location(user_name: str, contacts: list, lat: float, lng: float) -> dict:
    """Emails live location to all REGISTERED trusted contacts. Skips unregistered ones."""
    delivered, skipped = 0, 0
    link = maps_link(lat, lng)
    for c in contacts:
        if not c.email or c.status == "pending":
            skipped += 1
            continue
        html = f"""
        <p><strong>{user_name}</strong> has activated an SOS emergency alert on SafeHer AI.</p>
        <p>Their live location: <a href="{link}">{link}</a></p>
        <p>Please check on them or contact emergency services if needed.</p>
        """
        ok = await send_email(c.email, f"🚨 Emergency Alert from {user_name}", html)
        delivered += 1 if ok else 0
        skipped += 0 if ok else 1
    return {"delivered": delivered, "skipped": skipped, "total": len(contacts)}


async def notify_journey_contact(user_name: str, contact, event: str, from_label: str, to_label: str) -> bool:
    if not contact or not contact.email or contact.status == "pending":
        return False
    subjects = {
        "started": f"{user_name} started a journey — SafeHer AI",
        "deviated": f"⚠️ {user_name} has gone off their planned route",
        "arrived": f"✅ {user_name} has arrived safely",
    }
    bodies = {
        "started": f"<p>{user_name} started a journey from <strong>{from_label}</strong> to <strong>{to_label}</strong>. You'll be notified of any issues.</p>",
        "deviated": f"<p>{user_name}'s journey from <strong>{from_label}</strong> to <strong>{to_label}</strong> has deviated from the planned route. Please check on them.</p>",
        "arrived": f"<p>{user_name} has arrived safely at <strong>{to_label}</strong>.</p>",
    }
    return await send_email(contact.email, subjects.get(event, "SafeHer AI update"), bodies.get(event, ""))
