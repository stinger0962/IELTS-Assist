"""Explicit local-only Stripe sandbox launcher; no hosted guard changes.

Supported entry point: python -m app.local_sandbox (no options).
Requires an operator-confirmed disposable local PostgreSQL database and role,
not a production copy. Does not install software or create credentials/data.
"""
import importlib
import os
from pathlib import Path
import re
import sys

from app.staging import StagingPreflightError, _load_fixture_app, _safe_query, validate_binding

UI_ORIGIN = "http://127.0.0.1:5173"
API_HOST = "127.0.0.1"
API_PORT = 8001
DB_TARGET = ("127.0.0.1", 5432, "ielts_sandbox", "ielts_sandbox")
PROVIDER_KEYS = ("OPENAI_API_KEY", "AZURE_SPEECH_KEY", "RESEND_API_KEY", "GOOGLE_APPLICATION_CREDENTIALS")


def validate_local_configuration(settings, environ, make_url):
    """No imports of app.database/app.main and no network or mutation."""
    if settings.SITE_URL != UI_ORIGIN or settings.STRIPE_TEST_RETURN_ORIGIN != UI_ORIGIN:
        raise StagingPreflightError("Local sandbox requires the fixed numeric loopback UI origin")
    if (type(settings.STUDY_PASS_ENABLED) is not bool
            or type(settings.STRIPE_TEST_CHECKOUT_ENABLED) is not bool
            or settings.STUDY_PASS_ENABLED != settings.STRIPE_TEST_CHECKOUT_ENABLED):
        raise StagingPreflightError("Local sandbox checkout flags must agree")
    if settings.DAILY_GENERATION_ENABLED is not False:
        raise StagingPreflightError("Local sandbox scheduled generation must be disabled")
    if any(getattr(settings, key, "") or environ.get(key) for key in PROVIDER_KEYS):
        raise StagingPreflightError("Local sandbox must not contain unrelated provider credentials")
    if any(key.startswith("PG") and value for key, value in environ.items()):
        raise StagingPreflightError("Local sandbox must not inherit libpq overrides")
    # Only the approved smoke offer is supported. The adapter still verifies the
    # actual account, catalog and settled payment before granting any access.
    for key, prefix in (("STRIPE_TEST_SECRET_KEY", "sk_test_"),
                        ("STRIPE_TEST_WEBHOOK_SECRET", "whsec_"),
                        ("STRIPE_TEST_ACCOUNT_ID", "acct_"),
                        ("STRIPE_TEST_PRICE_ID", "price_")):
        value = getattr(settings, key, "")
        if (settings.STUDY_PASS_ENABLED or value) and not re.fullmatch(prefix + r"[A-Za-z0-9_]+", value):
            raise StagingPreflightError("Local sandbox requires explicit test-only Stripe configuration")
    if settings.STUDY_PASS_ENABLED and (
            settings.STRIPE_TEST_AMOUNT_MINOR != 1900 or settings.STRIPE_TEST_CURRENCY != "USD"
            or settings.STRIPE_TEST_WRITING_REVIEWS != 5 or not settings.STRIPE_TEST_OFFER_SKU):
        raise StagingPreflightError("Local sandbox requires the USD19 five-review smoke offer")
    try:
        # Demand an explicit URL rather than default/fallback config.
        url = make_url(environ["DATABASE_URL"])
        actual = (url.host, url.port or 5432, url.database, url.username)
        valid = (url.get_backend_name() == "postgresql" and _safe_query(url.query)
                 and actual == DB_TARGET and bool(url.password))
    except Exception:
        valid = False
    if not valid:
        raise StagingPreflightError("Local sandbox requires the dedicated loopback PostgreSQL database and role")
    return DB_TARGET


def _create_local_app():
    # Pydantic's Settings reads .env from cwd at import. Refuse before that import;
    # never read dotenv contents or let an accidental production file influence us.
    if (Path.cwd() / ".env").exists() or (Path.cwd() / ".env").is_symlink():
        raise StagingPreflightError("Run local sandbox from a directory without a dotenv file")
    if any(name in sys.modules for name in ("app.config", "app.database", "app.main")):
        raise StagingPreflightError("Local sandbox must start in a fresh process before app configuration")
    try:
        config = importlib.import_module("app.config")
        if not os.environ.get("SECRET_KEY"):
            raise StagingPreflightError("Local sandbox requires an explicitly supplied signing key")
        config.assert_secret_key_is_safe(config.settings.SECRET_KEY)
        sqlalchemy = importlib.import_module("sqlalchemy")
        make_url = importlib.import_module("sqlalchemy.engine").make_url
        target = validate_local_configuration(config.settings, os.environ, make_url)
        database = importlib.import_module("app.database")
        validate_binding(database, target, sqlalchemy.text)
        return _load_fixture_app()
    except StagingPreflightError:
        raise
    except Exception:
        raise StagingPreflightError("Local sandbox initialization failed") from None


def main():
    if len(sys.argv) != 1:
        raise StagingPreflightError("Local sandbox launcher accepts no bind or runtime overrides")
    app = _create_local_app()
    uvicorn = importlib.import_module("uvicorn")
    uvicorn.run(app, host=API_HOST, port=API_PORT, proxy_headers=False,
                workers=1, reload=False)


if __name__ == "__main__":
    main()
