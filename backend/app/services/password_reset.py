"""Password reset tokens: issue, verify, consume.

Only the SHA-256 hash of a token is persisted. The value that can actually
reset an account exists solely in the email that was sent, so a database leak
yields nothing usable — which is the whole point of hashing them.
"""

import datetime as dt
import hashlib
import logging
import secrets

from sqlalchemy.orm import Session

from app.config import settings
from app.models.models import PasswordResetToken, User
from app.services.auth import get_password_hash

logger = logging.getLogger(__name__)


def hash_token(raw: str) -> str:
    """Tokens are high-entropy random values, so a plain SHA-256 is sufficient:
    there is nothing to brute-force the way there is with a human password."""
    return hashlib.sha256(raw.encode()).hexdigest()


def issue(db: Session, user: User) -> str | None:
    """Create a token and return its raw value, or None if the user is throttled.

    Throttling is per user rather than per IP: Cloudflare hides client IPs
    unless we parse CF-Connecting-IP, and what actually needs limiting is how
    much mail one mailbox can be made to receive.
    """
    since = dt.datetime.utcnow() - dt.timedelta(hours=1)
    recent = (
        db.query(PasswordResetToken)
        .filter(PasswordResetToken.user_id == user.id,
                PasswordResetToken.created_at >= since)
        .count()
    )
    if recent >= settings.PASSWORD_RESET_MAX_PER_HOUR:
        logger.warning("password reset throttled for user %s (%d in the last hour)",
                       user.id, recent)
        return None

    raw = secrets.token_urlsafe(32)
    db.add(PasswordResetToken(
        user_id=user.id,
        token_hash=hash_token(raw),
        expires_at=dt.datetime.utcnow() + dt.timedelta(minutes=settings.PASSWORD_RESET_TTL_MINUTES),
        # created_at has a server default, but SQLite in tests does not apply it
        # until flush, and the throttle query above reads it back immediately.
        created_at=dt.datetime.utcnow(),
    ))
    db.commit()
    return raw


def consume(db: Session, raw: str, new_password: str) -> bool:
    """Validate a token and apply the new password. False if it is not usable."""
    if not raw:
        return False

    row = (
        db.query(PasswordResetToken)
        .filter(PasswordResetToken.token_hash == hash_token(raw))
        .first()
    )
    now = dt.datetime.utcnow()
    if row is None or row.used_at is not None or row.expires_at < now:
        return False

    user = db.query(User).filter(User.id == row.user_id).first()
    if user is None:
        return False

    user.hashed_password = get_password_hash(new_password)
    # Invalidates every access token issued before this instant — without it a
    # stolen session would survive the reset for the full 7-day token lifetime.
    user.password_changed_at = now

    # Burn this token and any other outstanding one for the same user, so a
    # second reset email cannot be replayed later.
    db.query(PasswordResetToken).filter(
        PasswordResetToken.user_id == user.id,
        PasswordResetToken.used_at.is_(None),
    ).update({PasswordResetToken.used_at: now}, synchronize_session=False)

    db.commit()
    logger.info("password reset completed for user %s", user.id)
    return True


def reset_url(raw: str) -> str:
    return f"{settings.SITE_URL.rstrip('/')}/reset-password?token={raw}"


def build_email_html(raw: str) -> str:
    link = reset_url(raw)
    minutes = settings.PASSWORD_RESET_TTL_MINUTES
    return f"""
    <div style="font-family:system-ui,-apple-system,sans-serif;max-width:520px">
      <h2 style="margin:0 0 16px">Reset your IELTS Assist password</h2>
      <p>Click the button below to choose a new password.
         This link expires in {minutes} minutes and can be used once.</p>
      <p style="margin:24px 0">
        <a href="{link}"
           style="background:#4F46E5;color:#fff;padding:12px 20px;border-radius:6px;
                  text-decoration:none;display:inline-block">Reset password</a>
      </p>
      <p style="color:#6B7280;font-size:14px">
        If the button does not work, paste this into your browser:<br>
        <span style="word-break:break-all">{link}</span>
      </p>
      <p style="color:#6B7280;font-size:14px">
        If you did not request this, you can ignore this email — your password
        will not change.
      </p>
    </div>
    """
