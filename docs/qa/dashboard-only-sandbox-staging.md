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

## Verify independent staging access before requesting a Stripe delivery

Use one HTTPS origin for UI and API. If the approved access layer supports it,
use an independent browser operator-session cookie (host-only, Secure, HttpOnly;
SameSite=Lax for a compatible top-level GET return). Verify the actual browser
return and cookie expiry behavior. The operator cookie grants entry to staging,
not an app identity or paid entitlement. Preserve the app's `Authorization:
Bearer` header; don't require HTTP Basic in it or substitute the cookie for it.

An expired/missing operator cookie on an API request should produce a clearly
distinguishable JSON denial (prefer 403), not an HTML login redirect or the
app's 401. The frontend logs out on 401, so the edge denial should not erase an
otherwise valid app login. Re-authenticating to the gate is a separate step.
The public exception is **only POST to the literal
`/api/checkout/webhook`**: no prefix matching, alternate methods, redirects,
trailing slash or normalized/encoded aliases. Keep backend ports, alternate
hosts, API docs, health, media and all other app routes gated or denied. Any
separate gate login route is not a blanket application exemption.

| Probe | Expected outcome |
| --- | --- |
| No operator cookie on staging UI/API | Gate entry or clear API denial; no app data |
| Operator cookie only on app-authenticated API | Edge admits; app authentication still rejects |
| Valid app bearer only | Edge denies; bearer cannot bypass operator gate |
| Valid cookie and bearer | Normal app identity, ownership and entitlement checks |
| Expired operator cookie with valid app bearer | Edge denial does not clear app login |
| Top-level GET checkout return/cancel | Confirm cookie behavior and app login; only owned order status, no access or settlement from URL |
| Canonical unsigned webhook POST with sandbox disabled | Reaches the app without a gate challenge or redirect, fails closed without state change |
| Same unsigned POST after authorized sandbox enablement | App rejects missing signature, no state change |
| Wrong method or neighboring/encoded path | No gate bypass or redirect into exemption |
| Direct upstream or alternate host | No bypass of staging access policy |

Pass the original body bytes and `Stripe-Signature` without replacing headers,
parsing/reserializing or redirecting the request. The handler checks sandbox
configuration before verifying signatures, so a disabled response is expected
before enablement. Successful authenticated delivery is a later sandbox test,
not implied by this preflight. Keep cookies and credentials out of logs.


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
- Before starting FastAPI (its startup initializes schema), use the intended
  runtime configuration and a read-only connection check to confirm that the
  configured PostgreSQL host and credentials point only at the disposable
  staging database. Verify its provisioned identity, not just that a server
  answers; no production database or credential should be reachable by this
  runtime. If identity cannot be confirmed, stop before starting the app.
- Start with `STUDY_PASS_ENABLED=false` and
  `STRIPE_TEST_CHECKOUT_ENABLED=false`. A healthy `/api/health` is not enough:
  the health route runs `SELECT 1`, and a failed PostgreSQL connection can
  fall back to SQLite when Study Pass is disabled. From an operator-only check
  of the **serving process's SQLAlchemy engine**, require dialect
  `postgresql` and match the connected database to the provisioned disposable
  instance (for example, check `SELECT current_database()` against its expected
  name and confirm the instance identity separately). Checking an independent
  psql session or reading the intended `DATABASE_URL` is not evidence of the
  process's active binding. If not verifiable, or if the engine fell back to
  SQLite, stop before seeding. Repeat the check after the flags-on restart,
  before any test checkout. Capture pass/fail privately; do not publish a debug
  endpoint or print the DSN, credentials, or connection exceptions that might
  include them.
- Set `SITE_URL` to the staging HTTPS origin before auth testing. Password
  reset uses it independently of `STRIPE_TEST_RETURN_ORIGIN` and defaults to
  the production site. Use prepared synthetic accounts for checkout; do not
  trigger password reset as part of the smoke test. Without an email provider,
  the reset route can write the token-bearing link to app logs.
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

## Optional fail-closed staging entry point

After an operator has approved and independently verified the disposable runtime,
use `uvicorn app.staging:create_app --factory` from `backend/` instead of
`app.main:app`. Do not change the production service entry point. This factory
validates before importing `app.main`, whose module-level `init_db()` initializes
schema, and checks the same engine/session binding the app subsequently uses.
Each serving process reruns the check, including after the flags-on restart.

Supply the following nonsecret pins through the staging runtime environment:
`STAGING_EXPECTED_DB_HOST`, `STAGING_EXPECTED_DB_PORT`,
`STAGING_EXPECTED_DB_NAME`, and `STAGING_EXPECTED_DB_USER`. They must be the
operator-confirmed disposable instance, port, database and role, not values
blindly copied from a production connection string. The configured URL and
active engine must both match; a read-only transaction must return the expected
database and role. No schema or seed operation occurs before these checks pass.

The factory requires matching non-production HTTPS `SITE_URL` and
`STRIPE_TEST_RETURN_ORIGIN`, both checkout flags off or both on, disabled daily
generation, and no OpenAI, Azure speech, Google TTS or email credentials. It
rejects inherited nonempty `PG*` environment variables and database URL routing
options. Only `connect_timeout` (required, 1–15 seconds) and optional `sslmode`
are supported as URL query parameters. Keep the approved TLS policy; do not
weaken it to satisfy the guard. A deployment needing additional certificate or
proxy options needs a reviewed extension, not a bypass. Provision secrets through
the runtime's approved secret mechanism, never in shell arguments or screenshots.

The factory returns fixed failure messages without printing DSNs or driver
exceptions and rejects an already-imported database/application. It adds no
HTTP endpoint and makes no Stripe calls. This is a configuration/connected-role
check, **not proof of infrastructure ownership, account isolation, DNS integrity,
or absence of production data**. Pinning a production database by mistake is
still unsafe. Operator verification of the instance and an empty disposable
database remains mandatory. Startup-order tests use fakes in fresh processes;
the disposable PostgreSQL CI lane also exercises the connected-identity query
against its local fixture. Neither establishes that a staging deployment, TLS
gate, database or checkout works.

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
   Entitlement does not populate an empty mock pool. Verify actual card delivery
   and listening media separately using the [full-mock acceptance checklist](full-mock-delivery.md).
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
