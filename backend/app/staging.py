"""Opt-in sandbox ASGI factory. Never imported by the production entry point.

Run only in an approved disposable environment: uvicorn app.staging:create_app
--factory. Configuration/identity checks run in each serving process *before*
importing app.main, which initializes schema at import time. This guard cannot
prove infrastructure ownership; the operator must first verify its isolation.
"""
import importlib
import os
import re
import sys
from urllib.parse import urlsplit


class StagingPreflightError(RuntimeError):
    """A fixed, non-secret diagnostic suitable for startup logs."""


def _origin(value):
    try:
        parsed = urlsplit(value)
        host = (parsed.hostname or "").lower().rstrip(".")
        valid = (
            isinstance(value, str) and not any(c.isspace() for c in value)
            and parsed.scheme == "https" and host and "." in host
            and len(host) <= 253
            and all(re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label)
                    for label in host.split("."))
            and host != "annababy.cc" and not host.endswith(".annababy.cc")
            and parsed.username is None and parsed.password is None
            and parsed.path in ("", "/") and not parsed.query and not parsed.fragment
            and parsed.port in (None, 443)
        )
    except (ValueError, TypeError):
        valid = False
    if not valid:
        raise StagingPreflightError("Staging requires a non-production HTTPS origin")
    return f"https://{host}"


def _safe_query(query):
    # Reject libpq routing overrides (host/service/options) even when the URL's
    # visible host matches. Permit bounded connection time and explicit TLS.
    try:
        return (set(query) <= {"connect_timeout", "sslmode"}
                and isinstance(query.get("connect_timeout"), str)
                and 1 <= int(query["connect_timeout"]) <= 15
                and query.get("sslmode", "prefer") in {
                    "disable", "allow", "prefer", "require", "verify-ca", "verify-full"})
    except (TypeError, ValueError):
        return False


def validate_configuration(settings, environ, make_url):
    """Pure checks before database module import or any connection attempt."""
    site = _origin(settings.SITE_URL)
    if site != _origin(settings.STRIPE_TEST_RETURN_ORIGIN):
        raise StagingPreflightError("Staging origins must match")
    if settings.STUDY_PASS_ENABLED != settings.STRIPE_TEST_CHECKOUT_ENABLED:
        raise StagingPreflightError("Staging checkout flags must agree")
    if settings.DAILY_GENERATION_ENABLED:
        raise StagingPreflightError("Staging scheduled generation must be disabled")
    for key in ("OPENAI_API_KEY", "AZURE_SPEECH_KEY", "RESEND_API_KEY",
                "GOOGLE_APPLICATION_CREDENTIALS"):
        if getattr(settings, key, "") or environ.get(key):
            raise StagingPreflightError("Staging must not include unrelated provider credentials")
    if any(key.startswith("PG") and value for key, value in environ.items()):
        raise StagingPreflightError("Staging must not inherit libpq environment overrides")
    expected = tuple(environ.get(f"STAGING_EXPECTED_DB_{key}", "")
                     for key in ("HOST", "PORT", "NAME", "USER"))
    if any(not value or value.strip() != value for value in expected):
        raise StagingPreflightError("Staging database identity must be explicitly pinned")
    try:
        port = int(expected[1])
        if not 1 <= port <= 65535:
            raise ValueError
        url = make_url(environ.get("DATABASE_URL", settings.DATABASE_URL))
        actual = (url.host, url.port or 5432, url.database, url.username)
        target = (expected[0], port, expected[2], expected[3])
        valid = url.get_backend_name() == "postgresql" and _safe_query(url.query) and actual == target
    except Exception:
        valid = False
    if not valid:
        raise StagingPreflightError("Staging database URL does not match pinned PostgreSQL identity")
    return target


def validate_binding(database, target, text):
    """Inspect exactly the engine/session binding the serving app will reuse."""
    engine = database.engine
    try:
        url = engine.url
        valid = (
            engine.dialect.name == "postgresql" and _safe_query(url.query)
            and (url.host, url.port or 5432, url.database, url.username) == target
            and database.SessionLocal.kw.get("bind") is engine
        )
        if not valid:
            raise StagingPreflightError("Staging active database binding does not match")
        with engine.connect() as conn:
            # Explicitly read-only; do not seed, initialize schema or commit.
            conn.execute(text("SET TRANSACTION READ ONLY"))
            actual = tuple(conn.execute(text("SELECT current_database(), current_user")).one())
            if actual != target[2:]:
                raise StagingPreflightError("Staging connected database identity does not match")
    except StagingPreflightError:
        raise
    except Exception:
        raise StagingPreflightError("Staging database verification failed") from None


def create_app():
    """Uvicorn factory; checks rerun on every flags-on/off process restart."""
    if "app.main" in sys.modules or "app.database" in sys.modules:
        raise StagingPreflightError("Staging must start before the application is imported")
    try:
        settings = importlib.import_module("app.config").settings
        sqlalchemy = importlib.import_module("sqlalchemy")
        make_url = importlib.import_module("sqlalchemy.engine").make_url
        target = validate_configuration(settings, os.environ, make_url)
        database = importlib.import_module("app.database")
        validate_binding(database, target, sqlalchemy.text)
    except StagingPreflightError:
        raise
    except Exception:
        # Pydantic and driver exceptions may contain credential-bearing input.
        raise StagingPreflightError("Staging configuration or database initialization failed") from None
    try:
        return importlib.import_module("app.main").app
    except Exception:
        raise StagingPreflightError("Staging application initialization failed") from None
