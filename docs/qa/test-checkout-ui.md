# Stripe test checkout UI

This milestone is test-only and defaults to unavailable. It uses authenticated
server offers, creates an owned order, and can redirect only to HTTPS
checkout.stripe.com without credentials/port. There are no client-side grants,
real-card fields, locally chosen prices, or successful-return shortcuts.

## Contract

- GET /api/checkout/offer: off/unconfigured is disabled; a valid enabled offer
  includes test_mode:true, sku, positive integer amount_minor, currency USD,
  positive integer reviews and duration_days:30.
- POST /api/checkout/orders: only idempotency_key; retries/reloads in the same tab reuse the account-
  and offer-scoped sessionStorage key, and repeated in-flight clicks are ignored.
- GET /api/checkout/orders/{UUID}: owned state only, never a fulfillment write.
  Accepted states: pending, fulfilled, refunded, review. Responses require
  test_mode:true and matching order ID.
- Browser return and cancel use /checkout/return or /checkout/cancel with
  order_id. Neither the URL nor cancel action changes access. Refresh is manual
  or bounded (12 polls at five seconds); terminal states stop automatic polling.
- Authentication interruptions offer login with a narrowly validated returnTo
  restricted to those two local routes and a UUID. Other redirect values are
  rejected in favor of the default dashboard.

## Draft protection

An unfinished writing draft disables checkout and instructs the learner to keep
or copy the essay and use the Practice list when ready. The async create-order
response checks current draft state again before routing, preventing a typing-
during-checkout race. No checkout URL is shown while the draft is present.
This does not introduce browser storage of essays or cross-navigation draft
persistence; unrelated existing Back/refresh behavior is unchanged.

## Verification

52 frontend tests pass (22 checkout checks), including disabled/live offers,
test pricing/localization, unsafe URLs, duplicate clicks, same-key retries,
draft guard and mid-request edits, logout during checkout, pending/fulfilled/
canceled returns, unauthenticated/unauthorized order checks, and login redirects.
TypeScript + Vite production build passes, with pre-existing bundle-size warning.
Repository lint remains unavailable because no ESLint flat configuration exists.

No external Stripe browser, real API keys, real checkout sessions, production
backend, or customer data were used. Browser rendering and integrated real
sandbox checkout must be verified separately before activation; no E2E claim.

## Local fixture review checklist

At 430px then desktop, using mocked APIs only:
1. Off/unconfigured leaves the existing “Purchasing is not available” message.
2. Test offer shows exact USD amount/review limit and test-only/no-charge notice.
3. Test click opens only a stubbed approved URL; failure remains recoverable.
4. Typed essay disables checkout and survives errors/partial requests.
5. Return remains pending until the owned status endpoint says fulfilled.
6. Cancel never invokes create/fulfill; no “paid” inference from query strings.
7. Login expiry preserves only the permitted return path.

## Interrupted checkout recovery

Before sending a create request, persist only an opaque UUID request key and its
creation timestamp in sessionStorage. The storage key scopes it to the local
account ID and offer SKU/amount/currency/reviews/duration. No essay, auth token,
hosted URL, card data, order snapshot or other secret is stored.

Remount/reload/cancel return in the same tab shows a previous-attempt notice.
Nothing resumes automatically. The first click reuses the same key to retrieve
the owned pending order; a separate Resume click opens the validated URL.
The cancel/return page can likewise resume only a server-read owned pending
order, with an explicit click and without POSTing another order.

The attempt has a 24-hour usable lifespan. Expired/malformed storage and
pending-order conflicts stop with recovery copy; they NEVER rotate into a
fresh request automatically. A stale server attempt may require operator
resolution or the original order-return link. Session storage is tab-scoped:
closing the tab or clearing storage loses this recovery context. A new tab may
hit a pending-order conflict and must resolve that rather than retrying a
fresh payment. Account switches cannot reuse another account's key.
