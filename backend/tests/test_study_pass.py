from datetime import datetime, timedelta

import pytest
from fastapi import HTTPException

from app.config import settings
from app.models.models import GeneratedPractice, UserPractice, StudyPassGrant
from app.services.study_pass import (
    Reservation, grant_study_pass, has_full_mock_access, study_pass_status,
    reserve_writing_review, finalize_writing_review, release_writing_review,
)


@pytest.fixture(autouse=True)
def enabled(monkeypatch):
    monkeypatch.setattr(settings, "STUDY_PASS_ENABLED", True)


def card(db, user):
    gp = GeneratedPractice(skill="writing", content="{}")
    db.add(gp)
    db.flush()
    db.add(UserPractice(user_id=user.id, practice_id=gp.id))
    db.commit()
    return gp.id


def test_disabled_legacy(test_db, test_user, monkeypatch):
    monkeypatch.setattr(settings, "STUDY_PASS_ENABLED", False)
    assert study_pass_status(test_db, test_user) == dict(
        enabled=False, status="none", expires_at=None,
        writing_reviews_remaining=None, full_mock_access=False)
    assert reserve_writing_review(test_db, test_user, 999) is None
    test_user.role = "vip"
    assert has_full_mock_access(test_db, test_user)


def test_trial_single_use_refund_retry_and_stale_token(test_db, test_user):
    p1, p2 = card(test_db, test_user), card(test_db, test_user)
    assert study_pass_status(test_db, test_user)["writing_reviews_remaining"] == 1
    first = reserve_writing_review(test_db, test_user, p1)
    with pytest.raises(HTTPException) as exc:
        reserve_writing_review(test_db, test_user, p2)
    assert exc.value.status_code == 402
    release_writing_review(test_db, first)
    release_writing_review(test_db, first)
    assert study_pass_status(test_db, test_user)["writing_reviews_remaining"] == 1
    second = reserve_writing_review(test_db, test_user, p1)
    release_writing_review(test_db, first)
    assert study_pass_status(test_db, test_user)["writing_reviews_remaining"] == 0
    with pytest.raises(HTTPException):
        finalize_writing_review(test_db, first)
    test_db.rollback()
    finalize_writing_review(test_db, second)
    test_db.commit()
    release_writing_review(test_db, second)
    assert study_pass_status(test_db, test_user)["writing_reviews_remaining"] == 0


def test_pending_duplicate_no_second_debit(test_db, test_user):
    p = card(test_db, test_user)
    r = reserve_writing_review(test_db, test_user, p)
    with pytest.raises(HTTPException) as exc:
        reserve_writing_review(test_db, test_user, p)
    assert exc.value.status_code == 409
    release_writing_review(test_db, r)


def test_paid_expiry_zero_balance_and_trial(test_db, test_user):
    now = datetime.utcnow()
    grant = grant_study_pass(test_db, test_user.id, "fixture:purchase", 2, now)
    assert grant_study_pass(test_db, test_user.id, "fixture:purchase", 2).id == grant.id
    with pytest.raises(ValueError):
        grant_study_pass(test_db, test_user.id, "fixture:purchase", 3)
    test_db.commit()
    assert grant.expires_at == now + timedelta(days=30)
    assert has_full_mock_access(test_db, test_user)
    for _ in range(2):
        r = reserve_writing_review(test_db, test_user, card(test_db, test_user))
        finalize_writing_review(test_db, r)
        test_db.commit()
    assert study_pass_status(test_db, test_user)["writing_reviews_remaining"] == 0
    assert has_full_mock_access(test_db, test_user)
    with pytest.raises(HTTPException) as exc:
        reserve_writing_review(test_db, test_user, card(test_db, test_user))
    assert exc.value.status_code == 402
    grant.expires_at = now - timedelta(seconds=1)
    test_db.commit()
    status = study_pass_status(test_db, test_user)
    assert status["status"] == "expired" and not status["full_mock_access"]
    assert status["writing_reviews_remaining"] == 1


def test_vip_guard_without_debit(test_db, test_user):
    test_user.role = "vip"
    test_db.commit()
    p = card(test_db, test_user)
    r = reserve_writing_review(test_db, test_user, p)
    assert r is not None
    assert test_db.query(StudyPassGrant).count() == 0
    with pytest.raises(HTTPException) as exc:
        reserve_writing_review(test_db, test_user, p)
    assert exc.value.status_code == 409
    finalize_writing_review(test_db, r)
    test_db.commit()
    assert study_pass_status(test_db, test_user)["writing_reviews_remaining"] is None


def test_finalize_and_result_rollback_together(test_db, test_user):
    p = card(test_db, test_user)
    r = reserve_writing_review(test_db, test_user, p)
    up = test_db.query(UserPractice).filter_by(practice_id=p).one()
    up.submitted_at = datetime.utcnow()
    finalize_writing_review(test_db, r)
    test_db.rollback()
    release_writing_review(test_db, r)
    assert test_db.get(UserPractice, up.id).submitted_at is None
    assert study_pass_status(test_db, test_user)["writing_reviews_remaining"] == 1


def test_status_route_authenticated(client, auth_token):
    assert client.get("/api/study-pass").status_code == 401
    response = client.get("/api/study-pass", headers={"Authorization": f"Bearer {auth_token}"})
    assert response.status_code == 200
    assert response.json()["writing_reviews_remaining"] == 1
