# Offline checkout acceptance

This stage exercises internal application order logic against test-only, injected
adapters. It neither charges money nor proves a real provider integration. No fake
payment endpoint, callback, or grant action is registered on the application.

## Required invariants

- The server supplies the immutable SKU/amount/currency/allowance snapshot.
- A browser return, pending session, failed payment or authorization cannot grant.
- Owner and idempotency isolation survives retry; an ambiguous session-creation
  timeout remains retryable with the same order, never a new purchase.
- Only a verified settled event matching the expected provider/account/mode,
  session/payment identifiers, amount and currency can fulfill an order.
- Event recording, order fulfillment and entitlement grant are atomic. Repeated
  settlement can never extend expiry, top up consumed reviews or create a new grant.
- A confirmed full refund revokes future use and preserves past study history.
  Late success cannot resurrect that order. Duplicate refunds remain idempotent.
- Partial refunds and disputes require reconciliation, not invented credit math.
- Active-pass and legacy VIP accounts cannot purchase another overlapping pass.

## Evidence limits

SQLite fixture tests exercise the synchronous state machine, not production
locking. PostgreSQL race tests require the explicitly opt-in disposable CI
service. Skipped PostgreSQL tests are not a pass. Neither test type validates
real webhook signatures, account eligibility, provider settlement semantics,
customer checkout UX, or actual payments. Those remain separate launch gates.
