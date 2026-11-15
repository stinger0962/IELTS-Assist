"""Test-only adapters. Never imported by app modules or exposed as HTTP routes."""
from app.services.checkout import CheckoutSession, GatewayScope


class FakeGateway:
    def __init__(self, scope=None):
        self.scope = scope or GatewayScope(provider='fixture', account_id='fixture-merchant', mode='test')
        self.sessions = {}
        self.calls = []
        self.timeout_after_create_once = False

    def create_checkout(self, order):
        self.calls.append(order)
        session = self.sessions.setdefault(order.idempotency_key, CheckoutSession(
            session_id=f'fixture-session-{order.order_id}',
            url=f'https://checkout.invalid.test/{order.order_id}'))
        if self.timeout_after_create_once:
            self.timeout_after_create_once = False
            raise TimeoutError('synthetic ambiguous timeout after creation')
        return session


class FakeVerifier:
    """Opaque fixtures stand in for an already authenticated authoritative result.

    This deliberately does not implement or claim any provider signature algorithm.
    """
    def __init__(self, scope, snapshot):
        self.scope = scope
        self.snapshot = snapshot

    def verify(self, payload, headers):
        if payload != b'fixture-notification' or headers != {'fixture-proof': 'known'}:
            raise ValueError('unknown fixture proof')
        return self.snapshot
