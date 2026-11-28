"""Disabled-by-default sandbox checkout HTTP boundary; never a grant endpoint."""
from urllib.parse import urlsplit
import re

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.config import settings
from app.database import get_db
from app.models.models import User
from app.same_origin_route import ORIGIN as REHEARSAL_ORIGIN, PREFIX as REHEARSAL_PREFIX
from app.services.auth import get_current_user
from app.services.checkout import Offer, checkout_status, current_checkout_id, process_notification, start_checkout
from app.services.stripe_test import StripeTestAdapter, UnsupportedStripeEvent

router = APIRouter()


def _adapter_factory(**kwargs):
    return StripeTestAdapter(**kwargs)


def _sandbox(request: Request | None = None):
    """Validate the entire sandbox configuration; constructors must not do I/O."""
    if not settings.STRIPE_TEST_CHECKOUT_ENABLED or not settings.STUDY_PASS_ENABLED:
        raise HTTPException(503, 'Sandbox checkout is unavailable')
    origin = settings.STRIPE_TEST_RETURN_ORIGIN
    parsed = urlsplit(origin)
    hostname = (parsed.hostname or '').rstrip('.').lower()
    production_host = hostname == 'annababy.cc' or hostname.endswith('.annababy.cc')
    # No env toggle, host header or user input can confer the factory marker.
    same_host_rehearsal = (origin == REHEARSAL_ORIGIN and request is not None
                           and request.scope.get("root_path") == REHEARSAL_PREFIX
                           and getattr(request.app.state, "same_origin_rehearsal", False) is True)
    if (not hostname or parsed.username or parsed.password or parsed.query or parsed.fragment
            or parsed.path not in ('', '/') or any(c.isspace() for c in origin)
            or (production_host and not same_host_rehearsal)
            or (parsed.scheme != 'https' and not (
                parsed.scheme == 'http' and hostname in ('localhost', '127.0.0.1', '::1')))):
        raise ValueError('An explicit local or isolated HTTPS sandbox return origin is required')
    sku = settings.STRIPE_TEST_OFFER_SKU
    amount = settings.STRIPE_TEST_AMOUNT_MINOR
    reviews = settings.STRIPE_TEST_WRITING_REVIEWS
    currency = settings.STRIPE_TEST_CURRENCY
    # The preview UI intentionally supports USD only; other currencies stay off.
    if not sku or len(sku) > 100 or amount < 1 or reviews < 1 or currency != 'USD':
        raise ValueError('The server sandbox offer is incomplete')
    if (not settings.STRIPE_TEST_SECRET_KEY.startswith('sk_test_')
            or not settings.STRIPE_TEST_WEBHOOK_SECRET.startswith('whsec_')
            or not settings.STRIPE_TEST_ACCOUNT_ID.startswith('acct_')):
        raise ValueError('Explicit sandbox credentials required')
    price_id = settings.STRIPE_TEST_PRICE_ID or None
    if price_id is not None and (
        not re.fullmatch(r"price_[A-Za-z0-9_]+", price_id) or amount != 1900 or currency != "USD"
    ):
        raise ValueError("Dashboard Price must be the selected USD19 test offer")
    callback_origin = origin.rstrip('/') + (REHEARSAL_PREFIX if same_host_rehearsal else '')
    adapter = _adapter_factory(
        api_key=settings.STRIPE_TEST_SECRET_KEY,
        webhook_secret=settings.STRIPE_TEST_WEBHOOK_SECRET,
        account_id=settings.STRIPE_TEST_ACCOUNT_ID,
        success_url=callback_origin + '/checkout/return?order_id={ORDER_ID}',
        cancel_url=callback_origin + '/checkout/cancel?order_id={ORDER_ID}',
    )
    return Offer(sku, amount, currency, reviews, provider_price_id=price_id), adapter


def _required_sandbox(request: Request):
    try:
        return _sandbox(request)
    except (ValueError, TypeError):
        raise HTTPException(503, 'Sandbox checkout is unavailable') from None


def _public_order(order):
    url = order.checkout_url
    if url:
        try:
            parsed = urlsplit(url)
            valid = (parsed.scheme == 'https' and parsed.hostname == 'checkout.stripe.com'
                     and not parsed.username and not parsed.password
                     and parsed.port in (None, 443)
                     and not any(c.isspace() for c in url))
        except ValueError:
            valid = False
        if not valid:
            raise HTTPException(503, 'Sandbox checkout URL unavailable')
    return {'id': order.id, 'state': order.state, 'checkout_url': order.checkout_url,
            'test_mode': True}


class CreateOrder(BaseModel):
    model_config = ConfigDict(extra='forbid')
    idempotency_key: str = Field(min_length=1, max_length=100)


@router.get('/offer')
def get_offer(request: Request, user: User = Depends(get_current_user)):
    try:
        offer, _ = _sandbox(request)
    except (HTTPException, ValueError, TypeError):
        return {'enabled': False, 'test_mode': True}
    return {'enabled': True, 'test_mode': True, 'sku': offer.sku,
            'amount_minor': offer.amount_minor, 'currency': offer.currency,
            'reviews': offer.reviews, 'duration_days': offer.duration_days}


@router.post('/orders')
def create_order(body: CreateOrder, request: Request, db: Session = Depends(get_db),
                 user: User = Depends(get_current_user)):
    offer, adapter = _required_sandbox(request)
    try:
        return _public_order(start_checkout(db, user.id, body.idempotency_key, offer, adapter))
    except HTTPException:
        raise
    except Exception:
        # Includes ambiguous provider timeouts. Retry SAME key; never expose key,
        # provider payload or database details to the client.
        db.rollback()
        raise HTTPException(503, 'Checkout could not be confirmed. Retry with the same request.') from None


@router.get('/orders/current')
def get_current_order(request: Request, response: Response, db: Session = Depends(get_db),
                      user: User = Depends(get_current_user)):
    _, adapter = _required_sandbox(request)
    order_id = current_checkout_id(db, user.id, adapter.scope)
    if order_id is None:
        raise HTTPException(404, 'No current checkout order', headers={'Cache-Control': 'private, no-store'})
    response.headers['Cache-Control'] = 'private, no-store'
    return {'id': order_id, 'test_mode': True}


@router.get('/orders/{order_id}')
def get_order(order_id: str, request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _required_sandbox(request)
    return _public_order(checkout_status(db, user.id, order_id))


@router.post('/webhook')
async def webhook(request: Request, db: Session = Depends(get_db)):
    _, adapter = _required_sandbox(request)
    payload = bytearray()
    async for chunk in request.stream():
        payload.extend(chunk)
        if len(payload) > 131072:
            raise HTTPException(413, 'Notification too large')
    try:
        # Provider verification and SQL are synchronous; never block the event loop.
        await run_in_threadpool(process_notification, db, bytes(payload), dict(request.headers), adapter)
    except UnsupportedStripeEvent:
        return {'received': True, 'ignored': True}
    except ValueError:
        db.rollback()
        raise HTTPException(400, 'Invalid sandbox payment notification') from None
    except Exception:
        db.rollback()
        raise HTTPException(503, 'Notification processing unavailable; retry later') from None
    return {'received': True}
