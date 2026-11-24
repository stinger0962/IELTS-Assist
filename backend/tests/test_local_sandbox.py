"""Local sandbox guard: configuration and fake startup only, never Stripe/DB IO."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from types import SimpleNamespace

import pytest
from sqlalchemy.engine import make_url
from app import local_sandbox as local
from app.staging import StagingPreflightError, _origin


@pytest.fixture
def settings():
    return SimpleNamespace(SITE_URL=local.UI_ORIGIN, STRIPE_TEST_RETURN_ORIGIN=local.UI_ORIGIN,
        STUDY_PASS_ENABLED=True, STRIPE_TEST_CHECKOUT_ENABLED=True, DAILY_GENERATION_ENABLED=False,
        STRIPE_TEST_SECRET_KEY="sk_test_fixture", STRIPE_TEST_WEBHOOK_SECRET="whsec_fixture",
        STRIPE_TEST_ACCOUNT_ID="acct_fixture", STRIPE_TEST_PRICE_ID="price_fixture",
        STRIPE_TEST_AMOUNT_MINOR=1900, STRIPE_TEST_CURRENCY="USD", STRIPE_TEST_WRITING_REVIEWS=5,
        STRIPE_TEST_OFFER_SKU="fixture-pass")


@pytest.fixture
def env():
    return {"DATABASE_URL": "postgresql://ielts_sandbox:fixture@127.0.0.1:5432/ielts_sandbox?connect_timeout=5"}


def test_valid_local_and_hosted_stays_strict(settings, env):
    assert local.validate_local_configuration(settings, env, make_url) == local.DB_TARGET
    with pytest.raises(StagingPreflightError):
        _origin(local.UI_ORIGIN)
    settings.STUDY_PASS_ENABLED = settings.STRIPE_TEST_CHECKOUT_ENABLED = False
    assert local.validate_local_configuration(settings, env, make_url) == local.DB_TARGET


@pytest.mark.parametrize("value", ["http://localhost:5173", "http://127.0.0.1:5174", "http://0.0.0.0:5173",
    "http://[::1]:5173", "http://127.0.0.1:5173/", "https://annababy.cc", "http://127.0.0.1.evil.test:5173"])
def test_reject_noncanonical_origins(settings, env, value):
    settings.SITE_URL = settings.STRIPE_TEST_RETURN_ORIGIN = value
    with pytest.raises(StagingPreflightError):
        local.validate_local_configuration(settings, env, make_url)


@pytest.mark.parametrize("field,value", [("STRIPE_TEST_SECRET_KEY", "sk_live_fixture"),
    ("STRIPE_TEST_ACCOUNT_ID", "wrong"), ("STRIPE_TEST_WEBHOOK_SECRET", ""),
    ("STRIPE_TEST_PRICE_ID", "prod_fixture"), ("DAILY_GENERATION_ENABLED", True),
    ("STUDY_PASS_ENABLED", False), ("STRIPE_TEST_AMOUNT_MINOR", 2000),
    ("STRIPE_TEST_CURRENCY", "EUR"), ("STRIPE_TEST_WRITING_REVIEWS", 4),
    ("OPENAI_API_KEY", "fixture"), ("RESEND_API_KEY", "fixture")])
def test_reject_other_configuration(settings, env, field, value):
    setattr(settings, field, value)
    with pytest.raises(StagingPreflightError):
        local.validate_local_configuration(settings, env, make_url)


@pytest.mark.parametrize("url", ["sqlite:///:memory:",
    "postgresql://postgres:fixture@127.0.0.1/ielts_sandbox?connect_timeout=5",
    "postgresql://ielts_sandbox:fixture@127.0.0.1/ielts_assist?connect_timeout=5",
    "postgresql://ielts_sandbox:fixture@localhost/ielts_sandbox?connect_timeout=5",
    "postgresql://ielts_sandbox:fixture@127.0.0.1:5433/ielts_sandbox?connect_timeout=5",
    "postgresql://ielts_sandbox:fixture@remote.invalid/ielts_sandbox?connect_timeout=5",
    "postgresql://ielts_sandbox:fixture@127.0.0.1/ielts_sandbox?host=remote.invalid&connect_timeout=5",
    "postgresql://ielts_sandbox@127.0.0.1/ielts_sandbox?connect_timeout=5"])
def test_reject_wrong_database(settings, env, url):
    env["DATABASE_URL"] = url
    with pytest.raises(StagingPreflightError):
        local.validate_local_configuration(settings, env, make_url)


def test_reject_ambient_pg_overrides(settings, env):
    env["PGHOSTADDR"] = "192.0.2.1"
    with pytest.raises(StagingPreflightError):
        local.validate_local_configuration(settings, env, make_url)


@pytest.mark.parametrize("mode", ["ok", "dotenv", "loaded", "sqlite", "wrong_identity", "connect_error", "args"])
def test_fresh_process_startup_is_local_and_guarded(mode, tmp_path):
    backend = Path(__file__).resolve().parents[1]
    script = r'''
import sys, os
from types import SimpleNamespace as NS
from unittest.mock import MagicMock
from sqlalchemy.engine import make_url
from app import local_sandbox as local
mode = sys.argv.pop()
sys.argv = ["local_sandbox"] + (["--host", "0.0.0.0"] if mode == "args" else [])
s = NS(SITE_URL=local.UI_ORIGIN, STRIPE_TEST_RETURN_ORIGIN=local.UI_ORIGIN,
    STUDY_PASS_ENABLED=False, STRIPE_TEST_CHECKOUT_ENABLED=False, DAILY_GENERATION_ENABLED=False,
    SECRET_KEY="local-fixture")
os.environ["SECRET_KEY"] = "local-fixture"
os.environ["DATABASE_URL"] = "postgresql://ielts_sandbox:fixture@127.0.0.1:5432/ielts_sandbox?connect_timeout=5"
e = MagicMock(); e.url = make_url(os.environ["DATABASE_URL"])
e.dialect.name = "sqlite" if mode == "sqlite" else "postgresql"
e.connect.return_value.__enter__.return_value.execute.return_value.one.return_value = (
    ("wrong_db", "ielts_sandbox") if mode == "wrong_identity" else ("ielts_sandbox", "ielts_sandbox"))
if mode == "connect_error": e.connect.side_effect = ValueError("credential-bearing-secret")
seen = []
def load(name):
    seen.append(name)
    if name == "app.config": return NS(settings=s, assert_secret_key_is_safe=lambda k: None)
    if name == "sqlalchemy": return NS(text=lambda s: s)
    if name == "sqlalchemy.engine": return NS(make_url=make_url)
    if name == "app.database": return NS(engine=e, SessionLocal=NS(kw={"bind":e}))
    if name == "app.main":
        assert e.connect.return_value.__exit__.called
        return NS(app=NS(state=NS()))
    if name == "uvicorn":
        def run(app, **kw):
            assert app.state.practice_auto_replenishment_enabled is False
            print("guarded", kw)
        return NS(run=run)
    raise AssertionError(name)
local.importlib.import_module = load
if mode == "dotenv": open(".env", "w").write("DATABASE_URL=credential-bearing-secret")
if mode == "loaded": sys.modules["app.config"] = NS()
try:
    local.main()
    assert mode == "ok"
except local.StagingPreflightError as error:
    assert mode != "ok"
    assert "credential-bearing-secret" not in str(error)
    assert "app.main" not in seen
    if mode in {"dotenv", "loaded", "args"}: assert not seen
    print("rejected safely")
'''
    clean = {k: v for k, v in os.environ.items() if not k.startswith("PG") and k not in local.PROVIDER_KEYS}
    clean["PYTHONPATH"] = str(backend)
    result = subprocess.run([sys.executable, "-c", script, mode], cwd=tmp_path, env=clean,
                            capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
    assert "credential-bearing-secret" not in result.stdout + result.stderr
    if mode == "ok":
        assert "'host': '127.0.0.1'" in result.stdout
        assert "'port': 8001" in result.stdout and "'reload': False" in result.stdout


@pytest.mark.skipif(not shutil.which("node"), reason="Frontend launcher requires Node.js")
def test_frontend_launcher_fixed_proxy_without_dotenv(tmp_path):
    launcher = Path(__file__).resolve().parents[2] / "frontend/scripts/local-sandbox.mjs"
    script = f'''
import assert from 'node:assert/strict';
import {{ startLocal, localOptions }} from {json.dumps(launcher.as_uri())};
let listened = 0, created = 0;
const deps = {{ react: () => ({{}}), createServer: async options => {{
  created++;
  assert.equal(options.configFile, false); assert.equal(options.envDir, false);
  assert.deepEqual(options.envPrefix, []);
  assert.equal(options.server.host, '127.0.0.1'); assert.equal(options.server.port, 5173);
  assert.equal(options.server.strictPort, true);
  assert.equal(options.server.proxy['/api'].target, 'http://127.0.0.1:8001');
  assert.equal(options.define['import.meta.env.VITE_API_URL'], '"/api"');
  return {{listen: async () => {{listened++;}}}};
}} }};
await startLocal(deps, []); assert.equal(listened, 1);
await assert.rejects(startLocal(deps, ['--host=0.0.0.0'])); assert.equal(created, 1);
'''
    result = subprocess.run(["node", "--input-type=module", "-e", script], cwd=tmp_path,
                            capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
