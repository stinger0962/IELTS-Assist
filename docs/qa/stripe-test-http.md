# Stripe test-mode HTTP boundary

This milestone defaults off and is not a production payment integration.
No provider credentials are included. Unit tests use injected offline doubles.

An independently authorized sandbox must set both `STUDY_PASS_ENABLED` and
`STRIPE_TEST_CHECKOUT_ENABLED`, plus its own `STRIPE_TEST_SECRET_KEY` (test-only),
`STRIPE_TEST_WEBHOOK_SECRET`, `STRIPE_TEST_ACCOUNT_ID`, and explicit
`STRIPE_TEST_RETURN_ORIGIN`. The origin is HTTPS staging or HTTP loopback;
`annababy.cc` and its subdomains are rejected. It is not inferred from request
Host/Origin or the production `SITE_URL`. Server-only offer configuration is
`STRIPE_TEST_OFFER_SKU`, `STRIPE_TEST_AMOUNT_MINOR`, USD-only
`STRIPE_TEST_CURRENCY`, and `STRIPE_TEST_WRITING_REVIEWS`. Incomplete config
hides the offer and rejects order/webhook operations. No change to deployment
configuration is included or implied.

- Authenticated `GET /api/checkout/offer` reports availability and the server
  offer. No secrets or merchant identifiers appear in the response.
- Authenticated `POST /api/checkout/orders` accepts only `idempotency_key`.
  Extra fields, including client price, are rejected. Retry the same key after
  an ambiguous provider failure. It does not grant on checkout creation.
- Authenticated `GET /api/checkout/orders/{id}` returns only the owned order's
  `id`, `state`, sanitized `checkout_url`, and `test_mode`. Query flags do not
  change state or grant access. Another account receives 404.
- `POST /api/checkout/webhook` preserves raw signed bytes and passes only through
  the Stripe adapter verifier before settlement processing. It limits the body
  to 128 KiB, runs synchronous provider/DB work outside the event loop, and
  acknowledges unrelated *verified* events without creating grants.
- Return/cancel URLs are fixed to `/checkout/return?order_id=...` and
  `/checkout/cancel?order_id=...` at the configured origin. Browser return is not
  proof of payment. Only verified successful settlement can fulfill an order.

Run `python -m pytest tests/test_checkout_http.py` from `backend` with local
fixture environment settings. These tests do not contact Stripe, make charges,
prove deployed configuration, or validate a live sandbox account. Signature and
provider wire-format tests belong to the adapter lane. Approval to develop this
branch does not authorize enabling it in production.
