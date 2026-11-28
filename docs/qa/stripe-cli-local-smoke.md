# Local Stripe sandbox smoke test

This is the no-hosting first check for the study pass. Keep the browser,
frontend, backend and Stripe CLI on the same machine and use only loopback
interfaces. Use a new PostgreSQL database and role expressly for this test, with
synthetic users. Do not reuse a production database, environment file, API key
or localhost tunnel. Do not create a Dashboard webhook destination or deploy
anything for this test.

## Stripe access

1. Use the official Stripe CLI on the test machine. Pair it using
   [Stripe's browser login](https://docs.stripe.com/cli/login), limiting it to the
   **IELTS Assist Sandbox**. Verify that the current CLI environment is that
   sandbox, not live mode or a different test environment.
2. Configure the Python app separately with the matching sandbox-only Stripe API
   key and account ID. CLI pairing does not configure the app. Use private
   local environment/secret entry, not source, chat, screenshots or logs.
3. Subscribe to the Checkout completion only for the initial test:

   ```sh
   stripe listen --events-from @self --events checkout.session.completed --forward-to http://127.0.0.1:8001/api/checkout/webhook
   ```

   Use this listener's signing secret for the app, not a signing secret from
   the Dashboard. Do not include the listener startup banner in shared output.

## Run the local copy

Use a clean working directory without a `.env` file, with the repository's
`backend` directory on `PYTHONPATH`, and run `python -m app.local_sandbox`
with the project's backend dependencies installed. Use a new local
`ielts_sandbox` PostgreSQL database owned only by a dedicated
`ielts_sandbox` login role; the launcher requires `127.0.0.1:5432` and a
bounded `connect_timeout` in `DATABASE_URL`. Do not point a port forward at
another database. Set a separate local `SECRET_KEY` for learner sign-in.

Supply these settings to the backend process only:

- `SITE_URL` and `STRIPE_TEST_RETURN_ORIGIN`: both `http://127.0.0.1:5173`.
- `STUDY_PASS_ENABLED=true`, `STRIPE_TEST_CHECKOUT_ENABLED=true`,
  `DAILY_GENERATION_ENABLED=false`.
- `STRIPE_TEST_OFFER_SKU=ielts-30-day-study-pass`,
  `STRIPE_TEST_AMOUNT_MINOR=1900`, `STRIPE_TEST_CURRENCY=USD`,
  `STRIPE_TEST_WRITING_REVIEWS=5`, and the sandbox `STRIPE_TEST_PRICE_ID`.
- `STRIPE_TEST_ACCOUNT_ID`, `STRIPE_TEST_SECRET_KEY`, and
  `STRIPE_TEST_WEBHOOK_SECRET` from the authorized sandbox/listener. Do not
  load AI, speech or email credentials. Do not export secrets to Vite.

With the frontend dependencies installed, start the separate frontend process
with `node frontend/scripts/local-sandbox.mjs` from the repository root.
Neither launcher accepts alternate bind addresses. The backend launcher skips
background practice-pool replenishment but still serves and saves seeded
exercises. Writing's local prompt fallback still works. This is not an egress
block; avoid explicit AI review, generation, speech and email during this
checkout smoke test.

## Pass/fail checklist

- Start the guarded local backend and frontend. Confirm UI is served from
  `http://127.0.0.1:5173` and its API is proxied to the loopback backend.
- Register a fresh synthetic learner such as `learner@example.com` at
  `/register`, then open `/practice` and expand the study-pass details. Confirm no existing pass and check the
  server offer matches the dedicated USD19 sandbox Price, five reviews and
  30 days. Enable only the opt-in study-pass and checkout flags.
- Create an order from the app and cancel at Stripe Checkout. The return page
  must not grant a pass. Resume that pending order for the success case; the
  app deliberately preserves the idempotency key on cancellation.
- Complete that sandbox Checkout Session using an
  [official Stripe test card](https://docs.stripe.com/testing). Do not use a
  real card or substitute `stripe trigger`; a generic trigger does not carry
  the order metadata created by this app.
- Check the signed notification returned HTTP 200 and the same learner now sees
  an active 30-day pass and five reviews. Refresh the page and confirm the order
  and entitlement remain active. Report only states and counts, with no
  account/session IDs, secrets, learner emails or checkout URLs.
- A local pass tests checkout and fulfillment through the CLI. It does **not**
  certify delivery to a registered HTTPS endpoint, hosted access controls or
  production readiness. Test delivery on the intended deployment separately.
