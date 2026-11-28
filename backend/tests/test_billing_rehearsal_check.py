"""Read-only probes use fixtures and do not touch the network."""
import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "billing_check", Path(__file__).resolve().parents[2] / "ops/check-billing-rehearsal.py")
check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check)
FILES = {"index.html": b"<html>fixture</html>", "assets/x.js": b"// fixture",
         "assets/x.css": b"body{}", "vite.svg": b"<svg/>"}
MANIFEST = {"api_base": check.PREFIX + "api", "entrypoint": "app.same_origin_sandbox",
            "source_revision": "a" * 40,
            "files": {"frontend/" + name: check.sha256(body).hexdigest() for name, body in FILES.items()}}
HOME = (200, {"content-type": "text/html"}, b"<html>ordinary app</html>")
JSON = (200, {"content-type": "application/json", "cache-control": "private, no-store"},
        b'{"status":"healthy","database":"ok"}')
P = check.PREFIX


def public_fixture(public, path):
    assert public
    if path == "/":
        return HOME
    if path == "/api/health":
        return JSON
    assert path.startswith(P)
    return 403, {}, b""


def loopback_fixture(public, path, host=check.HOST):
    assert not public
    if host != check.HOST or path == "/":
        return 404, {}, b""
    if path == check.HEALTH:
        return JSON
    name = path.removeprefix(P)
    if name in {"", "practice", "checkout/return", "checkout/cancel"}:
        name = "index.html"
    return 200, {"cache-control": "private, no-store",
                 "content-type": sorted(check.MIME[Path(name).suffix])[0]}, FILES[name]


def test_confirm_manifest_matched_loopback_and_anonymous_denial():
    check.check_public(MANIFEST, public_fixture)
    check.check_loopback(MANIFEST, loopback_fixture)


@pytest.mark.parametrize("path,response,error", [
    (P, HOME, "ordinary homepage fallback"),
    (check.HEALTH, JSON, "unexpectedly public"),
    (P + "assets/x.js", (302, {"location": "/"}, b""), "unexpected HTTP 302"),
    ("/api/health", HOME, "expected HTTP 200 JSON"),
])
def test_ordinary_fallback_or_public_exposure_fails(path, response, error):
    def fetch(public, uri):
        return response if uri == path else public_fixture(public, uri)
    with pytest.raises(check.CheckError, match=error):
        check.check_public(MANIFEST, fetch)


@pytest.mark.parametrize("path,mutation,error", [
    (P + "assets/x.js", lambda s, h, b: (s, h, b"// stale fixture"), "not the expected namespaced build"),
    (P + "checkout/return", lambda s, h, b: (s, dict(h, **{"set-cookie": "fake"}), b), "returned a cookie"),
    (P + "checkout/cancel", lambda s, h, b: (s, dict(h, **{"cache-control": "public, no-store"}), b), "missing private"),
    (check.HEALTH, lambda s, h, b: (s, h, b'{"status":"healthy","database":"unreachable"}'), "database not confirmed"),
    ("/", lambda s, h, b: HOME, "wrong Host"),
])
def test_loopback_must_match_artifact_and_stay_guarded(path, mutation, error):
    def fetch(public, uri, host=check.HOST):
        response = loopback_fixture(public, uri, host)
        return mutation(*response) if uri == path else response
    with pytest.raises(check.CheckError, match=error):
        check.check_loopback(MANIFEST, fetch)


def test_rejects_ordinary_bundle_before_network():
    def fetch(*args):
        pytest.fail("network not allowed without a valid manifest")
    with pytest.raises(check.CheckError, match="verified same-origin"):
        check.check_public(dict(MANIFEST, api_base="/api"), fetch)

    with pytest.raises(check.CheckError, match="required frontend digests"):
        check.check_loopback(dict(MANIFEST, files={}), fetch)
