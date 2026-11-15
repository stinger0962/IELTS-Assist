"""Independent-session checkout races on the same guarded disposable PG fixture."""
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

import pytest
from test_study_pass_postgres import pg, seed, URL

pytestmark = pytest.mark.skipif(not URL, reason='disposable PostgreSQL URL not provided')


def test_duplicate_settlements_grant_once(pg):
    from app.models.models import StudyPassGrant
    from app.services.checkout import Offer, PaymentSnapshot, start_checkout, process_notification
    from tests.support.fake_checkout import FakeGateway, FakeVerifier
    factory, _, _ = pg
    user_id, _ = seed(factory)
    gateway = FakeGateway()
    now = datetime(2026, 11, 15, 10)
    with factory() as db:
        order = start_checkout(db, user_id, 'request-1',
            Offer(sku='fixture-30-day', amount_minor=1900, currency='USD', reviews=5), gateway, now=now)
        payment = PaymentSnapshot(event_id='same-event', order_id=order.id,
            session_id=order.session_id, payment_id=f'payment-{order.id}',
            sku='fixture-30-day', amount_minor=1900, currency='USD', state='settled')
    barrier = threading.Barrier(2)
    def settle():
        with factory() as db:
            barrier.wait(timeout=5)
            result = process_notification(db, b'fixture-notification', {'fixture-proof': 'known'},
                FakeVerifier(gateway.scope, payment), now=now)
            return result.grant_id
    with ThreadPoolExecutor(max_workers=2) as workers:
        results = [future.result(timeout=20) for future in [workers.submit(settle), workers.submit(settle)]]
    assert results[0] == results[1]
    with factory() as db:
        assert db.query(StudyPassGrant).filter_by(user_id=user_id).count() == 1
        assert db.get(StudyPassGrant, results[0]).reviews_remaining == 5


def test_parallel_order_requests_do_not_create_overlapping_purchases(pg):
    from fastapi import HTTPException
    from app.services.checkout import Offer, start_checkout
    factory, _, _ = pg
    user_id, _ = seed(factory)
    offer = Offer(sku='fixture-30-day', amount_minor=1900, currency='USD', reviews=5)
    barrier = threading.Barrier(2)
    # Different request IDs must not create two pending purchases for one account.
    def start(key):
        from tests.support.fake_checkout import FakeGateway
        with factory() as db:
            barrier.wait(timeout=5)
            try:
                return ('created', start_checkout(db, user_id, key, offer, FakeGateway()).id)
            except HTTPException as exc:
                return ('rejected', exc.status_code)
    with ThreadPoolExecutor(max_workers=2) as workers:
        results = [future.result(timeout=20) for future in
                   [workers.submit(start, 'one'), workers.submit(start, 'two')]]
    assert sum(r[0] == 'created' for r in results) == 1
    assert ('rejected', 409) in results
