"""All Stripe endpoints are in-memory httpx fixtures; no accounts/keys are created."""
import copy
import hashlib
import hmac
import json
from urllib.parse import parse_qs

import httpx
import pytest

from app.services.checkout import CheckoutRequest
from app.services.stripe_test import (
    API_VERSION, StripeTestAdapter, StripeProviderError, UnsupportedStripeEvent,
)

NOW = 1800000000
SECRET = "whsec_not_a_real_endpoint_secret"
META = {"order_id": "fixture-order", "user_id": "123", "sku": "fixture-pass",
        "reviews": "5", "duration_days": "30"}
REQUEST = CheckoutRequest("fixture-order", 123, "fixture-pass", 1900, "USD", 5, 30, "fixture-order")


class StripeFixture:
    def __init__(self):
        self.calls = []
        self.status_code = 200
        self.session = {
            "object": "checkout.session", "id": "cs_test_fixture", "livemode": False,
            "mode": "payment", "metadata": copy.deepcopy(META), "client_reference_id": "fixture-order",
            "amount_total": 1900, "amount_subtotal": 1900, "currency": "usd",
            "total_details": {"amount_discount": 0, "amount_shipping": 0, "amount_tax": 0},
            "payment_intent": "pi_fixture", "status": "complete", "payment_status": "paid",
            "url": "https://checkout.stripe.com/c/pay/cs_test_fixture#fixture",
        }
        self.payment = {
            "object": "payment_intent", "id": "pi_fixture", "livemode": False,
            "metadata": copy.deepcopy(META), "amount": 1900, "amount_received": 1900,
            "currency": "usd", "status": "succeeded", "latest_charge": "ch_fixture",
        }
        self.charge = {
            "object": "charge", "id": "ch_fixture", "livemode": False,
            "payment_intent": "pi_fixture", "amount": 1900, "currency": "usd",
            "paid": True, "captured": True, "amount_captured": 1900, "amount_refunded": 0,
            "disputed": False,
        }
        self.line = {"quantity": 1, "amount_total": 1900, "currency": "usd",
                     "price": {"object": "price", "livemode": False, "unit_amount": 1900,
                               "currency": "usd", "recurring": None,
                               "product": {"object": "product", "livemode": False,
                                           "metadata": {"sku": "fixture-pass"}}}}
        self.refunds = []
        self.account = "acct_fixture"
        self.refund_has_more = False

    def respond(self, request):
        self.calls.append(request)
        assert request.url.host == "api.stripe.com"
        assert request.headers["Stripe-Version"] == API_VERSION
        assert request.headers["Authorization"] == "Bearer sk_test_not_a_real_key"
        path = request.url.path
        if self.status_code != 200:
            return httpx.Response(self.status_code, json={"error": {"message": "sensitive"}})
        if path == "/v1/account":
            obj = {"object": "account", "id": self.account}
        elif path in ("/v1/checkout/sessions/cs_test_fixture", "/v1/checkout/sessions") and request.method == "POST":
            obj = self.session
        elif path == "/v1/checkout/sessions":
            obj = {"object": "list", "data": [self.session], "has_more": False}
        elif path == "/v1/checkout/sessions/cs_test_fixture":
            obj = self.session
        elif path == "/v1/checkout/sessions/cs_test_fixture/line_items":
            obj = {"object": "list", "data": [self.line], "has_more": False}
        elif path == "/v1/payment_intents/pi_fixture":
            obj = self.payment
        elif path == "/v1/charges/ch_fixture":
            obj = self.charge
        elif path == "/v1/refunds":
            obj = {"object": "list", "data": self.refunds, "has_more": self.refund_has_more}
        elif path == "/v1/refunds/re_fixture":
            obj = self.refunds[0]
        elif path == "/v1/disputes/dp_fixture":
            obj = {"object": "dispute", "id": "dp_fixture", "livemode": False,
                   "payment_intent": "pi_fixture"}
        else:
            raise AssertionError(f"Unexpected request: {request.method} {path}")
        return httpx.Response(200, json=obj)

    def adapter(self, **kwargs):
        return StripeTestAdapter(
            "sk_test_not_a_real_key", SECRET, "acct_fixture",
            "http://localhost:5173/checkout/return?order_id={ORDER_ID}",
            "http://localhost:5173/checkout/cancel?order_id={ORDER_ID}",
            http_client=httpx.Client(transport=httpx.MockTransport(self.respond)),
            clock=lambda: NOW, **kwargs)


def signed(event=None, timestamp=NOW):
    if event is None:
        event = {"object": "event", "id": "evt_fixture", "livemode": False,
                 "type": "checkout.session.completed",
                 "data": {"object": {"object": "checkout.session", "id": "cs_test_fixture",
                                     "livemode": False}}}
    body = json.dumps(event, separators=(",", ":")).encode()
    signature = hmac.new(SECRET.encode(), str(timestamp).encode() + b"." + body,
                         hashlib.sha256).hexdigest()
    return body, {"Stripe-Signature": f"t={timestamp},v1={signature}"}


def refund(amount=1900, status="succeeded"):
    return {"object": "refund", "id": "re_fixture", "payment_intent": "pi_fixture",
            "currency": "usd", "amount": amount, "status": status}


def test_constructor_is_inert_and_rejects_live_key():
    fixture = StripeFixture()
    fixture.adapter()
    assert fixture.calls == []
    with pytest.raises(ValueError):
        StripeTestAdapter("sk_live_forbidden", SECRET, "acct_fixture", "https://example.test/ok",
                          "https://example.test/no")


def test_create_uses_immutable_one_time_offer_and_stable_key():
    fixture = StripeFixture()
    adapter = fixture.adapter()
    first = adapter.create_checkout(REQUEST)
    second = adapter.create_checkout(REQUEST)
    assert first == second
    posts = [r for r in fixture.calls if r.method == "POST"]
    assert all(r.headers["Idempotency-Key"] == REQUEST.order_id for r in posts)
    fields = parse_qs(posts[0].content.decode())
    assert fields["mode"] == ["payment"]
    assert fields["adaptive_pricing[enabled]"] == ["false"]
    assert fields["line_items[0][price_data][unit_amount]"] == ["1900"]
    assert fields["line_items[0][quantity]"] == ["1"]
    assert fields["payment_intent_data[metadata][order_id]"] == ["fixture-order"]
    assert fields["success_url"] == ["http://localhost:5173/checkout/return?order_id=fixture-order"]
    assert "customer_email" not in fields
    assert not any("subscription" in field for field in fields)


@pytest.mark.parametrize("url", ["http://checkout.stripe.com/x", "https://evil.test/x",
                                  "https://checkout.stripe.com.evil.test/x",
                                  "https://user:secret@checkout.stripe.com/x",
                                  "https://checkout.stripe.com:444/x"])
def test_hosted_url_allowlist(url):
    fixture = StripeFixture()
    fixture.session["url"] = url
    with pytest.raises(ValueError):
        fixture.adapter().create_checkout(REQUEST)


def test_signature_tampering_and_stale_or_future_rejected_without_api_calls():
    fixture = StripeFixture()
    adapter = fixture.adapter()
    body, headers = signed()
    with pytest.raises(ValueError):
        adapter.verify(body + b" ", headers)
    for stamp in (NOW - 301, NOW + 301):
        with pytest.raises(ValueError):
            adapter.verify(*signed(timestamp=stamp))
    with pytest.raises(ValueError):
        adapter.verify(body, {"Stripe-Signature": f"t={NOW},v0=ignored,payload=ignored"})
    assert fixture.calls == []


def test_native_signature_multiple_v1_and_debug_metadata():
    fixture = StripeFixture()
    body, headers = signed()
    headers["Stripe-Signature"] += ",v1=bad,payload=not-authority,secret=not-authority"
    snap = fixture.adapter().verify(body, headers)
    assert snap.state == "settled" and snap.payment_id == "pi_fixture"
    assert snap.amount_minor == 1900 and snap.currency == "USD" and snap.sku == "fixture-pass"


@pytest.mark.parametrize("change", [{"livemode": True}, {"account": "acct_other"},
                                    {"context": "acct_other"}])
def test_event_mode_and_account_rejected_before_api(change):
    fixture = StripeFixture()
    body, _ = signed()
    event = json.loads(body)
    event.update(change)
    with pytest.raises(ValueError):
        fixture.adapter().verify(*signed(event))
    assert fixture.calls == []


def test_unknown_authentic_event_ignored_without_api_calls():
    fixture = StripeFixture()
    body, _ = signed()
    event = json.loads(body)
    event["type"] = "customer.created"
    with pytest.raises(UnsupportedStripeEvent):
        fixture.adapter().verify(*signed(event))
    assert fixture.calls == []


def test_key_account_must_match_expected_account():
    fixture = StripeFixture()
    fixture.account = "acct_other"
    with pytest.raises(ValueError):
        fixture.adapter().verify(*signed())


@pytest.mark.parametrize("target,field,value", [
    ("session", "livemode", True), ("payment", "livemode", True), ("charge", "livemode", True),
    ("session", "client_reference_id", "other-order"), ("payment", "amount", 1),
    ("payment", "currency", "eur"), ("charge", "payment_intent", "pi_other"),
])
def test_authoritative_resources_must_correlate(target, field, value):
    fixture = StripeFixture()
    getattr(fixture, target)[field] = value
    with pytest.raises(ValueError):
        fixture.adapter().verify(*signed())


def test_metadata_and_line_item_sku_mismatch_rejected():
    fixture = StripeFixture()
    fixture.payment["metadata"]["user_id"] = "999"
    with pytest.raises(ValueError):
        fixture.adapter().verify(*signed())
    fixture.payment["metadata"] = copy.deepcopy(META)
    fixture.line["price"]["product"]["metadata"]["sku"] = "other"
    with pytest.raises(ValueError):
        fixture.adapter().verify(*signed())


@pytest.mark.parametrize("target,field,value", [
    ("session", "payment_status", "unpaid"), ("payment", "status", "processing"),
    ("payment", "amount_received", 1800), ("charge", "captured", False),
])
def test_completion_alone_is_not_settlement(target, field, value):
    fixture = StripeFixture()
    getattr(fixture, target)[field] = value
    assert fixture.adapter().verify(*signed()).state == "pending"


def test_full_and_partial_successful_refunds_and_pending_refund():
    fixture = StripeFixture()
    fixture.refunds = [refund()]
    assert fixture.adapter().verify(*signed()).state == "refunded"
    fixture.refunds = [refund(500)]
    assert fixture.adapter().verify(*signed()).refunded_minor == 500
    fixture.refunds = [refund(status="pending")]
    snap = fixture.adapter().verify(*signed())
    assert snap.state == "pending" and snap.refunded_minor == 0
    fixture.refunds = [refund(status="failed")]
    assert fixture.adapter().verify(*signed()).state == "settled"


def test_refund_event_resolves_payment_session_and_current_state():
    fixture = StripeFixture()
    fixture.refunds = [refund()]
    event = {"object": "event", "id": "evt_refund", "livemode": False,
             "type": "refund.updated", "data": {"object": fixture.refunds[0]}}
    snap = fixture.adapter().verify(*signed(event))
    assert snap.state == "refunded" and snap.refunded_minor == 1900
    assert any(r.url.path == "/v1/checkout/sessions" for r in fixture.calls)


def test_dispute_maps_to_review_not_settlement():
    fixture = StripeFixture()
    fixture.charge["disputed"] = True
    assert fixture.adapter().verify(*signed()).state == "disputed"


def test_refund_mismatch_and_incomplete_pagination_fail_closed():
    fixture = StripeFixture()
    fixture.refunds = [refund()]
    fixture.refunds[0]["payment_intent"] = "pi_other"
    with pytest.raises(ValueError):
        fixture.adapter().verify(*signed())
    fixture.refunds = []
    fixture.refund_has_more = True
    with pytest.raises(ValueError):
        fixture.adapter().verify(*signed())


def test_provider_error_is_sanitized_and_never_followed():
    fixture = StripeFixture()
    fixture.status_code = 302
    with pytest.raises(StripeProviderError) as error:
        fixture.adapter().verify(*signed())
    assert "sensitive" not in str(error.value)
    assert len(fixture.calls) == 1


@pytest.mark.parametrize("hours,blocked", [(22, False), (23, True), (25, True)])
def test_ambiguous_session_creation_has_bounded_retry(test_db, test_user, hours, blocked):
    from datetime import datetime, timedelta
    from fastapi import HTTPException
    from app.services.checkout import Offer, start_checkout
    from tests.support.fake_checkout import FakeGateway
    gateway = FakeGateway()
    gateway.timeout_after_create_once = True
    when = datetime(2026, 11, 15, 10)
    offer = Offer("fixture-pass", 1900, "USD", 5)
    with pytest.raises(TimeoutError):
        start_checkout(test_db, test_user.id, "retry", offer, gateway, now=when)
    if blocked:
        with pytest.raises(HTTPException) as error:
            start_checkout(test_db, test_user.id, "retry", offer, gateway,
                           now=when + timedelta(hours=hours))
        assert error.value.status_code == 409
        assert len(gateway.calls) == 1
    else:
        order = start_checkout(test_db, test_user.id, "retry", offer, gateway,
                               now=when + timedelta(hours=hours))
        assert order.session_id is not None and len(gateway.sessions) == 1


def test_open_checkout_can_have_no_payment_intent_without_granting():
    fixture = StripeFixture()
    fixture.session.update(payment_intent=None, status="open", payment_status="unpaid")
    created = fixture.adapter().create_checkout(REQUEST)
    assert created.session_id == "cs_test_fixture"
    # This adapter does not subscribe to session.created/open events. A malformed
    # completed notification with no PI fails closed rather than inventing payment.
    with pytest.raises(ValueError):
        fixture.adapter().verify(*signed())


def test_adaptive_pricing_cannot_change_customer_presentment():
    fixture = StripeFixture()
    fixture.session["adaptive_pricing"] = {"enabled": True}
    with pytest.raises(ValueError):
        fixture.adapter().create_checkout(REQUEST)
    with pytest.raises(ValueError):
        fixture.adapter().verify(*signed())
