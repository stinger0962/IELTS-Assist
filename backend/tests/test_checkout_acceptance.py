from dataclasses import replace
from datetime import datetime, timedelta

import pytest
from fastapi import HTTPException

from app.config import settings
from app.models.models import StudyPassGrant, User
from app.services.checkout import (
    Offer, GatewayScope, PaymentSnapshot, start_checkout, checkout_status,
    process_notification,
)
from tests.support.fake_checkout import FakeGateway, FakeVerifier

NOW = datetime(2026, 11, 15, 10)
OFFER = Offer(sku='fixture-30-day', amount_minor=1900, currency='USD', reviews=5)


@pytest.fixture(autouse=True)
def enabled(monkeypatch):
    monkeypatch.setattr(settings, 'STUDY_PASS_ENABLED', True)


def begin(db, user, gateway=None, key='request-1'):
    gateway = gateway or FakeGateway()
    return start_checkout(db, user.id, key, OFFER, gateway, now=NOW), gateway


def snapshot(order, **changes):
    value = PaymentSnapshot(event_id='event-1', order_id=order.id,
        session_id=order.session_id, payment_id=f'payment-{order.id}',
        sku=OFFER.sku, amount_minor=OFFER.amount_minor, currency=OFFER.currency,
        state='settled')
    return replace(value, **changes)


def notify(db, gateway, payment, now=NOW):
    return process_notification(db, b'fixture-notification', {'fixture-proof': 'known'},
                                FakeVerifier(gateway.scope, payment), now=now)


def test_pending_and_browser_return_do_not_grant(test_db, test_user):
    order, gateway = begin(test_db, test_user)
    assert checkout_status(test_db, test_user.id, order.id).grant_id is None
    assert test_db.query(StudyPassGrant).count() == 0
    notify(test_db, gateway, snapshot(order, state='pending'))
    assert test_db.query(StudyPassGrant).count() == 0
    assert gateway.calls[0].amount_minor == OFFER.amount_minor
    assert gateway.calls[0].reviews == OFFER.reviews


def test_owner_and_request_idempotency(test_db, test_user):
    order, gateway = begin(test_db, test_user)
    again, _ = begin(test_db, test_user, gateway)
    assert again.id == order.id
    assert len(gateway.sessions) == 1
    other = User(email='outsider@invalid.test', username='outsider', hashed_password='fixture')
    test_db.add(other); test_db.commit()
    with pytest.raises(HTTPException) as e:
        checkout_status(test_db, other.id, order.id)
    assert e.value.status_code == 404
    with pytest.raises((ValueError, HTTPException)):
        start_checkout(test_db, test_user.id, 'request-1', replace(OFFER, reviews=999), gateway)


def test_ambiguous_checkout_retries_same_provider_key(test_db, test_user):
    gateway = FakeGateway()
    gateway.timeout_after_create_once = True
    with pytest.raises(TimeoutError):
        begin(test_db, test_user, gateway)
    order, _ = begin(test_db, test_user, gateway)
    assert len(gateway.sessions) == 1
    assert gateway.calls[0].idempotency_key == gateway.calls[1].idempotency_key == order.id
    assert test_db.query(StudyPassGrant).count() == 0


def test_settlement_grants_once_without_resetting_expiry_or_balance(test_db, test_user):
    order, gateway = begin(test_db, test_user)
    payment = snapshot(order)
    settled = notify(test_db, gateway, payment)
    grant = test_db.get(StudyPassGrant, settled.grant_id)
    assert grant.user_id == test_user.id
    assert grant.reviews_remaining == 5
    assert grant.expires_at == NOW + timedelta(days=30)
    grant.reviews_remaining = 2
    test_db.commit()
    notify(test_db, gateway, payment, now=NOW + timedelta(days=1))
    notify(test_db, gateway, replace(payment, event_id='event-2'), now=NOW + timedelta(days=2))
    test_db.refresh(grant)
    assert test_db.query(StudyPassGrant).count() == 1
    assert grant.reviews_remaining == 2
    assert grant.expires_at == NOW + timedelta(days=30)


@pytest.mark.parametrize('change', [
    {'amount_minor': 1}, {'currency': 'EUR'}, {'sku': 'other'},
    {'session_id': 'other-session'}, {'order_id': 'missing-order'},
])
def test_mismatched_settlement_never_grants(test_db, test_user, change):
    order, gateway = begin(test_db, test_user)
    with pytest.raises((ValueError, HTTPException)):
        notify(test_db, gateway, snapshot(order, **change))
    test_db.rollback()
    assert test_db.query(StudyPassGrant).count() == 0


@pytest.mark.parametrize('scope', [
    GatewayScope(provider='other', account_id='fixture-merchant', mode='test'),
    GatewayScope(provider='fixture', account_id='other', mode='test'),
    GatewayScope(provider='fixture', account_id='fixture-merchant', mode='live'),
])
def test_verifier_scope_must_match_order(test_db, test_user, scope):
    order, gateway = begin(test_db, test_user)
    gateway.scope = scope
    with pytest.raises(ValueError):
        notify(test_db, gateway, snapshot(order))
    test_db.rollback()
    assert test_db.query(StudyPassGrant).count() == 0


def test_unverified_payload_is_not_accepted(test_db, test_user):
    order, gateway = begin(test_db, test_user)
    with pytest.raises(ValueError):
        process_notification(test_db, b'untrusted', {}, FakeVerifier(gateway.scope, snapshot(order)))
    assert test_db.query(StudyPassGrant).count() == 0


def test_full_refund_revokes_and_late_success_never_restores(test_db, test_user):
    order, gateway = begin(test_db, test_user)
    payment = snapshot(order)
    settled = notify(test_db, gateway, payment)
    grant_id = settled.grant_id
    refunded = replace(payment, event_id='refund-1', state='refunded', refunded_minor=1900)
    notify(test_db, gateway, refunded)
    notify(test_db, gateway, refunded)
    notify(test_db, gateway, replace(payment, event_id='late-success'))
    grant = test_db.get(StudyPassGrant, grant_id)
    test_db.refresh(grant)
    assert grant.revoked_at is not None
    assert test_db.query(StudyPassGrant).count() == 1


def test_refund_before_settlement_never_grants(test_db, test_user):
    order, gateway = begin(test_db, test_user)
    payment = snapshot(order)
    notify(test_db, gateway, replace(payment, state='refunded', refunded_minor=1900))
    notify(test_db, gateway, replace(payment, event_id='late-success'))
    assert test_db.query(StudyPassGrant).count() == 0


@pytest.mark.parametrize('state, refunded', [('failed', 0), ('disputed', 0), ('refunded', 500)])
def test_non_settled_or_partial_refund_does_not_grant(test_db, test_user, state, refunded):
    order, gateway = begin(test_db, test_user)
    notify(test_db, gateway, snapshot(order, state=state, refunded_minor=refunded))
    assert test_db.query(StudyPassGrant).count() == 0


def test_vip_or_active_pass_cannot_start_second_purchase(test_db, test_user):
    test_user.role = 'vip'; test_db.commit()
    with pytest.raises(HTTPException):
        begin(test_db, test_user)
    test_db.rollback(); test_user.role = 'free'; test_db.commit()
    order, gateway = begin(test_db, test_user)
    notify(test_db, gateway, snapshot(order))
    with pytest.raises(HTTPException):
        begin(test_db, test_user, key='new-request')


def test_grant_failure_rolls_back_event_and_allows_retry(test_db, test_user, monkeypatch):
    from app.services import checkout
    from app.models.models import CheckoutEvent
    order, gateway = begin(test_db, test_user)
    payment = snapshot(order)
    grant = checkout.grant_study_pass
    def fail_after_insert(*args, **kwargs):
        grant(*args, **kwargs)
        raise RuntimeError('synthetic failure after entitlement insert')
    monkeypatch.setattr(checkout, 'grant_study_pass', fail_after_insert)
    with pytest.raises(RuntimeError):
        notify(test_db, gateway, payment)
    assert test_db.query(StudyPassGrant).count() == 0
    assert test_db.query(CheckoutEvent).count() == 0
    assert checkout_status(test_db, test_user.id, order.id).grant_id is None
    monkeypatch.setattr(checkout, 'grant_study_pass', grant)
    assert notify(test_db, gateway, payment).grant_id is not None


def test_old_event_retry_with_evolved_snapshot_is_noop(test_db, test_user):
    order, gateway = begin(test_db, test_user)
    payment = snapshot(order)
    notify(test_db, gateway, payment)
    notify(test_db, gateway, replace(payment, state='refunded', refunded_minor=1900))
    assert test_db.query(StudyPassGrant).one().revoked_at is None
    notify(test_db, gateway, replace(payment, event_id='new-refund', state='refunded', refunded_minor=1900))
    assert test_db.query(StudyPassGrant).one().revoked_at is not None


def test_live_mode_gateway_is_rejected_before_call(test_db, test_user):
    gateway = FakeGateway(GatewayScope(provider='fixture', account_id='fixture-merchant', mode='live'))
    with pytest.raises(ValueError):
        begin(test_db, test_user, gateway)
    assert gateway.calls == []


def test_event_immutable_correlation_cannot_change(test_db, test_user):
    order, gateway = begin(test_db, test_user)
    payment = snapshot(order)
    notify(test_db, gateway, payment)
    with pytest.raises(ValueError):
        notify(test_db, gateway, replace(payment, payment_id='other-payment'))
    test_db.rollback()
    assert test_db.query(StudyPassGrant).count() == 1


def test_insecure_checkout_url_rejected_but_intent_retryable(test_db, test_user):
    from app.services.checkout import CheckoutSession
    class BadGateway(FakeGateway):
        def create_checkout(self, request):
            good = super().create_checkout(request)
            return CheckoutSession(session_id=good.session_id, url='javascript:alert(1)')
    bad = BadGateway()
    with pytest.raises(ValueError):
        begin(test_db, test_user, bad)
    gateway = FakeGateway()
    gateway.sessions = bad.sessions
    order, _ = begin(test_db, test_user, gateway)
    assert order.checkout_url.startswith('https://checkout.invalid.test/')
    assert gateway.calls[0].idempotency_key == bad.calls[0].idempotency_key
    assert test_db.query(StudyPassGrant).count() == 0
