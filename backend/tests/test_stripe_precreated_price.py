"""Dashboard Price support, entirely offline with synthetic provider identifiers."""
import copy
from dataclasses import asdict, replace
from hashlib import sha256
import json
from urllib.parse import parse_qs

from fastapi import HTTPException
import httpx
import pytest
from sqlalchemy import create_engine, inspect, text

from app.config import settings
from app.models.models import CheckoutEvent, CheckoutOrder, StudyPassGrant
from app.services.checkout import Offer, process_notification, start_checkout
from tests.test_stripe_test_adapter import StripeFixture, REQUEST, signed
from tests.support.fake_checkout import FakeGateway, FakeVerifier
from tests.test_checkout_acceptance import snapshot

PRICE_ID = "price_dashboard_fixture"
PRODUCT_ID = "prod_ielts_fixture"
OFFER = Offer("fixture-pass", 1900, "USD", 5, provider_price_id=PRICE_ID)


class DashboardPriceFixture(StripeFixture):
    def __init__(self):
        super().__init__()
        self.price = {
            "object": "price", "id": PRICE_ID, "livemode": False, "active": True,
            "type": "one_time", "recurring": None, "unit_amount": 1900, "currency": "usd",
            "billing_scheme": "per_unit", "custom_unit_amount": None, "transform_quantity": None,
            "product": {
                "object": "product", "id": PRODUCT_ID, "livemode": False, "active": True,
                "name": "IELTS 30-Day Study Pass", "metadata": {},
            },
        }
        self.line["price"] = copy.deepcopy(self.price)
        for obj in (self.session, self.payment):
            obj["metadata"]["stripe_price_id"] = PRICE_ID
            obj["metadata"]["stripe_product_id"] = PRODUCT_ID

    def respond(self, request):
        if request.url.path == f"/v1/prices/{PRICE_ID}":
            self.calls.append(request)
            assert request.url.params["expand[]"] == "product"
            return httpx.Response(200, json=self.price)
        return super().respond(request)


def test_precreated_price_selected_without_inline_product_or_owner_metadata():
    fixture = DashboardPriceFixture()
    result = fixture.adapter().create_checkout(replace(REQUEST, provider_price_id=PRICE_ID))
    assert (result.provider_price_id, result.provider_product_id) == (PRICE_ID, PRODUCT_ID)
    fields = parse_qs(next(r for r in fixture.calls if r.method == "POST").content.decode())
    assert fields["line_items[0][price]"] == [PRICE_ID]
    assert fields["currency"] == ["usd"]
    assert not any("price_data" in key for key in fields)
    assert fields["metadata[stripe_price_id]"] == [PRICE_ID]
    assert fields["payment_intent_data[metadata][stripe_product_id]"] == [PRODUCT_ID]
    assert fixture.price["product"]["metadata"] == {}  # no extra owner setup step


@pytest.mark.parametrize("field,value", [
    ("id", "price_other"), ("livemode", True), ("active", False), ("type", "recurring"),
    ("recurring", {"interval": "month"}), ("unit_amount", 2000), ("currency", "eur"),
    ("billing_scheme", "tiered"), ("custom_unit_amount", {"enabled": True}),
    ("transform_quantity", {"divide_by": 5, "round": "up"}),
])
def test_wrong_price_never_creates_checkout(field, value):
    fixture = DashboardPriceFixture()
    fixture.price[field] = value
    with pytest.raises(ValueError):
        fixture.adapter().create_checkout(replace(REQUEST, provider_price_id=PRICE_ID))
    assert not any(r.method == "POST" for r in fixture.calls)


@pytest.mark.parametrize("field,value", [
    ("livemode", True), ("active", False), ("name", "Other App Pass"),
    ("id", "not_a_product"),
])
def test_wrong_app_or_inactive_product_never_creates_checkout(field, value):
    fixture = DashboardPriceFixture()
    fixture.price["product"][field] = value
    with pytest.raises(ValueError):
        fixture.adapter().create_checkout(replace(REQUEST, provider_price_id=PRICE_ID))
    assert not any(r.method == "POST" for r in fixture.calls)


def test_price_lookup_uses_expected_merchant_before_catalog_read():
    fixture = DashboardPriceFixture()
    fixture.account = "acct_other"
    with pytest.raises(ValueError):
        fixture.adapter().create_checkout(replace(REQUEST, provider_price_id=PRICE_ID))
    assert len(fixture.calls) == 1 and fixture.calls[0].url.path == "/v1/account"


def test_settlement_survives_archival_and_rename_but_not_identity_change():
    fixture = DashboardPriceFixture()
    fixture.line["price"]["active"] = False
    fixture.line["price"]["product"].update(active=False, name="Renamed after sale")
    snap = fixture.adapter().verify(*signed())
    assert snap.state == "settled"
    assert (snap.provider_price_id, snap.provider_product_id) == (PRICE_ID, PRODUCT_ID)
    fixture.line["price"]["product"]["id"] = "prod_other"
    with pytest.raises(ValueError):
        fixture.adapter().verify(*signed())


def test_durable_order_binding_and_changed_config_cannot_reinterpret_settlement(test_db, test_user):
    fixture = DashboardPriceFixture()
    # The fixture echoes the actual server order into the mock API response.
    base_respond = fixture.respond
    def respond(request):
        if request.method == "POST":
            fields = parse_qs(request.content.decode())
            for obj in (fixture.session, fixture.payment):
                for field in ("order_id", "user_id", "sku", "reviews", "duration_days"):
                    obj["metadata"][field] = fields[f"metadata[{field}]"][0]
            fixture.session["client_reference_id"] = fields["client_reference_id"][0]
        return base_respond(request)
    fixture.respond = respond
    adapter = fixture.adapter()
    order = start_checkout(test_db, test_user.id, "fixture-idempotency", OFFER, adapter)
    assert (order.provider_price_id, order.provider_product_id) == (PRICE_ID, PRODUCT_ID)
    # Config switches to a different Price: retries may not mutate the original.
    with pytest.raises(HTTPException) as error:
        start_checkout(test_db, test_user.id, "fixture-idempotency",
                       replace(OFFER, provider_price_id="price_future_fixture"), adapter)
    assert error.value.status_code == 409
    processed = process_notification(test_db, *signed(), adapter)
    assert processed.state == "fulfilled"
    assert test_db.get(StudyPassGrant, processed.grant_id).reviews_remaining == 5
    # An authenticated notification for another Product can never grant this order.
    bad = replace(adapter.verify(*signed()), event_id="evt_other",
                  provider_product_id="prod_other")
    with pytest.raises(ValueError):
        process_notification(test_db, b"fixture-notification", {"fixture-proof": "known"},
                             FakeVerifier(adapter.scope, bad))
    assert test_db.query(StudyPassGrant).count() == 1


def test_inline_orders_and_event_fingerprints_preserved(test_db, test_user):
    gateway = FakeGateway()
    old_offer = Offer("fixture-30-day", 1900, "USD", 5)
    order = start_checkout(test_db, test_user.id, "legacy-inline", old_offer, gateway)
    event = snapshot(order)
    identity = asdict(event)
    for key in ("state", "refunded_minor", "provider_price_id", "provider_product_id"):
        identity.pop(key)
    legacy_fingerprint = sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
    process_notification(test_db, b"fixture-notification", {"fixture-proof": "known"},
                         FakeVerifier(gateway.scope, event))
    assert order.provider_price_id is None and order.provider_product_id is None
    assert test_db.query(CheckoutEvent).one().fingerprint == legacy_fingerprint


def test_router_price_configuration_is_server_only_and_fixed_usd19(monkeypatch):
    from app.routers import checkout
    monkeypatch.setattr(settings, "STRIPE_TEST_CHECKOUT_ENABLED", True)
    monkeypatch.setattr(settings, "STUDY_PASS_ENABLED", True)
    monkeypatch.setattr(settings, "STRIPE_TEST_RETURN_ORIGIN", "http://localhost:5173")
    monkeypatch.setattr(settings, "STRIPE_TEST_OFFER_SKU", "fixture-pass")
    monkeypatch.setattr(settings, "STRIPE_TEST_AMOUNT_MINOR", 1900)
    monkeypatch.setattr(settings, "STRIPE_TEST_WRITING_REVIEWS", 5)
    monkeypatch.setattr(settings, "STRIPE_TEST_SECRET_KEY", "sk_test_fixture")
    monkeypatch.setattr(settings, "STRIPE_TEST_WEBHOOK_SECRET", "whsec_fixture")
    monkeypatch.setattr(settings, "STRIPE_TEST_ACCOUNT_ID", "acct_fixture")
    monkeypatch.setattr(settings, "STRIPE_TEST_PRICE_ID", PRICE_ID)
    offer, _ = checkout._sandbox()
    assert offer.provider_price_id == PRICE_ID
    monkeypatch.setattr(settings, "STRIPE_TEST_AMOUNT_MINOR", 1999)
    with pytest.raises(ValueError):
        checkout._sandbox()


def test_additive_columns_preserve_legacy_order_row(tmp_path, monkeypatch):
    from app import database
    engine = create_engine(f"sqlite:///{tmp_path / 'old-schema.db'}")
    # Simulate the existing table without the two new nullable binding columns.
    from sqlalchemy.schema import CreateTable
    ddl = str(CreateTable(CheckoutOrder.__table__).compile(engine))
    ddl = "\n".join(line for line in ddl.splitlines()
                    if "provider_price_id" not in line and "provider_product_id" not in line)
    with engine.begin() as connection:
        connection.execute(text(ddl))
        connection.execute(text("""
            INSERT INTO checkout_orders
              (id, owner_id, idempotency_key, provider, provider_account_id, mode,
               sku, amount_minor, currency, reviews, duration_days, state, created_at)
            VALUES ('legacy-fixture', 1, 'legacy', 'fixture', 'fixture', 'test',
                    'old-sku', 1900, 'USD', 5, 30, 'pending', '2026-11-15 00:00:00')
        """))
    monkeypatch.setattr(database, "engine", engine)
    database.init_db()
    columns = {column["name"] for column in inspect(engine).get_columns("checkout_orders")}
    assert {"provider_price_id", "provider_product_id"} <= columns
    database.init_db()  # rerunnable, no destructive migration
    with engine.connect() as connection:
        row = connection.execute(text("""
            SELECT sku, provider_price_id, provider_product_id FROM checkout_orders
            WHERE id='legacy-fixture'
        """)).one()
    assert tuple(row) == ("old-sku", None, None)
