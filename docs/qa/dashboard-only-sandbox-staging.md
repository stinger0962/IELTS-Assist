# Dashboard-only sandbox verification: proposed staging runbook

Status: design only. No staging URL, host, tunnel, database, secrets or Stripe
endpoint has been provisioned or verified. This document does not authorize
external setup, publication, payment/refund actions or production changes.
No Stripe CLI is needed for the procedure below.

## Least-effort isolated deployment shape

Use one **explicitly approved** temporary runtime with a disposable PostgreSQL
database and one fixed HTTPS origin. Serve the built React frontend and reverse
proxy `/api/` to FastAPI on the same origin. Prefer the owner's existing approved
staging service if available; otherwise obtain a concrete hosting choice and
scope before creating a project, exposing a tunnel, provisioning infrastructure,
or spending money. A temporary HTTPS tunnel is an alternative only after the
operator approves the specific exposure and the local runtime can remain awake.
Do not repurpose the production VPS or modify its proxy/firewall/DB.

The repository has a production VPS deployment workflow, not a staging deployment
or Docker composition. The inspected dot runtime has no Docker/Postgres binaries
and no known inbound HTTPS address. GitHub's ephemeral CI PostgreSQL service is
not a persistent staging database or public webhook host. Consequently the URL
cannot honestly be supplied until an approved staging runtime exists.

Expose only `/api/checkout/webhook` publicly through the staging edge. Keep the
UI and all other API paths behind the chosen staging access control, and retain
normal application authentication/ownership checks. The webhook exception must
not bypass Stripe signature verification. Stripe cannot satisfy an interactive
login, CAPTCHA or HTTP Basic auth prompt. Route exact POSTs without redirects,
retain raw bytes and `Stripe-Signature`, and use a valid TLS certificate. Do not
re-use or weaken production access controls. A low-volume sandbox still needs
bounded request size/timeouts and accessible delivery diagnostics.

## Runtime isolation before any exposure

- Check out the exact tested PR commit, not moving `main`; do not trigger the
  production deploy workflow. Build frontend with `/api` as the API base. Route
  `/checkout/return` and `/checkout/cancel` through the SPA fallback.
- Use a new disposable PostgreSQL database, independent credentials and fresh
  app signing key. Seed synthetic test accounts only. Never copy a production
  `.env`, database, customer rows, essays, recordings, cookies or provider keys.
- Inject secrets via the approved runtime's secret store/environment at process
  start, not source control, frontend `VITE_*` variables, build args, commands,
  log output or chat. Persist test orders long enough to retry webhook delivery.
- Keep checkout disabled during boot. Check database health and runtime isolation
  before enabling `STUDY_PASS_ENABLED` and `STRIPE_TEST_CHECKOUT_ENABLED`.
- Supply `STRIPE_TEST_SECRET_KEY` (`sk_test_...`), the corresponding sandbox
  `STRIPE_TEST_ACCOUNT_ID`, and **that Dashboard endpoint's**
  `STRIPE_TEST_WEBHOOK_SECRET` (`whsec_...`). Inject these through the approved
  secret path; never substitute a live key or another endpoint's secret.
- Set `STRIPE_TEST_RETURN_ORIGIN` to the fixed isolated HTTPS origin. The code
  intentionally rejects annababy.cc and its subdomains. A new host-generated
  staging origin avoids production DNS changes. If a temporary origin changes,
  update both runtime return origin and the Dashboard destination before testing.
- Set explicit fixture offer SKU, positive integer amount in minor units,
  currency and review allowance using the current `STRIPE_TEST_*` configuration.
  These are sandbox values, not an approved live price. Verify the displayed
  offer matches Checkout exactly; the browser does not send price data.
- For a Dashboard-created catalog Price, set `STRIPE_TEST_PRICE_ID` to that
  non-secret sandbox Price ID. For this smoke test the related Product must
  be named `IELTS 30-Day Study Pass` and its Price must be an active,
  one-time flat US$19.00 price. The app checks the catalog before any
  provider session is created; leave Product metadata blank. Confirm those
  catalog details in the Dashboard before attempting a test order.
- Set `DAILY_GENERATION_ENABLED=false` so isolated staging does not start
  the scheduled AI worker. Use no AI, TTS or email credentials, keep test data
  synthetic, and avoid unrelated exercise-generation endpoints. This smoke
  test needs no other provider credentials.

## Stripe Dashboard setup, after authorization

In the selected sandbox/test environment, open **Workbench > Webhooks > Create
an event destination**. Select **Your account**, **Snapshot** payloads, and a
compatible snapshot API version. This adapter expects snapshot event objects,
not the Dashboard's recommended Thin format. Match the currently tested adapter
API version rather than copying a stale value from this runbook.

Register `https://<approved-staging-origin>/api/checkout/webhook`. The endpoint's
settings supply its signing secret. Configure only supported events; a broad
“All events” subscription is unnecessary. The adapter's exact supported list is:

1. `checkout.session.completed`
2. `checkout.session.async_payment_succeeded`
3. `checkout.session.async_payment_failed`
4. `charge.refunded`
5. `refund.created`
6. `refund.updated`
7. `refund.failed`
8. `charge.dispute.created`
9. `charge.dispute.updated`
10. `charge.dispute.closed`

For the **first card-only success test**, `checkout.session.completed` is enough.
Add `charge.refunded` for the next full-refund revocation check. Other listed
refund/dispute and delayed-payment events broaden coverage later; delayed
methods are not currently offered by the card-only adapter. Generic
`payment_intent.succeeded` and thin events are not substitutes for the supported
Checkout event. A generic Dashboard fixture without the app-created order and
metadata is not an end-to-end fulfillment test and may correctly be rejected.

## Verification sequence without CLI

1. Log into a synthetic staging account and inspect the server offer. Start
   Checkout **from the app**, so a local pending order, immutable offer snapshot
   and order metadata exist. Cancel once and verify no pass was granted. Reuse
   the app's pending order/checkout rather than creating unsupported parallel
   purchases; canceled/failed order reconciliation remains an explicit boundary.
2. Complete a card payment using Stripe's documented test-card values, never a
   real card. Confirm the Dashboard shows a test payment in the intended
   account. Browser success alone is not evidence of fulfillment.
3. In Dashboard **Event deliveries**, inspect the real event and delivery
   response. Verify a successful delivery plus the app's authenticated owned
   order status `fulfilled`, exactly one grant, expected expiry/allowance, and
   full-mock access. No need to display customer data or secret values.
4. Use Dashboard **Resend** on that event. Verify no extra grant, reset expiry
   or restored consumed reviews. Dashboard permits resending recent events;
   use its current UI rather than shell tooling.
5. After separately approved **test** refund action, confirm a new refund event
   reaches staging and blocks future paid access while preserving saved study.
   A late old success event must not restore access. Partial refunds/disputes
   enter review, not automatic proportional credits or live refund initiation.
6. Stop on a mismatch, timeout or repeated rejection. Inspect sanitized status
   and event IDs privately; do not dump payloads or secrets. This implementation
   performs bounded provider reconciliation inline: delayed provider responses
   can cause webhook retries. A real asynchronous delivery queue is a separate
   scale/reliability enhancement, not proven by these sandbox checks.

## Cleanup and evidence

Record the tested commit, sandbox account identifier, event IDs and assertions
privately. Do not claim live readiness from mock/CI success or a Dashboard 200
alone. The sandbox approval does not authorize switching live mode, changing
production, or publishing real pricing. At the approved end of the test window,
disable the staging offer and endpoint/exposure according to that authorization;
preserve test evidence and do not permanently delete storage without the required
approval. Invalidate temporary credentials only within approved cleanup scope.

## Official references checked November 15, 2026

- [Stripe webhooks](https://docs.stripe.com/webhooks): Dashboard destination setup,
  snapshot selection, public HTTPS, signature secret, delivery view and Resend.
- [Checkout fulfillment](https://docs.stripe.com/checkout/fulfillment.md?ui=full-page):
  webhook-backed fulfillment and duplicate-safe processing.
- [Stripe testing](https://docs.stripe.com/testing): sandbox-only payments and test
  cards; never real card details.

## Later live-launch preparation: interrupted writing reviews

Before live launch, rehearse the [stale writing reservation recovery runbook](../operations/writing-reservation-recovery.md)
in separately authorized isolated staging with a synthetic account and stub grader.
Confirm stopped-worker evidence, exact attempt identity, no saved result, one-time
credit restoration, and rejection of a late stale completion. This is **not a
prerequisite for the first Stripe sandbox webhook test** above. Do not release
reservations solely because of age or use this checklist as production approval.
