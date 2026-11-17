"""Provider-free startup preflight tests: no actual database or app import."""
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from sqlalchemy.engine import make_url

from app import staging


@pytest.fixture
def settings():
    return SimpleNamespace(
        SITE_URL="https://rehearsal.example.test",
        STRIPE_TEST_RETURN_ORIGIN="https://rehearsal.example.test",
        STUDY_PASS_ENABLED=False, STRIPE_TEST_CHECKOUT_ENABLED=False,
        DAILY_GENERATION_ENABLED=False,
        DATABASE_URL="postgresql://synthetic:secret@stage-db:5432/rehearsal?connect_timeout=5",
    )


@pytest.fixture
def env():
    return {f"STAGING_EXPECTED_DB_{k}": v for k, v in dict(
        HOST="stage-db", PORT="5432", NAME="rehearsal", USER="synthetic").items()}


def test_valid_config_both_flags_off_or_on(settings, env):
    assert staging.validate_configuration(settings, env, make_url) == (
        "stage-db", 5432, "rehearsal", "synthetic")
    settings.STUDY_PASS_ENABLED = settings.STRIPE_TEST_CHECKOUT_ENABLED = True
    assert staging.validate_configuration(settings, env, make_url)


@pytest.mark.parametrize("origin", [
    "https://annababy.cc", "https://www.annababy.cc", "https://ANNABABY.CC.",
    "https://annababy。cc", "https://invalid_host.example", "https://-bad.example",
    "http://rehearsal.example.test", "https://rehearsal.example.test/path",
    "https://user:secret@rehearsal.example.test", "https://rehearsal.example.test?x=1",
    "https://rehearsal.example.test#x", "https://rehearsal.example.test:wrong",
])
def test_reject_origins(settings, env, origin):
    settings.SITE_URL = origin
    with pytest.raises(staging.StagingPreflightError):
        staging.validate_configuration(settings, env, make_url)


@pytest.mark.parametrize("change", ["flag", "scheduler", "provider", "pin", "url", "host_override", "timeout", "PGHOSTADDR", "PGOPTIONS", "PGSERVICE"])
def test_reject_unsafe_configuration(settings, env, change):
    if change.startswith("PG"): env[change] = "unapproved"
    if change == "flag": settings.STUDY_PASS_ENABLED = True
    if change == "scheduler": settings.DAILY_GENERATION_ENABLED = True
    if change == "provider": settings.OPENAI_API_KEY = "secret"
    if change == "pin": del env["STAGING_EXPECTED_DB_NAME"]
    if change == "url": env["DATABASE_URL"] = "postgresql://u:secret@production/prod"
    if change == "host_override": settings.DATABASE_URL += "&host=production"
    if change == "timeout": settings.DATABASE_URL = settings.DATABASE_URL.replace("timeout=5", "timeout=0")
    with pytest.raises(staging.StagingPreflightError):
        staging.validate_configuration(settings, env, make_url)


def binding():
    engine = Mock()
    engine.dialect.name = "postgresql"
    engine.url = make_url("postgresql://synthetic:secret@stage-db:5432/rehearsal?connect_timeout=5")
    from unittest.mock import MagicMock
    connection = MagicMock()
    engine.connect.return_value = connection
    connection.__enter__.return_value.execute.return_value.one.return_value = ("rehearsal", "synthetic")
    return SimpleNamespace(engine=engine, SessionLocal=SimpleNamespace(kw={"bind": engine})), connection


@pytest.mark.parametrize("bad", [None, "sqlite", "session", "identity", "connection"])
def test_bound_engine_before_application(bad):
    db, connection = binding()
    if bad == "sqlite": db.engine.dialect.name = "sqlite"
    if bad == "session": db.SessionLocal.kw["bind"] = object()
    if bad == "identity": connection.__enter__.return_value.execute.return_value.one.return_value = ("prod", "synthetic")
    if bad == "connection": db.engine.connect.side_effect = RuntimeError("do not leak secret DSN")
    if bad:
        with pytest.raises(staging.StagingPreflightError) as error:
            staging.validate_binding(db, ("stage-db", 5432, "rehearsal", "synthetic"), lambda s: s)
        assert "secret" not in str(error.value)
    else:
        staging.validate_binding(db, ("stage-db", 5432, "rehearsal", "synthetic"), lambda s: s)
        assert connection.__enter__.return_value.execute.call_args_list[0].args == ("SET TRANSACTION READ ONLY",)
        connection.__exit__.assert_called_once()


@pytest.mark.parametrize("mode", ["ok", "sqlite", "config", "preimported", "database_preimported", "main_error"])
def test_factory_in_fresh_process(mode, tmp_path):
    """Fake imports prove ordering and prevent any driver/provider network calls."""
    backend = Path(__file__).resolve().parents[1]
    script = r'''
import sys, os
from types import SimpleNamespace as NS
from unittest.mock import MagicMock
from sqlalchemy.engine import make_url
from app import staging
mode = sys.argv[1]
s = NS(SITE_URL="https://rehearsal.example.test", STRIPE_TEST_RETURN_ORIGIN="https://rehearsal.example.test",
       STUDY_PASS_ENABLED=False, STRIPE_TEST_CHECKOUT_ENABLED=False, DAILY_GENERATION_ENABLED=False,
       DATABASE_URL="postgresql://synthetic:secret@stage-db:5432/rehearsal?connect_timeout=5")
os.environ.update({"STAGING_EXPECTED_DB_HOST":"stage-db", "STAGING_EXPECTED_DB_PORT":"5432",
                   "STAGING_EXPECTED_DB_NAME":"rehearsal", "STAGING_EXPECTED_DB_USER":"synthetic"})
e = MagicMock()
e.url = make_url(s.DATABASE_URL)
e.dialect.name = "sqlite" if mode == "sqlite" else "postgresql"
e.connect.return_value.__enter__.return_value.execute.return_value.one.return_value = ("rehearsal", "synthetic")
db = NS(engine=e, SessionLocal=NS(kw={"bind":e}))
seen = []
def load(name):
    seen.append(name)
    if name == "app.config":
        if mode == "config": raise ValueError("secret_config_payload")
        return NS(settings=s)
    if name == "sqlalchemy": return NS(text=lambda x: x)
    if name == "sqlalchemy.engine": return NS(make_url=make_url)
    if name == "app.database": return db
    if name == "app.main":
        assert e.connect.return_value.__exit__.called
        if mode == "main_error": raise ValueError("secret_schema_DSN")
        return NS(app="guarded-app")
    raise AssertionError(name)
staging.importlib.import_module = load
if mode == "preimported": sys.modules["app.main"] = NS()
if mode == "database_preimported": sys.modules["app.database"] = NS()
try:
    assert staging.create_app() == "guarded-app"
    assert mode == "ok"
    print("passed")
except staging.StagingPreflightError as error:
    assert mode != "ok"
    assert "secret" not in str(error)
    if mode != "main_error": assert "app.main" not in seen
    if mode in {"config", "preimported", "database_preimported"}: assert "app.database" not in seen
    print("rejected safely")
'''
    clean_env = {k: v for k, v in os.environ.items() if not k.startswith("PG") and k not in {
        "DATABASE_URL", "OPENAI_API_KEY", "RESEND_API_KEY", "AZURE_SPEECH_KEY", "GOOGLE_APPLICATION_CREDENTIALS"}}
    clean_env["PYTHONPATH"] = str(backend)
    result = subprocess.run([sys.executable, "-c", script, mode], cwd=tmp_path,
                            env=clean_env, capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
    assert "secret" not in result.stdout + result.stderr
