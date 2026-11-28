"""Test-mode Stripe adapter, inert until explicitly configured/invoked.

No keys, account IDs, products or endpoints are provisioned here. Tests inject an
httpx.MockTransport; no provider requests are needed to verify this implementation.
See docs/superpowers/specs/2026-11-15-stripe-test-adapter.md for trust boundaries.
"""
import hashlib
import hmac
import json
import re
import time
from urllib.parse import quote, urlsplit

import httpx

from app.services.checkout import (
    CheckoutRequest, CheckoutSession, ExpiredCheckoutSnapshot, GatewayScope, PaymentSnapshot,
)

API_ORIGIN = "https://api.stripe.com"
API_VERSION = "2026-10-28.endive"
SIGNATURE_TOLERANCE_SECONDS = 300
SUPPORTED_EVENTS = {
    "checkout.session.completed", "checkout.session.async_payment_succeeded",
    "checkout.session.async_payment_failed", "checkout.session.expired",
    "charge.refunded", "refund.created", "refund.updated", "refund.failed",
    "charge.dispute.created", "charge.dispute.updated", "charge.dispute.closed",
}
_METADATA_KEYS = ("order_id", "user_id", "sku", "reviews", "duration_days")


class UnsupportedStripeEvent(ValueError):
    """Authentic test event outside this adapter's subscription set; ignore safely."""


class StripeProviderError(RuntimeError):
    """Provider unavailable/malformed. Do not leak provider bodies or credentials."""


def _identifier(value, prefix):
    if not isinstance(value, str) or not re.fullmatch(re.escape(prefix) + r"[A-Za-z0-9_]+", value):
        raise ValueError("Invalid Stripe resource identifier")
    return value


def _https_url(value, *, checkout=False):
    if not isinstance(value, str) or any(c.isspace() for c in value):
        raise ValueError("Invalid HTTPS URL")
    parsed = urlsplit(value)
    local_return = not checkout and parsed.hostname in {"localhost", "127.0.0.1", "::1"}
    if (not parsed.hostname or (parsed.scheme != "https" and not (
                local_return and parsed.scheme == "http"))
            or parsed.username is not None or parsed.password is not None
            or (checkout and (parsed.hostname != "checkout.stripe.com" or parsed.port not in (None, 443)))
            or (not checkout and parsed.fragment)):
        raise ValueError("URL must use the configured HTTPS destination")
    return value


def _test_object(obj, object_type):
    if (not isinstance(obj, dict) or obj.get("object") != object_type
            or obj.get("livemode") is not False):
        raise ValueError("Stripe resource is not the expected test-mode object")
    return obj


def _metadata(obj):
    data = obj.get("metadata")
    if not isinstance(data, dict) or any(
        not isinstance(data.get(k), str) or not data[k] for k in _METADATA_KEYS
    ):
        raise ValueError("Missing order metadata")
    if (not data["user_id"].isdigit() or int(data["user_id"]) < 1
            or not data["reviews"].isdigit() or int(data["reviews"]) < 1
            or data["duration_days"] != "30"):
        raise ValueError("Invalid order metadata")
    result = {k: data[k] for k in _METADATA_KEYS}
    if "stripe_price_id" in data or "stripe_product_id" in data:
        result["stripe_price_id"] = _identifier(data.get("stripe_price_id"), "price_")
        result["stripe_product_id"] = _identifier(data.get("stripe_product_id"), "prod_")
    return result


class StripeTestAdapter:
    def __init__(self, api_key, webhook_secret, account_id, success_url, cancel_url,
                 *, http_client=None, clock=time.time):
        if (not isinstance(api_key, str) or not api_key.startswith("sk_test_")
                or len(api_key) <= len("sk_test_") or any(c.isspace() for c in api_key)):
            raise ValueError("An explicit Stripe test secret key is required")
        if (not isinstance(webhook_secret, str) or not webhook_secret.startswith("whsec_")
                or len(webhook_secret) <= len("whsec_")
                or any(c.isspace() for c in webhook_secret)):
            raise ValueError("An endpoint signing secret is required")
        _identifier(account_id, "acct_")
        self.scope = GatewayScope("stripe", account_id, "test")
        self._api_key, self._webhook_secret = api_key, webhook_secret
        self._success_url, self._cancel_url = _https_url(success_url), _https_url(cancel_url)
        self._client = http_client
        self._clock = clock

    def _request(self, method, path, *, params=None, data=None, idempotency_key=None):
        # Paths are internal constants + strict identifiers, never provider URLs.
        headers = {"Authorization": f"Bearer {self._api_key}", "Stripe-Version": API_VERSION}
        if idempotency_key is not None:
            headers["Idempotency-Key"] = idempotency_key
        def send(client):
            try:
                response = client.request(method, API_ORIGIN + path, params=params, data=data,
                                          headers=headers, follow_redirects=False, timeout=15)
                if response.status_code < 200 or response.status_code >= 300:
                    raise StripeProviderError("Stripe test request did not succeed")
                result = response.json()
                if not isinstance(result, dict):
                    raise StripeProviderError("Stripe returned an invalid object")
                return result
            except (httpx.HTTPError, json.JSONDecodeError) as exc:
                raise StripeProviderError("Stripe test request unavailable") from None
        if self._client is not None:
            return send(self._client)
        with httpx.Client() as client:
            return send(client)

    def _check_account(self):
        result = self._request("GET", "/v1/account")
        if result.get("object") != "account" or result.get("id") != self.scope.account_id:
            raise ValueError("Stripe test key belongs to another account")

    def _selected_price(self, order):
        price_id = _identifier(order.provider_price_id, "price_")
        if order.amount_minor != 1900 or order.currency != "USD":
            raise ValueError("The selected Dashboard Price must be USD19")
        price = _test_object(self._request(
            "GET", f"/v1/prices/{price_id}", params={"expand[]": "product"}), "price")
        product = _test_object(price.get("product"), "product")
        product_id = _identifier(product.get("id"), "prod_")
        if (price.get("id") != price_id or price.get("active") is not True
                or price.get("type") != "one_time" or price.get("recurring") is not None
                or price.get("billing_scheme") != "per_unit"
                or price.get("custom_unit_amount") is not None
                or price.get("transform_quantity") is not None
                or price.get("unit_amount") != 1900 or price.get("currency") != "usd"
                or product.get("active") is not True
                or product.get("name") != "IELTS 30-Day Study Pass"):
            raise ValueError("Selected Price is not the active IELTS USD19 one-time offer")
        return price_id, product_id

    def create_checkout(self, order: CheckoutRequest):
        self._check_account()
        metadata = dict(order_id=order.order_id, user_id=str(order.user_id), sku=order.sku,
                        reviews=str(order.reviews), duration_days=str(order.duration_days))
        data = {
            "mode": "payment", "payment_method_types[0]": "card",
            "client_reference_id": order.order_id,
            "success_url": self._success_url.replace("{ORDER_ID}", quote(order.order_id, safe="")),
            "cancel_url": self._cancel_url.replace("{ORDER_ID}", quote(order.order_id, safe="")),
            "allow_promotion_codes": "false", "automatic_tax[enabled]": "false",
            "adaptive_pricing[enabled]": "false",
            "line_items[0][quantity]": "1",
            "line_items[0][price_data][currency]": order.currency.lower(),
            "line_items[0][price_data][unit_amount]": str(order.amount_minor),
            "line_items[0][price_data][product_data][name]": "IELTS 30-day study pass",
            "line_items[0][price_data][product_data][metadata][sku]": order.sku,
        }
        selected_price_id, selected_product_id = None, None
        if order.provider_price_id is not None:
            selected_price_id, selected_product_id = self._selected_price(order)
            data = {key: value for key, value in data.items()
                    if not key.startswith("line_items[0][price_data]")}
            data["line_items[0][price]"] = selected_price_id
            data["currency"] = order.currency.lower()
            metadata["stripe_price_id"] = selected_price_id
            metadata["stripe_product_id"] = selected_product_id
        for key, value in metadata.items():
            data[f"metadata[{key}]"] = value
            data[f"payment_intent_data[metadata][{key}]"] = value
        result = self._request("POST", "/v1/checkout/sessions", data=data,
                               idempotency_key=order.idempotency_key)
        _test_object(result, "checkout.session")
        session_id = _identifier(result.get("id"), "cs_test_")
        if (result.get("adaptive_pricing") or {}).get("enabled") is True:
            raise ValueError("Adaptive pricing is outside this fixed-price test offer")
        if (result.get("mode") != "payment"
                or result.get("client_reference_id") != order.order_id
                or _metadata(result) != metadata
                or result.get("amount_total") != order.amount_minor
                or result.get("currency") != order.currency.lower()):
            raise ValueError("Stripe checkout does not match the server order")
        return CheckoutSession(session_id, _https_url(result.get("url"), checkout=True),
                               selected_price_id, selected_product_id)

    def _signed_event(self, payload, headers):
        if not isinstance(payload, bytes) or not payload or len(payload) > 1_000_000:
            raise ValueError("Invalid webhook body")
        signature = next((v for k, v in headers.items() if k.lower() == "stripe-signature"), "")
        if not isinstance(signature, str):
            raise ValueError("Missing webhook signature")
        parts = [p.strip().split("=", 1) for p in signature.split(",")]
        timestamps = [v for p in parts if len(p) == 2 for k, v in [p] if k == "t"]
        signatures = [v for p in parts if len(p) == 2 for k, v in [p] if k == "v1"]
        if len(timestamps) != 1 or not re.fullmatch(r"[0-9]+", timestamps[0]) or not signatures:
            raise ValueError("Invalid webhook signature")
        timestamp = int(timestamps[0])
        if abs(self._clock() - timestamp) > SIGNATURE_TOLERANCE_SECONDS:
            raise ValueError("Webhook timestamp is outside tolerance")
        expected = hmac.new(self._webhook_secret.encode(), timestamps[0].encode() + b"." + payload,
                            hashlib.sha256).hexdigest()
        if not any(re.fullmatch(r"[0-9a-f]{64}", sig) and hmac.compare_digest(expected, sig)
                   for sig in signatures):
            raise ValueError("Webhook signature verification failed")
        try:
            event = json.loads(payload)
        except (ValueError, UnicodeDecodeError):
            raise ValueError("Invalid webhook JSON") from None
        _test_object(event, "event")
        _identifier(event.get("id"), "evt_")
        # Standalone-account integration only. Never send Stripe-Account headers.
        if event.get("account") not in (None, self.scope.account_id) or event.get("context"):
            raise ValueError("Webhook account scope mismatch")
        if event.get("type") not in SUPPORTED_EVENTS:
            raise UnsupportedStripeEvent("Unrelated authenticated test event")
        return event

    def _list(self, path, params):
        result = self._request("GET", path, params=params)
        if (result.get("object") != "list" or not isinstance(result.get("data"), list)
                or not isinstance(result.get("has_more"), bool)):
            raise ValueError("Invalid Stripe collection")
        return result

    def _session_for_payment(self, payment_id):
        result = self._list("/v1/checkout/sessions", {"payment_intent": payment_id, "limit": "2"})
        if result["has_more"] or len(result["data"]) != 1:
            raise ValueError("Payment must belong to exactly one Checkout Session")
        session = _test_object(result["data"][0], "checkout.session")
        return _identifier(session.get("id"), "cs_test_")

    def _event_session(self, event):
        data = event.get("data")
        if not isinstance(data, dict):
            raise ValueError("Missing webhook data")
        obj = data.get("object")
        kind = event["type"]
        if kind.startswith("checkout.session."):
            _test_object(obj, "checkout.session")
            return _identifier(obj.get("id"), "cs_test_"), None
        if kind == "charge.refunded":
            _test_object(obj, "charge")
            charge_id = _identifier(obj.get("id"), "ch_")
            current = _test_object(self._request("GET", f"/v1/charges/{charge_id}"), "charge")
            if current.get("id") != charge_id:
                raise ValueError("Charge identity mismatch")
            payment_id = _identifier(current.get("payment_intent"), "pi_")
        elif kind.startswith("refund."):
            # Refund objects do not have a livemode property; scope comes from
            # signed event, authenticated API account and linked PI/session/charge.
            if not isinstance(obj, dict) or obj.get("object") != "refund":
                raise ValueError("Expected refund object")
            refund_id = _identifier(obj.get("id"), "re_")
            current = self._request("GET", f"/v1/refunds/{refund_id}")
            if current.get("object") != "refund" or current.get("id") != refund_id:
                raise ValueError("Refund identity mismatch")
            payment_id = _identifier(current.get("payment_intent"), "pi_")
        else:
            _test_object(obj, "dispute")
            dispute_id = _identifier(obj.get("id"), "dp_")
            current = _test_object(self._request("GET", f"/v1/disputes/{dispute_id}"), "dispute")
            if current.get("id") != dispute_id:
                raise ValueError("Dispute identity mismatch")
            payment_id = _identifier(current.get("payment_intent"), "pi_")
        return self._session_for_payment(payment_id), payment_id

    def _refunds(self, payment_id, currency, amount):
        total, pending, cursor, seen = 0, False, None, set()
        for _ in range(10):
            params = {"payment_intent": payment_id, "limit": "100"}
            if cursor:
                params["starting_after"] = cursor
            page = self._list("/v1/refunds", params)
            for refund in page["data"]:
                if not isinstance(refund, dict):
                    raise ValueError("Invalid refund object")
                refund_id = _identifier(refund.get("id"), "re_")
                if (refund.get("object") != "refund" or refund.get("payment_intent") != payment_id
                        or refund.get("currency") != currency or refund_id in seen
                        or type(refund.get("amount")) is not int or refund["amount"] < 1):
                    raise ValueError("Refund correlation mismatch")
                seen.add(refund_id)
                if refund.get("status") == "succeeded":
                    total += refund["amount"]
                elif refund.get("status") in {"pending", "requires_action"}:
                    pending = True
                elif refund.get("status") not in {"failed", "canceled"}:
                    raise ValueError("Unsupported refund state")
            if total > amount:
                raise ValueError("Refund total exceeds original order")
            if not page["has_more"]:
                return total, pending
            if not page["data"]:
                raise ValueError("Incomplete refund pagination")
            cursor = page["data"][-1]["id"]
        raise ValueError("Refund history requires manual reconciliation")

    def verify(self, payload: bytes, headers: dict):
        event = self._signed_event(payload, headers)
        self._check_account()
        session_id, event_payment_id = self._event_session(event)
        session = _test_object(self._request("GET", f"/v1/checkout/sessions/{session_id}"),
                               "checkout.session")
        if session.get("id") != session_id or session.get("mode") != "payment":
            raise ValueError("Checkout Session identity mismatch")
        if ((session.get("adaptive_pricing") or {}).get("enabled") is True
                or session.get("presentment_details")):
            raise ValueError("Adaptive pricing is outside this fixed-price test offer")
        metadata = _metadata(session)
        if session.get("client_reference_id") != metadata["order_id"]:
            raise ValueError("Checkout Session order ownership mismatch")
        amount, currency = session.get("amount_total"), session.get("currency")
        if (type(amount) is not int or amount < 1 or not isinstance(currency, str)
                or not re.fullmatch("[a-z]{3}", currency)):
            raise ValueError("Invalid Checkout Session total")
        details = session.get("total_details", {})
        if (session.get("amount_subtotal") != amount
                or any(details.get(k) != 0 for k in ("amount_discount", "amount_shipping", "amount_tax"))):
            raise ValueError("Tax, discounts and shipping are outside this test offer")
        lines = self._list(f"/v1/checkout/sessions/{session_id}/line_items",
                           {"limit": "2", "expand[]": "data.price.product"})
        if lines["has_more"] or len(lines["data"]) != 1:
            raise ValueError("Checkout must contain exactly one study pass")
        line = lines["data"][0]
        if not isinstance(line, dict):
            raise ValueError("Invalid checkout line item")
        price = _test_object(line.get("price"), "price")
        product = _test_object(price.get("product"), "product")
        if (line.get("quantity") != 1 or line.get("amount_total") != amount
                or line.get("currency") != currency or price.get("unit_amount") != amount
                or price.get("currency") != currency or price.get("recurring") is not None):
            raise ValueError("Checkout line item does not match study-pass amount")
        selected_price_id, selected_product_id = None, None
        if "stripe_price_id" in metadata:
            selected_price_id = _identifier(price.get("id"), "price_")
            selected_product_id = _identifier(product.get("id"), "prod_")
            if (selected_price_id != metadata["stripe_price_id"]
                    or selected_product_id != metadata["stripe_product_id"]
                    or price.get("type") != "one_time"
                    or price.get("billing_scheme") != "per_unit"
                    or price.get("custom_unit_amount") is not None
                    or price.get("transform_quantity") is not None):
                raise ValueError("Checkout line item does not match its recorded Price/Product")
            # Product names and active flags may change after purchase. Never use
            # current configuration/labels to reinterpret an existing paid order.
        elif product.get("metadata", {}).get("sku") != metadata["sku"]:
            raise ValueError("Legacy inline checkout SKU mismatch")
        if event["type"] == "checkout.session.expired":
            if (session.get("status") != "expired" or session.get("payment_status") != "unpaid"
                    or "payment_intent" not in session or session["payment_intent"] is not None
                    or session.get("after_expiration") is not None or session.get("recovered_from") is not None):
                # Never release a slot based on an expired label alone.
                raise ValueError("Checkout expiry is not confirmed unpaid and terminal")
            return ExpiredCheckoutSnapshot(event["id"], metadata["order_id"], session_id,
                                           int(metadata["user_id"]), metadata["sku"], amount,
                                           currency.upper(), int(metadata["reviews"]),
                                           int(metadata["duration_days"]), selected_price_id,
                                           selected_product_id)
        payment_id = _identifier(session.get("payment_intent"), "pi_")
        if event_payment_id is not None and event_payment_id != payment_id:
            raise ValueError("Event payment does not own Checkout Session")
        payment = _test_object(self._request("GET", f"/v1/payment_intents/{payment_id}"), "payment_intent")
        if (payment.get("id") != payment_id or _metadata(payment) != metadata
                or payment.get("amount") != amount or payment.get("currency") != currency):
            raise ValueError("PaymentIntent does not match Checkout Session")
        refunded, refund_pending = self._refunds(payment_id, currency, amount)
        state = "pending"
        charge = None
        if payment.get("latest_charge"):
            charge_id = _identifier(payment["latest_charge"], "ch_")
            charge = _test_object(self._request("GET", f"/v1/charges/{charge_id}"), "charge")
            if (charge.get("id") != charge_id or charge.get("payment_intent") != payment_id
                    or charge.get("amount") != amount or charge.get("currency") != currency):
                raise ValueError("Charge does not match PaymentIntent")
        if refunded:
            state = "refunded"  # core revokes full, sends partial to manual review
        elif charge and charge.get("disputed") is True:
            state = "disputed"
        elif refund_pending:
            state = "pending"
        elif (session.get("status") == "complete" and session.get("payment_status") == "paid"
                and payment.get("status") == "succeeded" and payment.get("amount_received") == amount
                and charge and charge.get("paid") is True and charge.get("captured") is True
                and charge.get("amount_captured") == amount and charge.get("amount_refunded") == 0):
            state = "settled"
        elif payment.get("status") in {"canceled", "requires_payment_method"}:
            state = "failed"
        return PaymentSnapshot(event["id"], metadata["order_id"], session_id, payment_id,
                               metadata["sku"], amount, currency.upper(), state, refunded,
                               selected_price_id, selected_product_id)
