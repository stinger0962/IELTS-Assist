"""Transactional email via Resend.

Deliberately degrades instead of failing: with no RESEND_API_KEY configured the
message is logged and the caller is told it was not sent. That lets the password
reset flow ship and be exercised before the credential exists — the same pattern
used for the Google TTS key.
"""

import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

RESEND_ENDPOINT = "https://api.resend.com/emails"


def is_configured() -> bool:
    return bool(settings.RESEND_API_KEY)


def send_email(*, to: str, subject: str, html: str) -> bool:
    """Send one email. Returns True only if the provider accepted it.

    Never raises: a mail outage must not turn into a 500 on a user-facing flow.
    """
    if not is_configured():
        logger.warning(
            "email not sent to %s (RESEND_API_KEY unset): %s", to, subject
        )
        return False

    try:
        response = httpx.post(
            RESEND_ENDPOINT,
            headers={"Authorization": f"Bearer {settings.RESEND_API_KEY}"},
            json={
                "from": settings.EMAIL_FROM,
                "to": [to],
                "subject": subject,
                "html": html,
            },
            timeout=10.0,
        )
    except Exception as e:
        logger.error("email transport failed for %s: %s", to, e)
        return False

    if response.status_code >= 400:
        # Resend's body explains domain-verification failures, which is the most
        # likely cause early on — log it, but never the message body itself.
        logger.error(
            "Resend rejected the message to %s: %s %s",
            to, response.status_code, response.text[:300],
        )
        return False

    logger.info("email sent to %s: %s", to, subject)
    return True
