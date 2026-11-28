"""Provider-neutral OFFLINE/TEST checkout foundation. No routes or concrete provider.

The injected verifier is the trust boundary: verify signature and merchant/test scope,
then retrieve authoritative payment state before producing a snapshot. A success URL,
client payload or checkout-completed event alone must NEVER become a settled snapshot.
Only normalized identifiers/statuses are persisted; no card or customer billing data.
"""
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from hashlib import sha256
import json
from typing import Protocol
from uuid import uuid4
from urllib.parse import urlsplit

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.models import CheckoutEvent, CheckoutOrder, StudyPassGrant, User
from app.services.study_pass import _active_pass, grant_study_pass


@dataclass(frozen=True)
class Offer:
    sku: str
    amount_minor: int
    currency: str
    reviews: int
    duration_days: int = 30
    provider_price_id: str | None = None


@dataclass(frozen=True)
class GatewayScope:
    provider: str
    account_id: str
    mode: str = "test"


@dataclass(frozen=True)
class CheckoutSession:
    session_id: str
    url: str
    provider_price_id: str | None = None
    provider_product_id: str | None = None


@dataclass(frozen=True)
class CheckoutRequest:
    order_id: str
    user_id: int
    sku: str
    amount_minor: int
    currency: str
    reviews: int
    duration_days: int
    idempotency_key: str
    provider_price_id: str | None = None


@dataclass(frozen=True)
class PaymentSnapshot:
    event_id: str
    order_id: str
    session_id: str
    payment_id: str
    sku: str
    amount_minor: int
    currency: str
    state: str  # pending | settled | refunded | failed | disputed
    refunded_minor: int = 0
    provider_price_id: str | None = None
    provider_product_id: str | None = None


@dataclass(frozen=True)
class ExpiredCheckoutSnapshot:
    event_id: str
    order_id: str
    session_id: str
    user_id: int
    sku: str
    amount_minor: int
    currency: str
    reviews: int
    duration_days: int
    provider_price_id: str | None = None
    provider_product_id: str | None = None


class Gateway(Protocol):
    scope: GatewayScope

    def create_checkout(self, order: CheckoutRequest) -> CheckoutSession: ...


class Verifier(Protocol):
    scope: GatewayScope

    def verify(self, payload: bytes, headers: dict) -> PaymentSnapshot | ExpiredCheckoutSnapshot: ...


def _scope(scope):
    if scope.mode != "test" or not scope.provider or not scope.account_id:
        raise ValueError("Only explicitly scoped test providers are supported")
    if len(scope.provider) > 50 or len(scope.account_id) > 100:
        raise ValueError("Provider scope is too long")


def _validate_offer(offer):
    if offer.provider_price_id is not None and (
        not isinstance(offer.provider_price_id, str) or not offer.provider_price_id
        or len(offer.provider_price_id) > 200
    ):
        raise ValueError("Invalid provider Price binding")
    if (not offer.sku or len(offer.sku) > 100
            or type(offer.amount_minor) is not int or offer.amount_minor < 1
            or type(offer.reviews) is not int or offer.reviews < 1
            or offer.duration_days != 30
            or len(offer.currency) != 3 or not offer.currency.isascii()
            or not offer.currency.isalpha() or offer.currency != offer.currency.upper()):
        raise ValueError("Invalid server offer snapshot")


def _matches_scope(order, scope):
    return (order.provider, order.provider_account_id, order.mode) == (
        scope.provider, scope.account_id, scope.mode)


def _matches_offer(order, offer):
    return (order.sku, order.amount_minor, order.currency, order.reviews, order.duration_days,
            order.provider_price_id) == (
        offer.sku, offer.amount_minor, offer.currency, offer.reviews, offer.duration_days,
        offer.provider_price_id)


def checkout_status(db: Session, user_id: int, order_id: str):
    order = db.query(CheckoutOrder).filter_by(id=order_id, owner_id=user_id).first()
    if not order:
        raise HTTPException(404, "Checkout order not found")
    return order


def current_checkout_id(db: Session, user_id: int, scope: GatewayScope) -> str | None:
    """Read the owned slot or most recent expired receipt, without provider I/O."""
    _scope(scope)
    orders = db.query(CheckoutOrder.id, CheckoutOrder.state).filter_by(
        owner_id=user_id, provider=scope.provider,
        provider_account_id=scope.account_id, mode=scope.mode,
    )
    active = orders.filter_by(active_owner_id=user_id).first()
    if active:
        return active.id
    latest = orders.order_by(CheckoutOrder.created_at.desc(), CheckoutOrder.id.desc()).first()
    return latest.id if latest and latest.state == "expired" else None


def _lock_owner(db, user_id):
    user = db.query(User).filter_by(id=user_id).with_for_update().first()
    if not user:
        raise HTTPException(404, "Account not found")
    return user


def start_checkout(db: Session, user_id: int, idempotency_key: str,
                   offer: Offer, gateway: Gateway, now=None):
    """Persist intent, call injected test gateway, then attach its session.

    Ambiguous gateway failure leaves intent pending. Retry the SAME key; gateway
    receives the stable order UUID, never a fresh provider idempotency key.
    This function owns its commits and must use a dedicated application session.
    """
    _scope(gateway.scope)
    _validate_offer(offer)
    if not idempotency_key or len(idempotency_key) > 100:
        raise ValueError("A bounded idempotency key is required")
    now = now or datetime.utcnow()
    try:
        user = _lock_owner(db, user_id)
        order = db.query(CheckoutOrder).filter_by(
            owner_id=user_id, idempotency_key=idempotency_key).first()
        if order:
            if not _matches_offer(order, offer) or not _matches_scope(order, gateway.scope):
                raise HTTPException(409, "Idempotency key was used for another offer")
            if order.session_id or order.state != "pending":
                db.commit()
                return order
            # Stripe may prune idempotency keys after 24 hours. An unresolved
            # attempt must not create another remote session after that window.
            if order.created_at > now or now - order.created_at >= timedelta(hours=23):
                raise HTTPException(409, "Checkout creation requires reconciliation")
        else:
            if user.role == "vip" or _active_pass(db, user_id, now):
                raise HTTPException(409, "An active entitlement already exists")
            previous = db.query(CheckoutOrder).filter_by(active_owner_id=user_id).first()
            if previous:
                # Fulfilled, expired entitlements can free a reserved slot here.
                # Unpaid Checkout expiry releases its slot only via verified proof.
                grant = db.get(StudyPassGrant, previous.grant_id) if previous.grant_id else None
                if (previous.state == "fulfilled" and grant is not None
                        and grant.expires_at <= now and grant.revoked_at is None):
                    previous.active_owner_id = None
                    db.flush()
                else:
                    raise HTTPException(409, "Another checkout requires reconciliation")
            order = CheckoutOrder(
                id=str(uuid4()), owner_id=user_id, active_owner_id=user_id,
                idempotency_key=idempotency_key, provider=gateway.scope.provider,
                provider_account_id=gateway.scope.account_id, mode=gateway.scope.mode,
                sku=offer.sku, amount_minor=offer.amount_minor, currency=offer.currency,
                reviews=offer.reviews, duration_days=offer.duration_days,
                provider_price_id=offer.provider_price_id,
                state="pending", created_at=now,
            )
            db.add(order)
        db.commit()
        order_id = order.id
        request = CheckoutRequest(order_id, user_id, order.sku, order.amount_minor,
                                  order.currency, order.reviews, order.duration_days, order_id,
                                  order.provider_price_id)
        # Attribute refresh after commit can start a read transaction. Close it too.
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "Concurrent checkout; retry the original idempotency key") from exc
    except Exception:
        db.rollback()
        raise
    # Intentionally outside a database transaction/row lock.
    session = gateway.create_checkout(request)
    if not session.session_id or len(session.session_id) > 200 or not session.url:
        raise ValueError("Gateway did not return a valid session")
    parsed = urlsplit(session.url)
    if (parsed.scheme != "https" or not parsed.hostname
            or parsed.username is not None or parsed.password is not None
            or any(char.isspace() for char in session.url)):
        raise ValueError("Checkout URL must be HTTPS without embedded credentials")
    try:
        order = db.query(CheckoutOrder).filter_by(id=order_id).with_for_update().one()
        if not _matches_scope(order, gateway.scope):
            raise ValueError("Gateway scope changed")
        if order.session_id and order.session_id != session.session_id:
            raise ValueError("Gateway changed session for an idempotent checkout")
        if session.provider_price_id != order.provider_price_id:
            raise ValueError("Gateway changed the immutable Price binding")
        if order.provider_price_id is not None:
            if (not session.provider_product_id or len(session.provider_product_id) > 200
                    or (order.provider_product_id is not None
                        and order.provider_product_id != session.provider_product_id)):
                raise ValueError("Gateway changed the Product binding")
            order.provider_product_id = session.provider_product_id
        elif session.provider_product_id is not None:
            raise ValueError("Unexpected Product binding on legacy inline checkout")
        if order.state != "expired":
            order.session_id, order.checkout_url = session.session_id, session.url
        db.commit()
        return order
    except Exception:
        db.rollback()
        raise


def _validate_snapshot(snapshot):
    for name in ("event_id", "order_id", "session_id", "payment_id", "sku"):
        value = getattr(snapshot, name)
        if not isinstance(value, str) or not value or len(value) > 200:
            raise ValueError("Invalid verified payment identifier")
    if (snapshot.state not in {"pending", "settled", "refunded", "failed", "disputed"}
            or type(snapshot.amount_minor) is not int or snapshot.amount_minor < 1
            or type(snapshot.refunded_minor) is not int
            or not 0 <= snapshot.refunded_minor <= snapshot.amount_minor):
        raise ValueError("Invalid verified payment state")


def _expire_checkout(db: Session, scope: GatewayScope, snapshot: ExpiredCheckoutSnapshot, now):
    """Release only the exact verified, unpaid Stripe order; keep its audit trail."""
    for value in (snapshot.event_id, snapshot.order_id, snapshot.session_id, snapshot.sku):
        if not isinstance(value, str) or not value or len(value) > 200:
            raise ValueError("Invalid verified checkout expiry")
    if (any(type(value) is not int or value < 1 for value in
            (snapshot.user_id, snapshot.reviews, snapshot.amount_minor))
            or snapshot.duration_days != 30):
        raise ValueError("Invalid verified checkout expiry offer")
    fingerprint = sha256(json.dumps({"expiry": asdict(snapshot)}, sort_keys=True).encode()).hexdigest()
    try:
        owner_id = db.query(CheckoutOrder.owner_id).filter_by(id=snapshot.order_id).scalar()
        if owner_id is None or owner_id != snapshot.user_id:
            raise ValueError("Unknown checkout expiry order")
        _lock_owner(db, owner_id)
        order = db.query(CheckoutOrder).filter_by(id=snapshot.order_id).with_for_update().one()
        if (not _matches_scope(order, scope) or order.session_id != snapshot.session_id
                or (order.sku, order.amount_minor, order.currency, order.reviews, order.duration_days,
                    order.provider_price_id, order.provider_product_id) != (
                    snapshot.sku, snapshot.amount_minor, snapshot.currency, snapshot.reviews,
                    snapshot.duration_days, snapshot.provider_price_id, snapshot.provider_product_id)):
            raise ValueError("Verified expiry does not match the immutable order")
        existing = db.query(CheckoutEvent).filter_by(
            provider=scope.provider, provider_account_id=scope.account_id, mode=scope.mode,
            event_id=snapshot.event_id).first()
        if existing:
            if existing.order_id != order.id or existing.fingerprint != fingerprint:
                raise ValueError("Expiry event identifier was reused with different content")
            db.commit()
            return order
        outcome = "expiry_ignored"
        if (order.state == "pending" and order.active_owner_id == owner_id
                and order.payment_id is None and order.grant_id is None):
            order.state, order.checkout_url, order.active_owner_id = "expired", None, None
            outcome = "expired"
        db.add(CheckoutEvent(provider=scope.provider, provider_account_id=scope.account_id,
                             mode=scope.mode, event_id=snapshot.event_id, order_id=order.id,
                             fingerprint=fingerprint, outcome=outcome, processed_at=now))
        db.commit()
        return order
    except Exception:
        db.rollback()
        raise


def process_notification(db: Session, payload: bytes, headers: dict,
                         verifier: Verifier, now=None):
    """Process ONLY through an injected verified-snapshot boundary, atomically.

    The verifier may reject invalid signatures or return unavailable; errors propagate
    without marking any event processed. Retried delivery is safe. No external refund
    calls occur here. A confirmed full refund revokes future use, retaining history.
    """
    _scope(verifier.scope)
    snapshot = verifier.verify(payload, headers)
    now = now or datetime.utcnow()
    if isinstance(snapshot, ExpiredCheckoutSnapshot):
        return _expire_checkout(db, verifier.scope, snapshot, now)
    _validate_snapshot(snapshot)
    # Current authoritative state can change between retries of the SAME immutable
    # event. Deduplicate its identity, not mutable settlement/refund observations.
    # A distinct refund event (or separately identified reconciliation) applies a
    # subsequent state change; re-delivery of a processed event is always a no-op.
    identity = asdict(snapshot)
    identity.pop("state")
    identity.pop("refunded_minor")
    # Preserve fingerprints already stored for legacy inline orders before these
    # optional fields existed.
    for field in ("provider_price_id", "provider_product_id"):
        if identity[field] is None:
            identity.pop(field)
    fingerprint = sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
    try:
        # Match the owner lock ordering used during checkout creation.
        owner_id = db.query(CheckoutOrder.owner_id).filter_by(id=snapshot.order_id).scalar()
        if owner_id is None:
            raise ValueError("Unknown payment order")
        owner = _lock_owner(db, owner_id)
        order = db.query(CheckoutOrder).filter_by(id=snapshot.order_id).with_for_update().one()
        if (not _matches_scope(order, verifier.scope)
                or order.session_id != snapshot.session_id
                or (order.sku, order.amount_minor, order.currency) != (
                    snapshot.sku, snapshot.amount_minor, snapshot.currency)
                or (order.payment_id is not None and order.payment_id != snapshot.payment_id)
                or order.provider_price_id != snapshot.provider_price_id
                or order.provider_product_id != snapshot.provider_product_id):
            raise ValueError("Verified payment does not match the immutable order")
        existing = db.query(CheckoutEvent).filter_by(
            provider=verifier.scope.provider, provider_account_id=verifier.scope.account_id,
            mode=verifier.scope.mode, event_id=snapshot.event_id).first()
        if existing:
            if existing.order_id != order.id or existing.fingerprint != fingerprint:
                raise ValueError("Payment event identifier was reused with different content")
            db.commit()
            return order
        outcome = "observed"
        if order.state != "expired":
            order.payment_id = snapshot.payment_id
        if order.state == "expired":
            # A contradictory later payment observation needs human review but
            # cannot grant a pass, reopen this checkout or touch its replacement.
            outcome = ("expired_ignored" if snapshot.state == "pending" and not snapshot.refunded_minor
                       else "expired_review")
        elif order.state == "refunded":
            # Terminal: delayed settlement can never resurrect this entitlement.
            outcome = "terminal_ignored"
        elif snapshot.state == "refunded" and snapshot.refunded_minor == order.amount_minor:
            if order.grant_id:
                grant = db.get(StudyPassGrant, order.grant_id)
                grant.revoked_at = now
            order.state, order.refunded_at = "refunded", now
            outcome = "revoked"
        elif snapshot.refunded_minor > 0 or snapshot.state in {"refunded", "disputed", "failed"}:
            # Unsupported partial refund/dispute/failure: manual reconciliation.
            order.state = "review"
            outcome = "review"
        elif snapshot.state == "settled" and order.state == "pending":
            if owner.role == "vip" or _active_pass(db, order.owner_id, now):
                order.state = "review"
                outcome = "review"
            else:
                grant = grant_study_pass(db, order.owner_id, f"order:{order.id}",
                                         order.reviews, now=now)
                order.grant_id = grant.id
                order.state, order.fulfilled_at = "fulfilled", now
                outcome = "granted"
        elif order.state == "review":
            outcome = "review"
        db.add(CheckoutEvent(
            provider=verifier.scope.provider, provider_account_id=verifier.scope.account_id,
            mode=verifier.scope.mode, event_id=snapshot.event_id, order_id=order.id,
            fingerprint=fingerprint, outcome=outcome, processed_at=now,
        ))
        db.commit()
        return order
    except Exception:
        db.rollback()
        raise
