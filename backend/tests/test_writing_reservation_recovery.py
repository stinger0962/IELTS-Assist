"""Synthetic stopped-worker recovery primitives, not an operator recovery API.

No test calls a grader/provider. Human evidence gates are documented in the runbook;
the low-level release helper does NOT enforce those gates.
"""
from datetime import datetime, timedelta

import pytest
from fastapi import HTTPException

from app.config import settings
from app.models.models import GeneratedPractice, UserPractice, WritingReviewReservation
from app.services.study_pass import (
    Reservation, finalize_writing_review, grant_study_pass, has_full_mock_access,
    release_writing_review, reserve_writing_review, study_pass_status,
)


@pytest.fixture(autouse=True)
def enabled(monkeypatch):
    monkeypatch.setattr(settings, "STUDY_PASS_ENABLED", True)


def attempt(db, user):
    gp = GeneratedPractice(skill="writing", content="{}")
    db.add(gp)
    db.flush()
    card = UserPractice(user_id=user.id, practice_id=gp.id)
    db.add(card)
    db.commit()
    reservation = reserve_writing_review(db, user, gp.id)
    return card, reservation


def balance(db, user):
    return study_pass_status(db, user)["writing_reviews_remaining"]


def save_result(db, card, reservation, text="synthetic saved result"):
    # Match writing route's atomic result + finalize + rollback boundary.
    try:
        card.submitted_at = datetime.utcnow()
        card.user_answers = text
        card.score = 6
        db.flush()  # Even an already flushed late result must roll back.
        finalize_writing_review(db, reservation)
        db.commit()
    except Exception:
        db.rollback()
        release_writing_review(db, reservation)
        raise


def test_age_alone_never_releases_or_refunds(test_db, test_user):
    card, reservation = attempt(test_db, test_user)
    row = test_db.get(WritingReviewReservation, reservation.id)
    row.created_at = row.updated_at = datetime.utcnow() - timedelta(days=60)
    test_db.commit()
    assert balance(test_db, test_user) == 0
    with pytest.raises(HTTPException) as error:
        reserve_writing_review(test_db, test_user, card.practice_id)
    assert error.value.status_code == 409
    test_db.refresh(row)
    assert row.state == "pending" and row.token == reservation.token
    assert card.submitted_at is None


def test_stopped_attempt_release_is_exactly_once_and_retry_has_new_identity(test_db, test_user):
    card, old = attempt(test_db, test_user)
    row = test_db.get(WritingReviewReservation, old.id)
    old_creation = datetime.utcnow() - timedelta(days=2)
    row.created_at = row.updated_at = old_creation
    test_db.commit()
    # Synthetic worker is stopped: no grading request exists in this fixture.
    release_writing_review(test_db, old)
    release_writing_review(test_db, old)
    assert balance(test_db, test_user) == 1
    retry = reserve_writing_review(test_db, test_user, card.practice_id)
    test_db.refresh(row)
    assert retry.id == old.id and retry.token != old.token
    assert row.created_at == old_creation  # Not the current attempt's start time.
    assert row.updated_at > old_creation
    release_writing_review(test_db, old)
    assert balance(test_db, test_user) == 0
    test_db.refresh(row)
    assert row.state == "pending" and row.token == retry.token


@pytest.mark.parametrize("retry_started", [False, True])
def test_late_old_completion_cannot_save_result_or_refund_new_attempt(
        test_db, test_user, retry_started):
    card, old = attempt(test_db, test_user)
    release_writing_review(test_db, old)
    retry = (reserve_writing_review(test_db, test_user, card.practice_id)
             if retry_started else None)
    with pytest.raises(HTTPException) as error:
        save_result(test_db, card, old, "late stale worker output")
    assert error.value.status_code == 409
    test_db.refresh(card)
    assert card.submitted_at is None and card.user_answers is None and card.score is None
    assert balance(test_db, test_user) == (0 if retry_started else 1)
    if retry:
        save_result(test_db, card, retry)
        release_writing_review(test_db, old)
        test_db.refresh(card)
        assert card.user_answers == "synthetic saved result"
        assert balance(test_db, test_user) == 0


def test_completed_result_is_never_released_or_regraded(test_db, test_user):
    card, reservation = attempt(test_db, test_user)
    save_result(test_db, card, reservation)
    release_writing_review(test_db, reservation)
    release_writing_review(test_db, reservation)
    test_db.refresh(card)
    assert card.user_answers == "synthetic saved result"
    assert balance(test_db, test_user) == 0
    with pytest.raises(HTTPException) as error:
        reserve_writing_review(test_db, test_user, card.practice_id)
    assert error.value.status_code == 409


def test_wrong_token_and_missing_attempt_do_nothing(test_db, test_user):
    _, reservation = attempt(test_db, test_user)
    release_writing_review(test_db, Reservation(reservation.id, "not-the-token"))
    release_writing_review(test_db, Reservation(reservation.id + 999, reservation.token))
    assert balance(test_db, test_user) == 0
    row = test_db.get(WritingReviewReservation, reservation.id)
    assert row.state == "pending" and row.token == reservation.token


@pytest.mark.parametrize("termination", ["expired", "revoked"])
def test_recovery_restores_original_grant_not_current_entitlement(test_db, test_user, termination):
    grant = grant_study_pass(test_db, test_user.id, "recovery:synthetic", 2)
    test_db.commit()
    _, reservation = attempt(test_db, test_user)
    test_db.refresh(grant)
    assert grant.reviews_remaining == 1
    if termination == "expired":
        grant.expires_at = datetime.utcnow() - timedelta(seconds=1)
    else:
        grant.revoked_at = datetime.utcnow()
    test_db.commit()
    release_writing_review(test_db, reservation)
    release_writing_review(test_db, reservation)
    test_db.refresh(grant)
    assert grant.reviews_remaining == 2
    assert not has_full_mock_access(test_db, test_user)
    assert balance(test_db, test_user) == 1  # Untouched lifetime trial, not restored pass.
