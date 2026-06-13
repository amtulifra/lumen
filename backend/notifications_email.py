import logging

import httpx

from config import settings

logger = logging.getLogger("lumen")


async def send_email_notification(
    to_email: str,
    subject: str,
    body_text: str,
) -> bool:
    provider = settings.email_provider.strip().lower()
    if provider == "none":
        return False
    if provider == "resend":
        return await _send_resend(to_email, subject, body_text)
    if provider == "postmark":
        return await _send_postmark(to_email, subject, body_text)

    logger.warning("Unknown email provider '%s'; skipping email", settings.email_provider)
    return False


async def _send_resend(to_email: str, subject: str, body_text: str) -> bool:
    if not settings.resend_api_key:
        logger.warning("resend_api_key is not configured; skipping email")
        return False
    payload = {
        "from": settings.email_from,
        "to": [to_email],
        "subject": subject,
        "text": body_text,
    }
    headers = {"Authorization": f"Bearer {settings.resend_api_key}"}
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post("https://api.resend.com/emails", json=payload, headers=headers)
    if response.status_code >= 400:
        logger.warning("Resend send failed (%s): %s", response.status_code, response.text)
        return False
    return True


async def _send_postmark(to_email: str, subject: str, body_text: str) -> bool:
    if not settings.postmark_server_token:
        logger.warning("postmark_server_token is not configured; skipping email")
        return False
    payload = {
        "From": settings.email_from,
        "To": to_email,
        "Subject": subject,
        "TextBody": body_text,
    }
    headers = {
        "X-Postmark-Server-Token": settings.postmark_server_token,
        "Accept": "application/json",
    }
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post("https://api.postmarkapp.com/email", json=payload, headers=headers)
    if response.status_code >= 400:
        logger.warning("Postmark send failed (%s): %s", response.status_code, response.text)
        return False
    return True
