# Same-origin IELTS billing rehearsal

This is an isolated **test-mode** checkout rehearsal, not a deployment or
change to the ordinary learner app. Use only the fixed path on the existing
origin. Never use live Stripe keys, a real card, a production account or a
production database backup. Use a dedicated clean browser profile. Same-origin
storage keys and server cookies are separated by convention and safeguards,
not by browser URL-path isolation.

## Offline build and runtime contract

- Build the frontend with `npm run build -- --mode billing-test`. Use a separate
  artifact from the ordinary production build. It mounts under
  `/__ielts-billing-test/`, uses the matching API path, and persists a separate
  browser token, preferences and checkout attempts. Do not put it in the
  production document root. If exercising Listening, copy only a synthetic
  fixture audio file to the test artifact's `audio/` directory.
- Launch with `python -m app.same_origin_sandbox` from a clean directory without
  dotenv files. Provide the draft backend via `PYTHONPATH` and the absolute test
  artifact path via `IELTS_BILLING_TEST_DIST`. It listens at `127.0.0.1:8011`.
  The launcher checks the dedicated loopback PostgreSQL instance at
  `127.0.0.1:55432`, database and role both `ielts_billing_test`, explicit
  `DATABASE_URL` with password and bounded `connect_timeout`, and an independent
  random secret of at least 32 characters. Verify independent ownership and
  pins before any schema writes. Seed only a synthetic learner and exercises.
- Set `SITE_URL` and `STRIPE_TEST_RETURN_ORIGIN` to exactly
  `https://annababy.cc`, and `DAILY_GENERATION_ENABLED=false`. Start with both
  `STUDY_PASS_ENABLED` and `STRIPE_TEST_CHECKOUT_ENABLED` false. Only enable both
  in this runtime after the isolation checks. Enabled startup needs the selected
  $19 one-time sandbox Price, account, test secret and destination signing
  secret, supplied by secure operator entry, never chat, source or logs.
- The protected UI starts on Practice. The surface excludes registration/reset,
  deliberate review/generation, speech, email, and generic production APIs. Any
  unneeded interactive feature is outside this rehearsal.

## Live site change gate

Nothing here installs or reloads Nginx. Before any change to the real site, an
operator with existing access must inspect the actual running TLS vhost, verify
its client-IP trust boundary and location precedence, reserve the loopback
ports, and separately approve the exact reversible configuration change.

The test namespace needs an operator-only edge gate. The **only** public
exception is the raw request URI
`POST /__ielts-billing-test/api/checkout/webhook`, without a query or aliases;
it still requires Stripe's test signature and matching provider state to
fulfill. Preserve the original request URI to the dedicated loopback service,
pin its upstream Host to `annababy.cc`, and do not forward cookies or XSRF
headers. No test path may rewrite or fall back to production; no ordinary
production path should resolve to this service. If the real operator access
gate cannot be verified, do not expose any test namespace.

With flags off, verify the actual TLS site from both allowed and denied client
contexts, including malformed methods/paths and unchanged production home/API
health. Confirm public webhook reachability without successful execution. Then
enable only this isolated runtime, confirm the pre-created Stripe Price, and
exercise $19 test checkout and signed completion. Capture status only, not
credentials, Checkout URLs or account/learner details. Use a second tab on the
same sandbox learner to check recovery: an order conflict offers **Find existing
test order**, which opens the owned status page in the rehearsal namespace. It
must not start another Stripe session. A lost or unverified lookup must not
offer to start over. A pending order with no resumable session still requires
operator reconciliation.

Set a hard end time for the rehearsal. Before withdrawing it, stop creating
sessions. In the Stripe sandbox, reconcile only the exact Checkout Session IDs
created by the rehearsal. Verify test mode and fixture ownership, and expire
any still open (Stripe's default lifetime is 24 hours). Confirm the terminal
states and any expected webhook deliveries before removing the test location,
service, database, learner and destination. Never touch unrelated sessions.
Do not merge or deploy the ordinary app for this test.
