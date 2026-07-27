import pytest
from fastapi import HTTPException

from app.models.models import UsageCounter, User
from app.services import quota


def _user(db, email="q@example.com"):
    u = User(email=email, username=email.split("@")[0], full_name="Q", hashed_password="x")
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def test_first_call_is_allowed_and_counted(test_db):
    u = _user(test_db)
    quota.consume(test_db, u.id, "lookup", limit=3)
    row = test_db.query(UsageCounter).filter_by(user_id=u.id, category="lookup").one()
    assert row.count == 1


def test_exceeding_the_limit_raises_429(test_db):
    u = _user(test_db)
    for _ in range(3):
        quota.consume(test_db, u.id, "lookup", limit=3)
    with pytest.raises(HTTPException) as exc:
        quota.consume(test_db, u.id, "lookup", limit=3)
    assert exc.value.status_code == 429
    assert "midnight UTC" in exc.value.detail


def test_refund_gives_the_call_back(test_db):
    """Cache hits cost nothing, so they must not consume quota."""
    u = _user(test_db)
    quota.consume(test_db, u.id, "lookup", limit=1)
    quota.refund(test_db, u.id, "lookup")
    quota.consume(test_db, u.id, "lookup", limit=1)  # must not raise


def test_refund_never_goes_negative(test_db):
    u = _user(test_db)
    quota.refund(test_db, u.id, "lookup")
    row = test_db.query(UsageCounter).filter_by(user_id=u.id, category="lookup").one()
    assert row.count == 0


def test_categories_are_counted_separately(test_db):
    u = _user(test_db)
    quota.consume(test_db, u.id, "lookup", limit=1)
    quota.consume(test_db, u.id, "grade", limit=1)  # must not raise


def test_users_are_counted_separately(test_db):
    a = _user(test_db, "a@example.com")
    b = _user(test_db, "b@example.com")
    quota.consume(test_db, a.id, "grade", limit=1)
    quota.consume(test_db, b.id, "grade", limit=1)  # b's quota is untouched by a


def test_estimated_spend_sums_weighted_usage(test_db):
    u = _user(test_db)
    quota.consume(test_db, u.id, "grade", limit=10)
    assert quota.estimated_spend_today(test_db) == pytest.approx(quota.COST_WEIGHTS["grade"])


def test_breaker_trips_above_the_cap(test_db):
    u = _user(test_db)
    quota.consume(test_db, u.id, "grade", limit=100)
    with pytest.raises(HTTPException) as exc:
        quota.check_breaker(test_db, cap_usd=0.001)
    assert exc.value.status_code == 503


def test_breaker_allows_below_the_cap(test_db):
    u = _user(test_db)
    quota.consume(test_db, u.id, "lookup", limit=100)
    quota.check_breaker(test_db, cap_usd=100.0)  # must not raise


# ── End-to-end through the API ───────────────────────────────────────────────

def test_cached_lookup_does_not_consume_quota(client, test_user, auth_token, monkeypatch, test_db):
    """define-word serves most lookups free from cache; those must be refunded."""
    from app.services import vocab

    monkeypatch.setattr(vocab, "generate_entry", lambda w, c=None: {
        "definition_en": "a ridge of rock", "definition_zh": None,
        "example": None, "phonetic": None})
    monkeypatch.setattr(vocab, "synthesize_pronunciation", lambda w: None)

    h = {"Authorization": f"Bearer {auth_token}"}
    first = client.post("/api/generate/define-word", json={"word": "reef"}, headers=h)
    second = client.post("/api/generate/define-word", json={"word": "reef"}, headers=h)

    assert first.json()["cached"] is False
    assert second.json()["cached"] is True
    row = test_db.query(UsageCounter).filter_by(user_id=test_user.id, category="lookup").one()
    assert row.count == 1, "the cached second lookup must not consume quota"


def test_route_returns_429_when_the_limit_is_reached(client, test_user, auth_token, monkeypatch):
    from app.config import settings
    from app.services import vocab

    monkeypatch.setattr(settings, "QUOTA_LOOKUP_PER_DAY", 2)
    monkeypatch.setattr(vocab, "generate_entry", lambda w, c=None: {
        "definition_en": "x", "definition_zh": None, "example": None, "phonetic": None})
    monkeypatch.setattr(vocab, "synthesize_pronunciation", lambda w: None)

    h = {"Authorization": f"Bearer {auth_token}"}
    assert client.post("/api/generate/define-word", json={"word": "aaa"}, headers=h).status_code == 200
    assert client.post("/api/generate/define-word", json={"word": "bbb"}, headers=h).status_code == 200
    third = client.post("/api/generate/define-word", json={"word": "ccc"}, headers=h)
    assert third.status_code == 429
    assert "midnight UTC" in third.json()["detail"]


def test_breaker_returns_503_on_paid_routes(client, test_user, auth_token, monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "DAILY_SPEND_CAP_USD", 0.0)

    resp = client.post("/api/generate/define-word", json={"word": "ddd"},
                       headers={"Authorization": f"Bearer {auth_token}"})
    assert resp.status_code == 503


def test_quotas_can_be_disabled(client, test_user, auth_token, monkeypatch):
    """Kill switch: an env change must restore service without a redeploy."""
    from app.config import settings
    from app.services import vocab

    monkeypatch.setattr(settings, "QUOTAS_ENABLED", False)
    monkeypatch.setattr(settings, "QUOTA_LOOKUP_PER_DAY", 0)
    monkeypatch.setattr(vocab, "generate_entry", lambda w, c=None: {
        "definition_en": "x", "definition_zh": None, "example": None, "phonetic": None})
    monkeypatch.setattr(vocab, "synthesize_pronunciation", lambda w: None)

    resp = client.post("/api/generate/define-word", json={"word": "eee"},
                       headers={"Authorization": f"Bearer {auth_token}"})
    assert resp.status_code == 200
