# IELTS Stripe test adapter: offline-verified boundary

This adapter is a **test-mode integration implementation**, not an activated payment
service. No account, product, key, webhook endpoint or payment is created by its
constructor or tests. It adds no HTTP app routes. The separate route lane must keep
checkout disabled by default and require explicit isolated test configuration.
Ziwei's payment configuration is not read or reused.

## Scope and trust

- Test secret keys only (sk_test_); fixed API host, HTTPS, explicit API version,
  no followed redirects, no Connect account switching. Before an operation it reads
  the authenticated account and compares its ID with the configured test merchant.
- Native v1 webhook signature is checked against **unchanged raw bytes** with HMAC
  SHA-256, constant-time comparison and a 300-second timestamp tolerance in both
  directions. Multiple v1 signatures permit endpoint-secret rotation; unsigned
  header debug fields have no authority. Invalid or stale signatures cause no API
  calls. Event/object live mode and account context are rejected.
- A signed event is a wakeup, not settlement proof. The adapter retrieves current
  Checkout Session, its single expanded product line, PaymentIntent, latest charge
  and paginated refunds. Their identities, test mode, amount/currency, order/user/SKU
  metadata and relationships must agree. The checkout service separately verifies
  those facts against its immutable local order.
- A completed checkout with an unpaid/processing payment stays pending. Settlement
  requires paid/complete session, successful full PaymentIntent receipt and a fully
  captured, paid charge. Successful full refunds are terminal through the checkout
  service; partial refunds/disputes require review. Pending refunds cannot produce a
  new settlement. A failed refund alone does not undo a successful payment.
- Returned hosted checkout URLs must use exactly checkout.stripe.com over HTTPS
  without userinfo or nonstandard ports. Return URLs are server-controlled; HTTP is
  allowed only for literal loopback hosts. The router additionally excludes the
  production domain for this milestone. The adapter substitutes escaped order ID
  into the fixed return/cancel templates, never client redirect destinations.
- One positive-price line, one-time payment, card-only; no recurring plan, promotion,
  adaptive price, tax or shipping behavior is supported. Tax/discount/shipping totals
  differing from zero are rejected during verification, not silently charged/granted.
- Failed, unsupported or ambiguous states are not auto-refunded. Provider errors are
  sanitized; raw responses, keys and customer data are never logged by this module.

## Retry bound and reconciliation

The existing order UUID remains the provider idempotency key. Because Stripe API v1
may prune keys after 24 hours, an ambiguous local order without an attached session
cannot automatically create/retry after 23 hours (or with a future creation time).
It requires reconciliation. Existing attached sessions remain retrievable through
owner-scoped order status. A new key cannot bypass the account's pending-order slot.

Creating an open Checkout Session may legitimately return a null PaymentIntent.
Creation does not require or grant one. Verification handles only the subscribed
completed/async/refund/dispute event types, and rejects a missing PI in those payment
flows rather than synthesizing one. Null totals are also not payable proof.

## Offline verification and remaining limits

The adapter tests use httpx.MockTransport and synthetic HMAC secrets/events only.
They exercise exact request bytes, immutable creation data, signatures/timestamps,
wrong account/mode, redirect restrictions, pending vs paid, identity/amount/SKU
mismatch, full/partial/pending/failed refund and retry boundaries.
The real Stripe transport, actual hosted UI, account permissions, webhook delivery,
and provider-side schema compatibility still require a separately authorized isolated
sandbox smoke test. Passing these fixtures does not claim live payments work.

## Official sources reviewed November 15, 2026

- [Endive changelog](https://docs.stripe.com/changelog/endive): October 28 GA release.
  Requests pin 2026-10-28.endive, also shown by the current API reference.
- [Create Checkout Session](https://docs.stripe.com/api/checkout/sessions/create)
  and [Session object](https://docs.stripe.com/api/checkout/sessions/object).
- [Fulfillment](https://docs.stripe.com/checkout/fulfillment.md?ui=full-page):
  duplicate/concurrent delivery and asynchronous payment completion.
- [Webhook verification](https://docs.stripe.com/events/manage-webhook-endpoints):
  exact raw payload and v1 HMAC, not debug metadata.
- [Session lookup by PaymentIntent](https://docs.stripe.com/api/checkout/sessions/list).
- [Refund pagination](https://docs.stripe.com/api/refunds/list).
- [Idempotency](https://docs.stripe.com/api/idempotent_requests?lang=python):
  same-key retries and API v1 key-retention limits.
