"""Per-user daily quotas and a global spend circuit breaker for paid AI calls.

Counters live in Postgres rather than memory: deploys restart the app several
times a day and would otherwise hand everyone a fresh quota.

Limits are per-category because costs are wildly asymmetric — a graded speaking
answer costs roughly fifty times a vocabulary lookup, so one flat request limit
would either strangle lookups or leave grading wide open.
"""

import datetime as dt
import logging

from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.models import UsageCounter, User
from app.services.auth import get_current_user

logger = logging.getLogger(__name__)

# Rough USD per call, used only by the global breaker. Order-of-magnitude is
# enough — this decides when to stop spending, not what to bill.
COST_WEIGHTS = {"grade": 0.04, "generate": 0.05, "lookup": 0.001}

LIMITS = {
    "grade": lambda: settings.QUOTA_GRADE_PER_DAY,
    "generate": lambda: settings.QUOTA_GENERATE_PER_DAY,
    "lookup": lambda: settings.QUOTA_LOOKUP_PER_DAY,
}


def _today() -> dt.date:
    return dt.datetime.now(dt.timezone.utc).date()


def _row(db: Session, user_id: int, category: str) -> UsageCounter:
    row = (
        db.query(UsageCounter)
        .filter_by(user_id=user_id, day=_today(), category=category)
        .first()
    )
    if row is None:
        row = UsageCounter(user_id=user_id, day=_today(), category=category, count=0)
        db.add(row)
        db.flush()
    return row


def consume(db: Session, user_id: int, category: str, limit: int) -> None:
    """Count one paid call. Raises 429 once the user is over their daily limit."""
    row = _row(db, user_id, category)
    if row.count >= limit:
        raise HTTPException(
            status_code=429,
            detail=f"Daily {category} limit reached ({limit}). It resets at midnight UTC.",
        )
    row.count += 1
    db.commit()


def refund(db: Session, user_id: int, category: str) -> None:
    """Give a call back when it turned out to cost nothing (e.g. a cache hit)."""
    row = _row(db, user_id, category)
    if row.count > 0:
        row.count -= 1
    db.commit()


def estimated_spend_today(db: Session) -> float:
    """Weighted sum of today's usage across all users, in USD."""
    rows = db.query(UsageCounter).filter(UsageCounter.day == _today()).all()
    return sum(COST_WEIGHTS.get(r.category, 0.0) * r.count for r in rows)


def check_breaker(db: Session, cap_usd: float) -> None:
    """Stop all paid work once the estimated daily spend exceeds the cap."""
    if estimated_spend_today(db) >= cap_usd:
        raise HTTPException(
            status_code=503,
            detail="Daily AI budget reached. Service resumes at midnight UTC.",
        )


def quota(category: str):
    """FastAPI dependency factory: attach to any route that spends money.

    Fails open on unexpected errors — a bug in metering must not take down the
    product. The global breaker remains as the backstop.
    """

    def dependency(
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
    ) -> None:
        if not settings.QUOTAS_ENABLED:
            return
        try:
            check_breaker(db, settings.DAILY_SPEND_CAP_USD)
            consume(db, current_user.id, category, LIMITS[category]())
        except HTTPException:
            raise
        except Exception as e:
            logger.error("quota check failed open for user %s: %s", current_user.id, e)

    return dependency
