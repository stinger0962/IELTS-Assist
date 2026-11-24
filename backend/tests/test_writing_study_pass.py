"""Route integration: provider operations mocked, no live grading or payment calls."""
import json
from unittest.mock import Mock

import pytest
from fastapi import BackgroundTasks, HTTPException, Request

from app.config import settings
from app.main import app
from app.models.models import GeneratedPractice, User, UserPractice
from app.routers import writing

ESSAY = "This is a sufficiently long sample essay explaining a position with evidence."
GRADE = {
    "examiner_result": {
        "overall_band": 6.5,
        **{name: {"band": 6.5, "evidence": "Sample evidence."} for name in
           ("task_response", "coherence_cohesion", "lexical_resource",
            "grammatical_range_accuracy")},
    },
    "coaching_feedback": {
        "summary": "Sample feedback.", "strengths": ["Clear position."],
        "improvements": ["Develop the evidence."],
    },
    "annotations": [],
}


@pytest.fixture
def grading(monkeypatch):
    monkeypatch.setattr(settings, "STUDY_PASS_ENABLED", True)
    monkeypatch.setattr(settings, "QUOTAS_ENABLED", False)
    grader = Mock()
    grader.grade.return_value = GRADE
    monkeypatch.setattr(writing, "WritingGrader", lambda: grader)
    monkeypatch.setattr(writing, "_extract_writing_topics", Mock())
    return grader


def card(db, user, skill="writing"):
    gp = GeneratedPractice(skill=skill, content=json.dumps({"prompt": {"statement": "Test"}}))
    db.add(gp)
    db.flush()
    up = UserPractice(user_id=user.id, practice_id=gp.id)
    db.add(up)
    db.commit()
    return up


def submit(db, user, up, essay=ESSAY, time=120):
    body = writing.SubmitAIWritingBody(practice_id=up.practice_id, essay=essay, time_seconds=time)
    return writing.submit_ai_writing(body, Request({"type": "http", "app": app}), BackgroundTasks(), db, user)


def test_free_review_then_paywall_and_exact_retry(test_db, test_user, grading):
    first = card(test_db, test_user)
    result = submit(test_db, test_user, first)
    assert result["grading"] == GRADE
    assert submit(test_db, test_user, first, time=135) == result
    assert grading.grade.call_count == 1
    with pytest.raises(HTTPException) as e:
        submit(test_db, test_user, first, essay=ESSAY + " Different.")
    assert e.value.status_code == 409
    second = card(test_db, test_user)
    with pytest.raises(HTTPException) as e:
        submit(test_db, test_user, second)
    assert e.value.status_code == 402
    assert e.value.detail["code"] == "study_pass_required"
    assert grading.grade.call_count == 1


def test_failed_grading_releases_trial_for_retry(test_db, test_user, grading):
    up = card(test_db, test_user)
    grading.grade.side_effect = RuntimeError("provider unavailable")
    with pytest.raises(RuntimeError):
        submit(test_db, test_user, up)
    test_db.refresh(up)
    assert up.submitted_at is None
    grading.grade.side_effect = None
    assert submit(test_db, test_user, up)["overall_band"] == 6.5
    assert grading.grade.call_count == 2


def test_invalid_or_other_owned_card_does_not_reserve(test_db, test_user, grading):
    up = card(test_db, test_user)
    with pytest.raises(HTTPException) as e:
        submit(test_db, test_user, up, essay="Too short")
    assert e.value.status_code == 400
    outsider = User(email="other@example.com", username="other", hashed_password="unused")
    test_db.add(outsider)
    test_db.commit()
    with pytest.raises(HTTPException) as e:
        submit(test_db, outsider, up)
    assert e.value.status_code == 404
    assert grading.grade.call_count == 0
    assert submit(test_db, test_user, up)["ok"]


def test_nonwriting_card_is_not_charged(test_db, test_user, grading):
    with pytest.raises(HTTPException) as e:
        submit(test_db, test_user, card(test_db, test_user, "reading"))
    assert e.value.status_code == 404
    assert submit(test_db, test_user, card(test_db, test_user))["ok"]
    assert grading.grade.call_count == 1


def test_pending_duplicate_cannot_grade_or_spend_again(test_db, test_user, grading):
    up = card(test_db, test_user)
    reservation = writing.reserve_writing_review(test_db, test_user, up.practice_id)
    with pytest.raises(HTTPException) as e:
        submit(test_db, test_user, up)
    assert e.value.status_code == 409
    grading.grade.assert_not_called()
    writing.release_writing_review(test_db, reservation)
    assert submit(test_db, test_user, up)["ok"]


def test_vip_has_no_paid_allowance_limit(test_db, test_user, grading):
    test_user.role = "vip"
    test_db.commit()
    for _ in range(2):
        assert submit(test_db, test_user, card(test_db, test_user))["ok"]
    assert grading.grade.call_count == 2


def test_disabled_preserves_existing_multiple_reviews(test_db, test_user, grading, monkeypatch):
    monkeypatch.setattr(settings, "STUDY_PASS_ENABLED", False)
    for _ in range(2):
        up = card(test_db, test_user)
        assert submit(test_db, test_user, up)["ok"]
    with pytest.raises(HTTPException) as e:
        submit(test_db, test_user, up)
    assert e.value.status_code == 404


def test_finalization_failure_does_not_persist_or_consume(test_db, test_user, grading, monkeypatch):
    up = card(test_db, test_user)
    finalize = writing.finalize_writing_review
    monkeypatch.setattr(writing, "finalize_writing_review", Mock(side_effect=RuntimeError("write failed")))
    with pytest.raises(RuntimeError):
        submit(test_db, test_user, up)
    test_db.refresh(up)
    assert up.submitted_at is None
    assert up.user_answers is None
    monkeypatch.setattr(writing, "finalize_writing_review", finalize)
    assert submit(test_db, test_user, up)["ok"]


def test_disabled_http_route_keeps_abuse_quota(client, test_user, auth_token, grading, monkeypatch):
    monkeypatch.setattr(settings, "STUDY_PASS_ENABLED", False)
    monkeypatch.setattr(settings, "QUOTAS_ENABLED", True)
    monkeypatch.setattr(settings, "QUOTA_GRADE_PER_DAY", 0)
    response = client.post("/api/generate/submit-ai-writing",
        headers={"Authorization": f"Bearer {auth_token}"},
        json={"practice_id": 123, "essay": ESSAY, "time_seconds": 120})
    assert response.status_code == 429
    grading.grade.assert_not_called()


def test_paid_allowance_and_expiry(test_db, test_user, grading):
    from datetime import datetime, timedelta
    from app.services.study_pass import grant_study_pass
    grant = grant_study_pass(test_db, test_user.id, "fixture-pass", reviews=2)
    test_db.commit()
    for _ in range(2):
        assert submit(test_db, test_user, card(test_db, test_user))["ok"]
    with pytest.raises(HTTPException) as e:
        submit(test_db, test_user, card(test_db, test_user))
    assert e.value.status_code == 402
    test_db.refresh(grant)
    assert grant.reviews_remaining == 0
    # Expiry permits only the account's single lifetime trial, not the old pass.
    grant.expires_at = datetime.utcnow() - timedelta(seconds=1)
    test_db.commit()
    assert submit(test_db, test_user, card(test_db, test_user))["ok"]
    with pytest.raises(HTTPException) as e:
        submit(test_db, test_user, card(test_db, test_user))
    assert e.value.status_code == 402
    assert grading.grade.call_count == 3


@pytest.mark.parametrize("malformed", [
    {}, None, {"examiner_result": {"overall_band": 6.5}},
    {**GRADE, "examiner_result": {**GRADE["examiner_result"], "overall_band": float("nan")}},
    {**GRADE, "examiner_result": {**GRADE["examiner_result"], "overall_band": 99}},
    {**GRADE, "examiner_result": {**GRADE["examiner_result"], "task_response": {"band": True, "evidence": "x"}}},
    {**GRADE, "coaching_feedback": {"summary": {}, "strengths": [], "improvements": []}},
    {**GRADE, "annotations": [{"category": "grammar", "severity": "minor", "suggestion": "x", "start_char": 0, "end_char": 9999}]},
])
def test_malformed_grade_does_not_charge_and_can_retry(test_db, test_user, grading, malformed):
    up = card(test_db, test_user)
    grading.grade.return_value = malformed
    with pytest.raises(HTTPException) as e:
        submit(test_db, test_user, up)
    assert e.value.status_code == 502
    test_db.refresh(up)
    assert up.submitted_at is None and up.user_answers is None
    grading.grade.return_value = GRADE
    assert submit(test_db, test_user, up)["ok"]


def test_enabled_quota_counts_only_provider_attempts(test_db, test_user, grading, monkeypatch):
    from app.models.models import UsageCounter
    monkeypatch.setattr(settings, "QUOTAS_ENABLED", True)
    up = card(test_db, test_user)
    with pytest.raises(HTTPException):
        submit(test_db, test_user, up, essay="short")
    assert test_db.query(UsageCounter).count() == 0
    reservation = writing.reserve_writing_review(test_db, test_user, up.practice_id)
    with pytest.raises(HTTPException) as e:
        submit(test_db, test_user, up)
    assert e.value.status_code == 409
    assert test_db.query(UsageCounter).count() == 0
    writing.release_writing_review(test_db, reservation)
    result = submit(test_db, test_user, up)
    assert submit(test_db, test_user, up) == result
    with pytest.raises(HTTPException) as e:
        submit(test_db, test_user, card(test_db, test_user))
    assert e.value.status_code == 402
    assert test_db.query(UsageCounter).one().count == 1
    grading.grade.assert_called_once()


def test_enabled_quota_denial_releases_allowance(test_db, test_user, grading, monkeypatch):
    monkeypatch.setattr(settings, "QUOTAS_ENABLED", True)
    monkeypatch.setattr(settings, "QUOTA_GRADE_PER_DAY", 0)
    up = card(test_db, test_user)
    with pytest.raises(HTTPException) as e:
        submit(test_db, test_user, up)
    assert e.value.status_code == 429
    grading.grade.assert_not_called()
    test_db.refresh(up)
    assert up.submitted_at is None
    monkeypatch.setattr(settings, "QUOTA_GRADE_PER_DAY", 30)
    assert submit(test_db, test_user, up)["ok"]

@pytest.mark.parametrize("status", ["complete", "partial", "unavailable"])
def test_annotation_outcome_persisted_and_replayed_once(test_db, test_user, grading, status):
    from app.services.study_pass import grant_study_pass
    grant = grant_study_pass(test_db, test_user.id, "synthetic-pass", reviews=1)
    test_db.commit()
    grading.grade.return_value = {**GRADE, "annotation_status": status}
    up = card(test_db, test_user)
    result = submit(test_db, test_user, up)
    assert result["grading"]["annotation_status"] == status
    assert json.loads(up.user_answers)["grading"]["annotation_status"] == status
    test_db.refresh(grant)
    assert grant.reviews_remaining == 0
    assert submit(test_db, test_user, up, time=135) == result
    assert grading.grade.call_count == 1
    with pytest.raises(HTTPException) as error:
        submit(test_db, test_user, card(test_db, test_user))
    assert error.value.status_code == 402
