"""HTTP trust boundary tests. Every provider operation is an injected offline fake."""
from dataclasses import replace

import pytest

from app.config import settings
from app.models.models import CheckoutOrder, StudyPassGrant, User
from app.routers import checkout
from app.services.checkout import PaymentSnapshot
from tests.support.fake_checkout import FakeGateway


class OfflineAdapter(FakeGateway):
    def __init__(self):
        super().__init__()
        self.payload = None
        self.snapshot = None
        self.error = None

    def create_checkout(self, request):
        result = super().create_checkout(request)
        return replace(result, url=f'https://checkout.stripe.com/c/pay/{request.order_id}')

    def verify(self, payload, headers):
        self.payload = payload
        if self.error:
            raise self.error
        if headers.get('stripe-signature') != 'fixture-proof':
            raise ValueError('invalid proof')
        return self.snapshot


@pytest.fixture
def sandbox(monkeypatch):
    values = dict(STUDY_PASS_ENABLED=True, STRIPE_TEST_CHECKOUT_ENABLED=True,
        STRIPE_TEST_SECRET_KEY='sk_test_fixture', STRIPE_TEST_WEBHOOK_SECRET='whsec_fixture',
        STRIPE_TEST_ACCOUNT_ID='acct_fixture', STRIPE_TEST_RETURN_ORIGIN='https://preview.invalid.test',
        STRIPE_TEST_OFFER_SKU='fixture-pass', STRIPE_TEST_AMOUNT_MINOR=1900,
        STRIPE_TEST_CURRENCY='USD', STRIPE_TEST_WRITING_REVIEWS=5)
    for key, value in values.items():
        monkeypatch.setattr(settings, key, value)
    adapter = OfflineAdapter()
    monkeypatch.setattr(checkout, '_adapter_factory', lambda **kwargs: adapter)
    return adapter


def auth(token):
    return {'Authorization': f'Bearer {token}'}


def order(client, token, key='request-1', **extra):
    return client.post('/api/checkout/orders', headers=auth(token),
                       json={'idempotency_key': key, **extra})


def payment_for(test_db, order_id):
    row = test_db.get(CheckoutOrder, order_id)
    return PaymentSnapshot(event_id='event-1', order_id=row.id, session_id=row.session_id,
        payment_id='payment-1', sku=row.sku, amount_minor=row.amount_minor,
        currency=row.currency, state='settled')


def test_disabled_offer_hides_and_mutations_unavailable(client, auth_token, monkeypatch):
    monkeypatch.setattr(settings, 'STRIPE_TEST_CHECKOUT_ENABLED', False)
    assert client.get('/api/checkout/offer', headers=auth(auth_token)).json() == {'enabled': False, 'test_mode': True}
    assert order(client, auth_token).status_code == 503
    assert client.get('/api/checkout/orders/current', headers=auth(auth_token)).status_code == 503
    assert client.post('/api/checkout/webhook', content=b'fixture').status_code == 503


def test_offer_and_order_require_authentication(client, sandbox):
    assert client.get('/api/checkout/offer').status_code == 401
    assert client.post('/api/checkout/orders', json={'idempotency_key': 'x'}).status_code == 401
    assert client.get('/api/checkout/orders/unknown').status_code == 401
    assert client.get('/api/checkout/orders/current').status_code == 401


def test_server_offer_immutable_and_order_sanitized(client, auth_token, test_db, sandbox):
    offer = client.get('/api/checkout/offer', headers=auth(auth_token)).json()
    assert offer == dict(enabled=True, test_mode=True, sku='fixture-pass', amount_minor=1900,
                        currency='USD', reviews=5, duration_days=30)
    assert order(client, auth_token, amount_minor=1).status_code == 422
    response = order(client, auth_token)
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {'id', 'state', 'checkout_url', 'test_mode'}
    assert body['state'] == 'pending' and body['test_mode'] is True
    assert order(client, auth_token).json()['id'] == body['id']
    assert test_db.query(StudyPassGrant).count() == 0


def test_return_status_read_never_fulfills(client, auth_token, test_db, sandbox):
    oid = order(client, auth_token).json()['id']
    for _ in range(2):
        response = client.get(f'/api/checkout/orders/{oid}?paid=true&success=true', headers=auth(auth_token))
        assert response.status_code == 200 and response.json()['state'] == 'pending'
    assert test_db.query(StudyPassGrant).count() == 0


def test_order_status_hides_other_owners(client, auth_token, test_db, sandbox):
    from app.services.auth import get_current_user
    oid = order(client, auth_token).json()['id']
    other = User(email='other@invalid.test', username='other', hashed_password='fixture')
    test_db.add(other); test_db.commit()
    client.app.dependency_overrides[get_current_user] = lambda: other
    try:
        assert client.get(f'/api/checkout/orders/{oid}', headers=auth(auth_token)).status_code == 404
        assert client.get('/api/checkout/orders/current', headers=auth(auth_token)).status_code == 404
    finally:
        client.app.dependency_overrides.pop(get_current_user)


def test_current_order_recovers_cross_tab_conflict_without_provider_or_grant(
        client, auth_token, test_db, sandbox):
    path = '/api/checkout/orders/current'
    headers = auth(auth_token)
    assert client.get(path, headers=headers).status_code == 404
    oid = order(client, auth_token, key='first-tab').json()['id']
    assert order(client, auth_token, key='second-tab').status_code == 409
    for _ in range(2):
        recovered = client.get(path, headers=headers)
        assert recovered.status_code == 200
        assert recovered.headers['Cache-Control'] == 'private, no-store'
        assert recovered.json() == {'id': oid, 'test_mode': True}
    assert client.get(f'/api/checkout/orders/{oid}', headers=headers).json()['state'] == 'pending'
    assert len(sandbox.calls) == 1
    assert test_db.query(CheckoutOrder).count() == 1
    assert test_db.query(StudyPassGrant).count() == 0


def test_current_order_is_limited_to_configured_provider_scope(client, auth_token, test_db, sandbox):
    oid = order(client, auth_token).json()['id']
    row = test_db.get(CheckoutOrder, oid)
    row.provider_account_id = 'acct_other_fixture'
    test_db.commit()
    assert client.get('/api/checkout/orders/current', headers=auth(auth_token)).status_code == 404


def test_webhook_keeps_raw_bytes_and_grants_only_verified_settlement(client, auth_token, test_db, sandbox):
    oid = order(client, auth_token).json()['id']
    sandbox.snapshot = payment_for(test_db, oid)
    raw = b'{ "signed": "bytes", "spacing":  true }'
    assert client.post('/api/checkout/webhook', content=raw).status_code == 400
    assert test_db.query(StudyPassGrant).count() == 0
    response = client.post('/api/checkout/webhook', content=raw, headers={'Stripe-Signature': 'fixture-proof'})
    assert response.json() == {'received': True}
    assert sandbox.payload == raw
    assert client.get(f'/api/checkout/orders/{oid}', headers=auth(auth_token)).json()['state'] == 'fulfilled'
    assert client.post('/api/checkout/webhook', content=raw, headers={'Stripe-Signature': 'fixture-proof'}).status_code == 200
    assert test_db.query(StudyPassGrant).count() == 1


def test_pending_notification_and_mismatch_never_grant(client, auth_token, test_db, sandbox):
    oid = order(client, auth_token).json()['id']
    sandbox.snapshot = replace(payment_for(test_db, oid), state='pending')
    assert client.post('/api/checkout/webhook', content=b'x', headers={'Stripe-Signature': 'fixture-proof'}).status_code == 200
    sandbox.snapshot = replace(sandbox.snapshot, event_id='next', amount_minor=1, state='settled')
    assert client.post('/api/checkout/webhook', content=b'x', headers={'Stripe-Signature': 'fixture-proof'}).status_code == 400
    assert test_db.query(StudyPassGrant).count() == 0


@pytest.mark.parametrize('field,value', [
    ('STRIPE_TEST_SECRET_KEY', 'sk_live_never'),
    ('STRIPE_TEST_RETURN_ORIGIN', 'https://annababy.cc'),
    ('STRIPE_TEST_RETURN_ORIGIN', 'https://annababy.cc.'),
    ('STRIPE_TEST_RETURN_ORIGIN', 'https://www.annababy.cc'),
    ('STRIPE_TEST_RETURN_ORIGIN', 'https://user:pass@preview.invalid.test'),
    ('STRIPE_TEST_RETURN_ORIGIN', 'https://preview.invalid.test/extra'),
    ('STRIPE_TEST_AMOUNT_MINOR', 0), ('STRIPE_TEST_WRITING_REVIEWS', 0),
])
def test_bad_config_fails_closed(client, auth_token, sandbox, monkeypatch, field, value):
    monkeypatch.setattr(settings, field, value)
    assert client.get('/api/checkout/offer', headers=auth(auth_token)).json()['enabled'] is False
    assert order(client, auth_token).status_code == 503
    assert sandbox.calls == []


def test_too_large_webhook_rejected_before_verifier(client, sandbox):
    assert client.post('/api/checkout/webhook', content=b'x' * 131073).status_code == 413
    assert sandbox.payload is None


def test_provider_timeout_retry_preserves_order(client, auth_token, test_db, sandbox):
    sandbox.timeout_after_create_once = True
    assert order(client, auth_token).status_code == 503
    response = order(client, auth_token)
    assert response.status_code == 200
    assert test_db.query(CheckoutOrder).count() == 1
    assert sandbox.calls[0].idempotency_key == sandbox.calls[1].idempotency_key


def test_unrelated_verified_event_is_acknowledged(client, sandbox):
    sandbox.error = checkout.UnsupportedStripeEvent('fixture unrelated')
    assert client.post('/api/checkout/webhook', content=b'x', headers={'Stripe-Signature': 'fixture-proof'}).json() == {'received': True, 'ignored': True}


def test_malformed_persisted_redirect_is_sanitized(client, auth_token, test_db, sandbox):
    oid = order(client, auth_token).json()['id']
    row = test_db.get(CheckoutOrder, oid)
    row.checkout_url = 'https://checkout.stripe.com:broken/pay'
    test_db.commit()
    response = client.get(f'/api/checkout/orders/{oid}', headers=auth(auth_token))
    assert response.status_code == 503
    assert response.json()['detail'] == 'Sandbox checkout URL unavailable'

def test_non_usd_offer_agrees_with_preview_ui(client, auth_token, sandbox, monkeypatch):
    monkeypatch.setattr(settings, "STRIPE_TEST_CURRENCY", "EUR")
    headers = auth(auth_token)
    assert client.get("/api/checkout/offer", headers=headers).json()["enabled"] is False
    assert client.post("/api/checkout/orders", headers=headers,
                       json={"idempotency_key":"unavailable-currency"}).status_code == 503


def test_http_checkout_uses_native_signature_and_authoritative_mock_stripe(
        client, auth_token, test_db, sandbox, monkeypatch):
    """Exercise router, real adapter, mocked Stripe HTTPS and storage together."""
    from urllib.parse import parse_qs

    import httpx

    from app.services.stripe_test import StripeTestAdapter
    from tests.test_stripe_test_adapter import NOW, SECRET, StripeFixture, signed

    provider = StripeFixture()
    provider.session.update(status="open", payment_status="unpaid", payment_intent=None)

    def respond(request):
        if request.method == "POST":
            fields = parse_qs(request.content.decode())
            metadata = {name: fields[f"metadata[{name}]"][0]
                        for name in provider.session["metadata"]}
            provider.session.update(metadata=metadata, client_reference_id=metadata["order_id"])
            provider.payment["metadata"] = metadata
        return provider.respond(request)

    monkeypatch.setattr(settings, "STRIPE_TEST_SECRET_KEY", "sk_test_not_a_real_key")
    monkeypatch.setattr(settings, "STRIPE_TEST_WEBHOOK_SECRET", SECRET)
    with httpx.Client(transport=httpx.MockTransport(respond)) as transport:
        monkeypatch.setattr(checkout, "_adapter_factory", lambda **kwargs: StripeTestAdapter(
            **kwargs, http_client=transport, clock=lambda: NOW))
        created = order(client, auth_token)
        assert created.status_code == 200
        oid = created.json()["id"]
        status_path = f"/api/checkout/orders/{oid}"
        assert test_db.query(StudyPassGrant).count() == 0
        assert client.get(status_path + "?success=true", headers=auth(auth_token)).json()["state"] == "pending"

        raw, proof = signed()
        before = len(provider.calls)
        assert client.post("/api/checkout/webhook", content=raw + b" ", headers=proof).status_code == 400
        assert len(provider.calls) == before
        # The signed completion alone does not establish payment. The retrieved
        # provider state (not the browser, not the event body's claims) must agree.
        provider.session.update(status="complete", payment_intent="pi_fixture")
        provider.payment.update(status="processing", amount_received=0, latest_charge=None)
        assert client.post("/api/checkout/webhook", content=raw, headers=proof).status_code == 200
        assert test_db.query(StudyPassGrant).count() == 0

        provider.session.update(payment_status="paid")
        provider.payment.update(status="succeeded", amount_received=1900, latest_charge="ch_fixture")
        import json
        event = json.loads(raw)
        event["id"] = "evt_settled"
        event["type"] = "checkout.session.async_payment_succeeded"
        settled, proof = signed(event)
        assert client.post("/api/checkout/webhook", content=settled, headers=proof).status_code == 200
        assert client.post("/api/checkout/webhook", content=settled, headers=proof).status_code == 200
        assert client.get(status_path, headers=auth(auth_token)).json()["state"] == "fulfilled"
        assert test_db.query(StudyPassGrant).count() == 1


def test_signed_expiry_releases_only_exact_unpaid_order(
        client, auth_token, test_db, sandbox, monkeypatch):
    import json
    from urllib.parse import parse_qs

    import httpx

    from app.models.models import CheckoutEvent
    from app.services.stripe_test import StripeTestAdapter
    from tests.test_stripe_test_adapter import NOW, SECRET, StripeFixture, signed

    provider = StripeFixture()
    provider.session.update(status="open", payment_status="unpaid", payment_intent=None)
    created_sessions = []

    def respond(request):
        if request.method == "POST":
            fields = parse_qs(request.content.decode())
            metadata = {name: fields[f"metadata[{name}]"][0] for name in provider.session["metadata"]}
            if created_sessions:
                created_sessions.append("cs_test_replacement")
                return httpx.Response(200, json={**provider.session,
                    "id": "cs_test_replacement", "status": "open", "metadata": metadata,
                    "client_reference_id": metadata["order_id"],
                    "url": "https://checkout.stripe.com/c/pay/cs_test_replacement"})
            created_sessions.append("cs_test_fixture")
            provider.session.update(metadata=metadata, client_reference_id=metadata["order_id"])
            provider.payment["metadata"] = metadata
        return provider.respond(request)

    monkeypatch.setattr(settings, "STRIPE_TEST_SECRET_KEY", "sk_test_not_a_real_key")
    monkeypatch.setattr(settings, "STRIPE_TEST_WEBHOOK_SECRET", SECRET)
    with httpx.Client(transport=httpx.MockTransport(respond)) as transport:
        monkeypatch.setattr(checkout, "_adapter_factory", lambda **kwargs: StripeTestAdapter(
            **kwargs, http_client=transport, clock=lambda: NOW))
        reply = order(client, auth_token)
        assert reply.status_code == 200
        oid = reply.json()["id"]
        path = f"/api/checkout/orders/{oid}"
        headers = auth(auth_token)
        event = json.loads(signed()[0])
        event.update(type="checkout.session.expired", id="evt_expired")
        raw, proof = signed(event)
        webhook = "/api/checkout/webhook"

        def deliver():
            return client.post(webhook, content=raw, headers=proof)

        # A signed event for an open session and provider downtime never release it.
        assert deliver().status_code == 400
        provider.status_code = 503
        assert deliver().status_code == 503
        provider.status_code = 200
        provider.session.update(status="expired", payment_status="unpaid", payment_intent="pi_fixture")
        assert deliver().status_code == 400
        provider.session.update(payment_intent=None, payment_status="paid")
        assert deliver().status_code == 400
        provider.session.update(payment_status="unpaid")
        assert client.post(webhook, content=raw + b" ", headers=proof).status_code == 400
        assert order(client, auth_token, key="replacement").status_code == 409
        assert test_db.query(CheckoutEvent).count() == 0
        # Wrong immutable offer metadata is rejected even for an expired session.
        provider.session["metadata"]["reviews"] = "6"
        assert deliver().status_code == 400
        provider.session["metadata"]["reviews"] = "5"

        assert deliver().status_code == 200
        assert deliver().status_code == 200
        assert client.get(path, headers=headers).json() == {
            "id": oid, "state": "expired", "checkout_url": None, "test_mode": True,
        }
        current = "/api/checkout/orders/current"
        assert client.get(current, headers=headers).json()["id"] == oid
        assert order(client, auth_token).json()["state"] == "expired"
        replaced = order(client, auth_token, key="replacement")
        assert replaced.status_code == 200 and replaced.json()["id"] != oid
        assert order(client, auth_token, key="other-replacement").status_code == 409
        assert client.get(current, headers=headers).json()["id"] == replaced.json()["id"]
        assert deliver().status_code == 200

        # Contradictory late payment evidence cannot activate the old order or
        # affect the replacement. Keep a distinct audit outcome for review.
        provider.session.update(status="complete", payment_status="paid", payment_intent="pi_fixture")
        assert client.post(webhook, content=signed()[0], headers=signed()[1]).status_code == 200
        assert client.get(path, headers=headers).json()["state"] == "expired"
        assert client.get(current, headers=headers).json()["id"] == replaced.json()["id"]
        assert [e.outcome for e in test_db.query(CheckoutEvent).order_by(CheckoutEvent.id)] == [
            "expired", "expired_review",
        ]
        assert len(created_sessions) == 2
        assert test_db.query(StudyPassGrant).count() == 0
