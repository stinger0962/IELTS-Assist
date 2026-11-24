"""Explicit, loopback-only same-host checkout rehearsal; not the production service."""
import importlib
import os
from pathlib import Path
import re
import sys

from app.same_origin_route import HOST, ORIGIN, PREFIX
from app.staging import StagingPreflightError, _load_fixture_app, _safe_query, validate_binding

API_HOST = "127.0.0.1"
API_PORT = 8011
DB_TARGET = ("127.0.0.1", 55432, "ielts_billing_test", "ielts_billing_test")
WEBHOOK = "/api/checkout/webhook"
CSP = (
    "default-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'; "
    f"script-src {ORIGIN}{PREFIX}/; connect-src {ORIGIN}{PREFIX}/; "
    f"style-src {ORIGIN}{PREFIX}/ 'unsafe-inline'; font-src {ORIGIN}{PREFIX}/; "
    f"img-src {ORIGIN}{PREFIX}/ data:; media-src {ORIGIN}{PREFIX}/ blob:"
).encode()
UUID = r"[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}"
PAGES = {"", "/", "/login", "/practice", "/checkout/return", "/checkout/cancel"}
GET_API = {"/api/health", "/api/auth/me", "/api/study-pass",
           "/api/checkout/offer", "/api/generate/recent-exams", "/api/generate/pool-status"} | {
               f"/api/generate/daily-{skill}" for skill in ("reading", "listening", "grammar", "writing", "speaking")}
POST_API = {"/api/auth/login", "/api/checkout/orders", WEBHOOK, "/api/generate/trigger-replenish",
            "/api/generate/submit-ai-reading-exam", "/api/generate/submit-ai-listening-exam"}
NO_PROVIDER = ("OPENAI_API_KEY", "AZURE_SPEECH_KEY", "GOOGLE_APPLICATION_CREDENTIALS", "RESEND_API_KEY")


def _validate(settings, env, make_url):
    if settings.SITE_URL != ORIGIN or settings.STRIPE_TEST_RETURN_ORIGIN != ORIGIN or settings.API_PREFIX != "/api":
        raise StagingPreflightError("Same-host sandbox requires the fixed HTTPS origin and API path")
    if "SITE_URL" not in env or len(env.get("SECRET_KEY", "")) < 32:
        raise StagingPreflightError("Same-host sandbox needs explicit site and disposable signing settings")
    if settings.STUDY_PASS_ENABLED != settings.STRIPE_TEST_CHECKOUT_ENABLED or settings.DAILY_GENERATION_ENABLED:
        raise StagingPreflightError("Same-host sandbox flags are not isolated")
    if any(getattr(settings, field, "") or env.get(field) for field in NO_PROVIDER):
        raise StagingPreflightError("Same-host sandbox must not include unrelated provider credentials")
    if any(key.startswith("PG") and value for key, value in env.items()):
        raise StagingPreflightError("Same-host sandbox must not inherit libpq overrides")
    try:
        url = make_url(env["DATABASE_URL"])
        actual = (url.host, url.port or 5432, url.database, url.username)
        db_ok = (actual == DB_TARGET and url.get_backend_name() == "postgresql"
                 and bool(url.password) and _safe_query(url.query))
    except Exception:
        db_ok = False
    if not db_ok:
        raise StagingPreflightError("Same-host sandbox requires its dedicated loopback database and role")
    keys = (("STRIPE_TEST_SECRET_KEY", "sk_test_"), ("STRIPE_TEST_WEBHOOK_SECRET", "whsec_"),
            ("STRIPE_TEST_ACCOUNT_ID", "acct_"), ("STRIPE_TEST_PRICE_ID", "price_"))
    for field, prefix in keys:
        value = getattr(settings, field, "")
        if (settings.STUDY_PASS_ENABLED or value) and not re.fullmatch(prefix + r"[A-Za-z0-9_]+", value):
            raise StagingPreflightError("Same-host sandbox requires test-only Stripe settings")
    if settings.STUDY_PASS_ENABLED and (settings.STRIPE_TEST_AMOUNT_MINOR != 1900
            or settings.STRIPE_TEST_CURRENCY != "USD" or settings.STRIPE_TEST_WRITING_REVIEWS != 5
            or not settings.STRIPE_TEST_OFFER_SKU):
        raise StagingPreflightError("Same-host sandbox requires the fixed USD19 test offer")


def _build_app(api, dist):
    from starlette.applications import Starlette
    from starlette.responses import FileResponse, Response
    from starlette.routing import Mount, Route
    from starlette.staticfiles import StaticFiles

    async def page(request):
        return FileResponse(dist / "index.html", headers={"Cache-Control": "private, no-store"})

    async def icon(request):
        return FileResponse(dist / "vite.svg")

    routes = [Route(PREFIX + page_path, page) for page_path in sorted(PAGES)]
    routes += [Route(PREFIX + "/vite.svg", icon), Mount(PREFIX + "/assets", app=StaticFiles(directory=dist / "assets"))]
    if (dist / "audio").is_dir():
        routes.append(Mount(PREFIX + "/audio", app=StaticFiles(directory=dist / "audio")))
    router = Starlette(routes=[*routes, Mount(PREFIX, api)])

    async def edge(scope, receive, send):
        if scope["type"] == "websocket":
            return await send({"type": "websocket.close", "code": 1008})
        if scope["type"] != "http":
            return await router(scope, receive, send)
        path = scope["path"]
        off = path[len(PREFIX):] if path.startswith(PREFIX + "/") or path == PREFIX else None
        method = scope["method"]
        headers = scope.get("headers", [])
        hosts = [value for key, value in headers if key == b"host"]
        public_webhook = off == WEBHOOK and method == "POST"
        static = off and re.fullmatch(r"/(?:assets|audio)/(?:[A-Za-z0-9_-]+/)*[A-Za-z0-9_-][A-Za-z0-9_.-]*", off)
        can_read = (off in GET_API or off in PAGES or off == "/vite.svg" or static
                    or (off and re.fullmatch(r"/api/checkout/orders/" + UUID, off)))
        # Uvicorn gives the raw path; older Starlette's test adapter includes the query.
        raw = scope.get("raw_path", b"").split(b"?", 1)[0]
        allowed = (off is not None and hosts == [HOST.encode()]
                   and raw == path.encode()
                   and (not public_webhook or not scope.get("query_string"))
                   and ((method in {"GET", "HEAD"} and can_read) or (method == "POST" and off in POST_API)))
        if not allowed or (method == "POST" and not public_webhook
                           and [v for k, v in headers if k == b"origin"] != [ORIGIN.encode()]):
            return await Response(status_code=404)(scope, receive, send)
        # Origin-wide browser cookies are never test credentials or passed to the inner app.
        trusted = dict(scope, headers=[(k, v) for k, v in headers if k not in {b"cookie", b"x-xsrf-token"}])

        async def no_store(message):
            if message["type"] == "http.response.start":
                message = dict(message)
                message["headers"] = [(k, v) for k, v in message.get("headers", [])
                                      if k not in {b"set-cookie", b"cache-control"}]
                message["headers"] += [(b"cache-control", b"private, no-store"),
                                       (b"referrer-policy", b"strict-origin"),
                                       (b"content-security-policy", CSP),
                                       (b"x-content-type-options", b"nosniff"),
                                       (b"x-frame-options", b"DENY")]
            await send(message)

        await router(trusted, receive, no_store)

    return edge


def _create_app():
    """Validate the dedicated binding before importing the schema-initializing app."""
    if Path(".env").exists() or Path(".env").is_symlink():
        raise StagingPreflightError("Same-host sandbox requires a fresh directory without dotenv")
    if any(name in sys.modules for name in ("app.config", "app.database", "app.main")):
        raise StagingPreflightError("Same-host sandbox must initialize in a fresh process")
    try:
        config = importlib.import_module("app.config")
        config.assert_secret_key_is_safe(config.settings.SECRET_KEY)
        sqlalchemy = importlib.import_module("sqlalchemy")
        _validate(config.settings, os.environ, importlib.import_module("sqlalchemy.engine").make_url)
        dist = Path(os.environ["IELTS_BILLING_TEST_DIST"])
        if not dist.is_absolute() or ('src="' + PREFIX + '/assets/') not in (dist / "index.html").read_text():
            raise StagingPreflightError("Same-host sandbox requires the dedicated prefixed build")
        config.settings.TTS_AUDIO_DIR = str(dist / "audio")
        db = importlib.import_module("app.database")
        validate_binding(db, DB_TARGET, sqlalchemy.text)
        api = _load_fixture_app()
        api.state.same_origin_rehearsal = True
        return _build_app(api, dist)
    except StagingPreflightError:
        raise
    except Exception:
        raise StagingPreflightError("Same-host sandbox initialization failed") from None


def main():
    if len(sys.argv) != 1:
        raise StagingPreflightError("Same-host sandbox accepts no bind or runtime overrides")
    app = _create_app()
    import uvicorn
    uvicorn.run(app, host=API_HOST, port=API_PORT, proxy_headers=False, access_log=False)


if __name__ == "__main__":
    main()
