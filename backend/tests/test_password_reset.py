"""Password reset: token handling and the endpoints built on it.

Security properties under test, each chosen because getting it wrong is not
visible from the outside:
  - the raw token is never stored, only its hash
  - tokens expire, are single use, and a reset invalidates the user's others
  - completing a reset invalidates existing sessions (the reason people reset)
  - the request endpoint cannot be used to discover which emails are registered
"""

import datetime as dt

from app.models.models import PasswordResetToken, User
from app.services import password_reset as pr
from app.services.auth import get_password_hash, verify_password


def _user(db, email="reset@example.com"):
    u = User(email=email, username=email.split("@")[0], full_name="R",
             hashed_password=get_password_hash("original-password"))
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


# ── token service ────────────────────────────────────────────────────────────

def test_raw_token_is_never_stored(test_db):
    user = _user(test_db)
    raw = pr.issue(test_db, user)

    row = test_db.query(PasswordResetToken).filter_by(user_id=user.id).one()
    assert row.token_hash != raw, "the raw token must not be stored"
    assert row.token_hash == pr.hash_token(raw)
    assert len(raw) > 20, "token should carry real entropy"


def test_consume_sets_the_new_password(test_db):
    user = _user(test_db)
    raw = pr.issue(test_db, user)

    assert pr.consume(test_db, raw, "brand-new-password") is True

    test_db.refresh(user)
    assert verify_password("brand-new-password", user.hashed_password)
    assert not verify_password("original-password", user.hashed_password)


def test_token_is_single_use(test_db):
    user = _user(test_db)
    raw = pr.issue(test_db, user)

    assert pr.consume(test_db, raw, "first-change") is True
    assert pr.consume(test_db, raw, "second-change") is False

    test_db.refresh(user)
    assert verify_password("first-change", user.hashed_password)


def test_expired_token_is_rejected(test_db):
    user = _user(test_db)
    raw = pr.issue(test_db, user)

    row = test_db.query(PasswordResetToken).filter_by(user_id=user.id).one()
    row.expires_at = dt.datetime.utcnow() - dt.timedelta(minutes=1)
    test_db.commit()

    assert pr.consume(test_db, raw, "too-late") is False
    test_db.refresh(user)
    assert verify_password("original-password", user.hashed_password)


def test_unknown_token_is_rejected(test_db):
    _user(test_db)
    assert pr.consume(test_db, "not-a-real-token", "nope") is False


def test_reset_invalidates_the_users_other_tokens(test_db):
    """Requesting twice then using one must not leave the other live."""
    user = _user(test_db)
    first = pr.issue(test_db, user)
    second = pr.issue(test_db, user)

    assert pr.consume(test_db, second, "changed") is True
    assert pr.consume(test_db, first, "should-not-work") is False


def test_consume_stamps_password_changed_at(test_db):
    user = _user(test_db)
    assert user.password_changed_at is None
    pr.consume(test_db, pr.issue(test_db, user), "changed")
    test_db.refresh(user)
    assert user.password_changed_at is not None


def test_throttle_limits_requests_per_user(test_db, monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "PASSWORD_RESET_MAX_PER_HOUR", 2)

    user = _user(test_db)
    assert pr.issue(test_db, user) is not None
    assert pr.issue(test_db, user) is not None
    assert pr.issue(test_db, user) is None, "third request in an hour must be refused"


# ── endpoints ────────────────────────────────────────────────────────────────

def test_forgot_password_does_not_reveal_whether_an_email_exists(client, test_db):
    _user(test_db, "known@example.com")

    known = client.post("/api/auth/forgot-password", json={"email": "known@example.com"})
    unknown = client.post("/api/auth/forgot-password", json={"email": "nobody@example.com"})

    assert known.status_code == unknown.status_code == 200
    assert known.json() == unknown.json(), "responses must be indistinguishable"


def test_forgot_password_works_with_email_unconfigured(client, test_db, monkeypatch):
    """No RESEND_API_KEY must degrade, not 500."""
    from app.config import settings
    monkeypatch.setattr(settings, "RESEND_API_KEY", "")
    _user(test_db, "nokey@example.com")

    resp = client.post("/api/auth/forgot-password", json={"email": "nokey@example.com"})
    assert resp.status_code == 200


def test_reset_password_endpoint_changes_the_password(client, test_db):
    user = _user(test_db, "flow@example.com")
    raw = pr.issue(test_db, user)

    resp = client.post("/api/auth/reset-password",
                       json={"token": raw, "new_password": "a-fresh-password"})
    assert resp.status_code == 200

    login = client.post("/api/auth/login",
                        data={"username": "flow@example.com", "password": "a-fresh-password"})
    assert login.status_code == 200


def test_reset_password_rejects_a_bad_token(client, test_db):
    _user(test_db, "bad@example.com")
    resp = client.post("/api/auth/reset-password",
                       json={"token": "garbage", "new_password": "whatever-long"})
    assert resp.status_code == 400


def test_reset_password_enforces_a_minimum_length(client, test_db):
    user = _user(test_db, "short@example.com")
    raw = pr.issue(test_db, user)
    resp = client.post("/api/auth/reset-password", json={"token": raw, "new_password": "abc"})
    assert resp.status_code == 422


def test_old_sessions_stop_working_after_a_reset(client, test_db):
    """The point of resetting: whoever held a token must be logged out."""
    import time

    user = _user(test_db, "session@example.com")
    login = client.post("/api/auth/login",
                        data={"username": "session@example.com", "password": "original-password"})
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    assert client.get("/api/auth/me", headers=headers).status_code == 200

    # JWT `iat` is whole seconds, so a token minted in the same second as the
    # reset is indistinguishable from one minted just after it. Cross a second
    # boundary to test the real case: a session predating the reset.
    time.sleep(1.1)

    raw = pr.issue(test_db, user)
    client.post("/api/auth/reset-password", json={"token": raw, "new_password": "rotated-password"})

    assert client.get("/api/auth/me", headers=headers).status_code == 401, (
        "a token issued before the reset must no longer be accepted"
    )
