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

## Dashboard-created USD19 Price (optional, backward compatible)

The owner may create the sandbox Product and Price in Stripe Dashboard without any
CLI. The Product must be named **IELTS 30-Day Study Pass**, active and in test mode.
Its selected Price must be active, fixed per-unit, one-time, USD1900 minor units,
without custom amount or quantity transformation. No Product metadata entry is
required. Configure its nonsecret ID through STRIPE_TEST_PRICE_ID only on the
server; the browser cannot provide a Price. No actual Price ID is committed.

Before creating Checkout, the adapter verifies the expected sandbox merchant and
retrieves the exact selected Price with expanded Product. It rejects wrong account,
live objects, other product names, inactive objects, recurring/tiered/custom pricing
and any amount/currency mismatch. It creates a one-time session using that Price ID,
quantity one and explicit USD currency, never inline price_data on this path.

The order stores the selected Price ID before requesting a session, and binds the
verified Product ID when attaching the session. Both IDs enter server-created
Session/PaymentIntent metadata and the authoritative payment snapshot. Fulfillment
compares them with the **stored order**, not current environment configuration. A
new configured Price cannot reinterpret an existing order. Retrying an old key with
a different offer returns conflict; reading the existing order remains possible.

A Product rename or Price/Product archival after checkout does not invalidate a
legitimate settlement/refund: the immutable IDs, amount, currency and relationships
must still match. Creation requires active/name checks; settlement does not.
A mismatch in Price or Product identity always fails closed.

Legacy inline orders retain null bindings, their existing SKU checks and original
event fingerprints. Two additive nullable-column migrations preserve those records;
no data backfill or destructive migration is needed. The mocked tests include
schema upgrade/re-run, wrong-app/mode/account, config changes, archival, immutable
binding, and the legacy inline path. Actual sandbox acceptance still needs its
separately authorized smoke run.

References: [Price retrieval](https://docs.stripe.com/api/prices/retrieve),
[Price object](https://docs.stripe.com/api/prices/object),
[Checkout creation](https://docs.stripe.com/api/checkout/sessions/create).
