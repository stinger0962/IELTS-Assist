"""Edge/launcher regressions: no proxy, production data or external Stripe traffic."""
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi import Request
from fastapi.testclient import TestClient
from sqlalchemy.engine import make_url

from app.config import settings
from app.main import app
from app.routers import checkout
from app.same_origin_route import ORIGIN, PREFIX
from app.same_origin_sandbox import _build_app, _validate
from app.services.checkout import CheckoutSession, GatewayScope
from app.staging import StagingPreflightError
from tests.test_stripe_precreated_price import PRICE_ID


def configuration():
    return SimpleNamespace(SITE_URL=ORIGIN, STRIPE_TEST_RETURN_ORIGIN=ORIGIN, API_PREFIX="/api",
                           STUDY_PASS_ENABLED=False, STRIPE_TEST_CHECKOUT_ENABLED=False,
                           DAILY_GENERATION_ENABLED=False), {
        "SITE_URL": ORIGIN, "SECRET_KEY": "x" * 32,
        "DATABASE_URL": "postgresql://ielts_billing_test:fixture@127.0.0.1:55432/ielts_billing_test?connect_timeout=5",
    }


@pytest.mark.parametrize("bad", [None, "sqlite", "prod", "pg_env", "provider", "origin", "key", "flags", "tick", "api", "live"])
def test_preflight_never_accepts_unisolated_runtime(bad):
    config, env = configuration()
    if bad == "sqlite":
        env["DATABASE_URL"] = "sqlite:///test.db"
    if bad == "prod":
        env["DATABASE_URL"] = "postgresql://postgres:fixture@127.0.0.1:5432/ielts_assist?connect_timeout=5"
    if bad == "pg_env":
        env["PGHOSTADDR"] = "127.0.0.1"
    if bad == "provider":
        env["OPENAI_API_KEY"] = "fixture"
    if bad == "origin":
        config.SITE_URL += "/"
    if bad == "key":
        env.pop("SECRET_KEY")
    if bad == "flags":
        config.STUDY_PASS_ENABLED = True
    if bad == "tick":
        config.DAILY_GENERATION_ENABLED = True
    if bad == "api":
        config.API_PREFIX = "/other"
    if bad == "live":
        config.STRIPE_TEST_SECRET_KEY = "sk_live_fixture"
    if bad:
        with pytest.raises(StagingPreflightError):
            _validate(config, env, make_url)
    else:
        assert _validate(config, env, make_url) is None


@pytest.fixture
def flags(monkeypatch):
    for k, v in {
        "STRIPE_TEST_RETURN_ORIGIN": ORIGIN, "STUDY_PASS_ENABLED": True,
        "STRIPE_TEST_CHECKOUT_ENABLED": True, "STRIPE_TEST_SECRET_KEY": "sk_test_fixture",
        "STRIPE_TEST_WEBHOOK_SECRET": "whsec_fixture", "STRIPE_TEST_ACCOUNT_ID": "acct_fixture",
        "STRIPE_TEST_OFFER_SKU": "fixture", "STRIPE_TEST_AMOUNT_MINOR": 1900,
        "STRIPE_TEST_CURRENCY": "USD", "STRIPE_TEST_WRITING_REVIEWS": 5, "STRIPE_TEST_PRICE_ID": PRICE_ID,
    }.items():
        monkeypatch.setattr(settings, k, v)


def test_normal_app_does_not_accept_production_host_even_with_flags(client, auth_token, flags, monkeypatch):
    factory = Mock()
    monkeypatch.setattr(checkout, "_adapter_factory", factory)
    headers = {"Authorization": f"Bearer {auth_token}", "Host": "annababy.cc", "Origin": ORIGIN, "X-Forwarded-Prefix": PREFIX}
    assert client.get("/api/checkout/offer", headers=headers).json()["enabled"] is False
    assert client.post("/api/checkout/webhook", headers=headers).status_code == 503
    factory.assert_not_called()


def test_fixed_router_only_allows_namespaced_surface(client, auth_token, flags, monkeypatch, tmp_path):
    monkeypatch.setattr(app, "state", type(app.state)())
    app.state.same_origin_rehearsal = True
    tmp_path.joinpath("assets").mkdir()
    tmp_path.joinpath("assets", "index.js").write_text("// fixture")
    tmp_path.joinpath("index.html").write_text("fixture page")
    adapter = Mock(scope=GatewayScope("stripe", "acct_fixture", "test"),
                   verify=Mock(side_effect=ValueError("fixture invalid signature")))
    factory = Mock(return_value=adapter)
    monkeypatch.setattr(checkout, "_adapter_factory", factory)
    auth = {"Authorization": f"Bearer {auth_token}"}
    with TestClient(_build_app(app, tmp_path), base_url=ORIGIN) as edge:
        for path in ("", "/", "/login", "/practice", "/checkout/return?order_id=synthetic", "/assets/index.js"):
            page = edge.get(PREFIX + path)
            assert page.status_code == 200, path
            assert page.headers["cache-control"] == "private, no-store"
        offer = edge.get(PREFIX + "/api/checkout/offer", headers={**auth, "Cookie": "production=secret"})
        assert offer.status_code == 200 and offer.json()["enabled"] is True
        args = factory.call_args.kwargs
        assert args["success_url"] == ORIGIN + PREFIX + "/checkout/return?order_id={ORDER_ID}"
        assert args["cancel_url"] == ORIGIN + PREFIX + "/checkout/cancel?order_id={ORDER_ID}"
        assert edge.get(PREFIX + "/api/checkout/offer", headers={"Cookie": "production=secret"}).status_code == 401
        endpoint = PREFIX + "/api/checkout/webhook"
        assert edge.post(endpoint, content=b"fixture").status_code == 400
        adapter.verify.assert_called_once()
        for method, path, headers in (
            ("GET", endpoint, {}), ("HEAD", endpoint, {}), ("POST", endpoint + "/", {}), ("POST", endpoint + "?unexpected=1", {}),
            ("POST", endpoint.replace("/api/", "//api/"), {}),
            ("POST", endpoint.replace("/checkout/", "/%63heckout/"), {}),
            ("POST", "/api/checkout/webhook", {}), ("GET", "/practice", {}),
            ("GET", PREFIX + "/api/docs", {}), ("GET", PREFIX + "/api/checkout/offer", {"Host": "www.annababy.cc"}),
            ("POST", PREFIX + "/api/checkout/orders", auth),
            ("POST", PREFIX + "/api/checkout/orders", {**auth, "Origin": "https://other.example"}),
            ("POST", PREFIX + "/api/auth/register", {"Origin": ORIGIN}),
            ("POST", PREFIX + "/api/generate/submit-ai-writing", {**auth, "Origin": ORIGIN}),
        ):
            assert edge.request(method, path, headers=headers, follow_redirects=False).status_code == 404, path
        assert edge.post(PREFIX + "/api/checkout/orders", json={}, headers={**auth, "Origin": ORIGIN}).status_code == 422
        current = PREFIX + "/api/checkout/orders/current"
        assert edge.get(current, headers={"Cookie": "production=secret"}).status_code == 401
        assert edge.post(current, headers={**auth, "Origin": ORIGIN}).status_code == 404
        assert edge.get(current, headers=auth).status_code == 404
        adapter.create_checkout.side_effect = lambda order: CheckoutSession(
            "cs_test_fixture", "https://checkout.stripe.com/c/pay/cs_test_fixture",
            order.provider_price_id, "prod_fixture" if order.provider_price_id else None,
        )
        original = edge.post(PREFIX + "/api/checkout/orders",
                             json={"idempotency_key": "first-tab"}, headers={**auth, "Origin": ORIGIN})
        assert original.status_code == 200
        recovered = edge.get(current, headers=auth)
        assert recovered.json() == {"id": original.json()["id"], "test_mode": True}
        assert recovered.headers["cache-control"] == "private, no-store"
        adapter.create_checkout.assert_called_once()
        assert edge.get(PREFIX + "/api/checkout/orders/11111111-1111-1111-1111-111111111111", headers=auth).status_code == 404


def test_inner_checkout_requires_factory_marker_and_root_path(flags, monkeypatch):
    monkeypatch.setattr(app, "state", type(app.state)())
    request = Request({"type": "http", "app": app, "root_path": PREFIX})
    with pytest.raises(ValueError):
        checkout._sandbox(request)
    app.state.same_origin_rehearsal = True
    request.scope["root_path"] = PREFIX + "other"
    with pytest.raises(ValueError):
        checkout._sandbox(request)
