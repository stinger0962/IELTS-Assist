"""Opt-in entitlements. All grants are internal/test fixtures, never public purchases.

Reservation commits before slow grading. Finalization belongs in the same transaction
as the saved result. Never automatically release a pending reservation on a timer:
a worker may still be grading. Reconcile crashed work manually before retrying it.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import update, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.models.models import StudyPassGrant, UserPractice, WritingReviewReservation


@dataclass(frozen=True)
class Reservation:
    id: int
    token: str


def _active_pass(db, user_id, now):
    return db.query(StudyPassGrant).filter(
        StudyPassGrant.user_id == user_id, StudyPassGrant.kind == "pass",
        StudyPassGrant.revoked_at.is_(None), StudyPassGrant.starts_at <= now,
        StudyPassGrant.expires_at > now,
    ).order_by(StudyPassGrant.expires_at.desc(), StudyPassGrant.id.desc()).first()


def has_full_mock_access(db, user, now=None):
    return user.role == "vip" or (
        settings.STUDY_PASS_ENABLED
        and _active_pass(db, user.id, now or datetime.utcnow()) is not None
    )


def study_pass_status(db, user, now=None):
    now = now or datetime.utcnow()
    base = dict(enabled=settings.STUDY_PASS_ENABLED, status="none", expires_at=None,
                writing_reviews_remaining=None, full_mock_access=user.role == "vip")
    if not settings.STUDY_PASS_ENABLED:
        return base
    grant = _active_pass(db, user.id, now)
    if grant:
        base.update(status="active", expires_at=grant.expires_at.isoformat() + "Z",
                    full_mock_access=True, writing_reviews_remaining=grant.reviews_remaining)
    else:
        previous = db.query(StudyPassGrant).filter(
            StudyPassGrant.user_id == user.id, StudyPassGrant.kind == "pass",
            StudyPassGrant.expires_at <= now,
        ).order_by(StudyPassGrant.expires_at.desc()).first()
        if previous:
            base.update(status="expired", expires_at=previous.expires_at.isoformat() + "Z")
        trial = db.query(StudyPassGrant).filter(
            StudyPassGrant.source_key == f"trial:{user.id}",
            StudyPassGrant.user_id == user.id, StudyPassGrant.kind == "trial",
        ).first()
        base["writing_reviews_remaining"] = (
            0 if trial and trial.revoked_at else trial.reviews_remaining if trial else 1
        )
    if user.role == "vip":
        base["writing_reviews_remaining"] = None
    return base


def grant_study_pass(db: Session, user_id: int, source_key: str, reviews: int, now=None):
    """Internal 30-day fixture/integration hook. Caller commits; no public grant route.

    Same source key is idempotent only for the same owner/allowance. A future payment
    integration must verify settlement and serialize duplicate delivery before calling.
    """
    now = now or datetime.utcnow()
    if not source_key or source_key.startswith("trial:") or reviews < 1:
        raise ValueError("A unique non-trial source key and positive allowance are required")
    existing = db.query(StudyPassGrant).filter_by(source_key=source_key).first()
    if existing:
        if existing.user_id != user_id or existing.kind != "pass" or existing.reviews_granted != reviews:
            raise ValueError("Grant source key belongs to another entitlement")
        return existing
    grant = StudyPassGrant(user_id=user_id, source_key=source_key, kind="pass",
                           starts_at=now, expires_at=now + timedelta(days=30),
                           reviews_granted=reviews, reviews_remaining=reviews)
    db.add(grant)
    db.flush()
    return grant


def _ensure_trial(db, user_id, now):
    grant = db.query(StudyPassGrant).filter_by(source_key=f"trial:{user_id}").first()
    if grant:
        return grant
    try:
        # Savepoint avoids rolling back any caller reads on duplicate creation.
        with db.begin_nested():
            grant = StudyPassGrant(user_id=user_id, source_key=f"trial:{user_id}",
                                   kind="trial", starts_at=now, expires_at=None,
                                   reviews_granted=1, reviews_remaining=1)
            db.add(grant)
            db.flush()
    except IntegrityError:
        grant = db.query(StudyPassGrant).filter_by(source_key=f"trial:{user_id}").one()
    return grant


def reserve_writing_review(db: Session, user, practice_id: int):
    if not settings.STUDY_PASS_ENABLED:
        return None
    now = datetime.utcnow()
    card = db.query(UserPractice).filter_by(user_id=user.id, practice_id=practice_id).first()
    if not card:
        raise HTTPException(404, "Active practice not found")
    if card.submitted_at is not None:
        raise HTTPException(409, "Writing review already completed")
    grant = None
    if user.role != "vip":
        grant = _active_pass(db, user.id, now) or _ensure_trial(db, user.id, now)
    token = str(uuid4())
    try:
        reservation = db.query(WritingReviewReservation).filter_by(user_practice_id=card.id).first()
        if reservation:
            changed = db.execute(update(WritingReviewReservation).where(
                WritingReviewReservation.id == reservation.id,
                WritingReviewReservation.user_id == user.id,
                WritingReviewReservation.state == "released",
            ).values(state="pending", token=token, grant_id=grant.id if grant else None,
                     updated_at=now)).rowcount
            if changed != 1:
                raise HTTPException(409, "Writing review is pending or already completed")
            reservation_id = reservation.id
        else:
            reservation = WritingReviewReservation(
                user_id=user.id, user_practice_id=card.id, grant_id=grant.id if grant else None,
                token=token, state="pending", created_at=now, updated_at=now,
            )
            db.add(reservation)
            db.flush()
            reservation_id = reservation.id
        if grant:
            changed = db.execute(update(StudyPassGrant).where(
                StudyPassGrant.id == grant.id, StudyPassGrant.reviews_remaining > 0,
                StudyPassGrant.revoked_at.is_(None),
                StudyPassGrant.starts_at <= now,
                or_(StudyPassGrant.expires_at.is_(None), StudyPassGrant.expires_at > now),
            ).values(reviews_remaining=StudyPassGrant.reviews_remaining - 1)).rowcount
            if changed != 1:
                raise HTTPException(402, {"code": "study_pass_required", "message": "No writing reviews remaining"})
        db.commit()
        return Reservation(reservation_id, token)
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Writing review is pending or already completed")
    except Exception:
        db.rollback()
        raise


def finalize_writing_review(db: Session, reservation):
    if reservation is None:
        return
    changed = db.execute(update(WritingReviewReservation).where(
        WritingReviewReservation.id == reservation.id,
        WritingReviewReservation.token == reservation.token,
        WritingReviewReservation.state == "pending",
    ).values(state="completed", updated_at=datetime.utcnow())).rowcount
    if changed != 1:
        raise HTTPException(409, "Writing reservation is no longer pending")
    # Do not commit: result persistence and completion must succeed together.


def release_writing_review(db: Session, reservation):
    if reservation is None:
        return
    db.rollback()
    row = db.query(WritingReviewReservation).filter_by(
        id=reservation.id, token=reservation.token, state="pending").first()
    if not row:
        return
    changed = db.execute(update(WritingReviewReservation).where(
        WritingReviewReservation.id == reservation.id,
        WritingReviewReservation.token == reservation.token,
        WritingReviewReservation.state == "pending",
    ).values(state="released", updated_at=datetime.utcnow())).rowcount
    if changed == 1 and row.grant_id is not None:
        db.execute(update(StudyPassGrant).where(StudyPassGrant.id == row.grant_id).values(
            reviews_remaining=StudyPassGrant.reviews_remaining + 1))
    db.commit()
