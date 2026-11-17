# Independent study-pass integration acceptance matrix

Scope: local/test only. No live provider, real payment, production DB, customer
content, external publication or credential setup. Baseline main 3df65b2.
Waiting for commander integration head before claiming implementation results.

Shared endpoint: GET /api/study-pass
Fields: enabled, status, expires_at, writing_reviews_remaining, full_mock_access.
Error for exhausted writing access: HTTP 402 with detail.code=study_pass_required.
Feature enabled: one free full writing review, then capped active-pass reviews.

## Acceptance scenarios

| ID | Setup/action | Required invariant | Evidence needed |
|---|---|---|---|
| OFF-1 | Flag absent/default false, free user | Existing writing behavior and existing VIP mock behavior unchanged; no study-pass charge/reservation | Route test and baseline assertion |
| OFF-2 | Disable after active/expired/exhausted records exist | Feature-off bypass does not mutate/erase prior entitlement history | DB before/after test |
| OFF-3 | GET status while off | Stable response contract, no implicit pass grant or mutating GET | Schema + record count |
| AUTH-1 | Unauthenticated GET/submit | 401; no entitlement/cost mutation | API test |
| AUTH-2 | User A acts on user B practice or spoofs account/role/remaining/expiry in request | Reject ownership or ignore forbidden fields; no grant/charge across users | Negative API tests |
| LEGACY-1 | Legacy VIP, enabled | Preserve agreed full-mock access; writing grandfather policy explicit | API, mock allocation tests |
| FREE-1 | Eligible free user submits valid essay | Complete full review, persisted result, exactly one free consumption | Provider mocked; DB assertions |
| FREE-2 | Same user submits a second valid essay | 402 code; provider not called, essay/practice not marked submitted; status says no reviews | Route + provider spy |
| FREE-3 | Historical completion before feature enable | No retroactive credit charge; explicit free eligibility policy | Fixture with historic rows |
| PASS-1 | Active unexpired pass, remaining >0 | Reviews succeed, exactly one committed debit per delivered saved review | API + ledger assertions |
| PASS-2 | Active pass at allowance limit | 402; no provider call or negative balance | API + DB |
| PASS-3 | Pass expires exactly at clock boundary | Expiry is exclusive, UTC-aware; no active entitlement at equality | Frozen-clock test |
| PASS-4 | Expired pass with leftover paid allowance | Paid allowance unusable; unused-free policy explicitly tested | Frozen clock + status/submit |
| PASS-5 | No paid writing allowance but active pass has full mocks | full_mock_access derives separately from writing balance | API + mock delivery |
| RACE-1 | Two independent DB sessions, same user, distinct practices, one available review | At most one request starts provider and consumes; other rejects/resolves predictably; no overspend | Actual Postgres barrier test |
| RACE-2 | Two concurrent requests for same practice | One provider charge/result; no duplicate ledger debit; deterministic duplicate/inflight response | Actual Postgres barrier test |
| RACE-3 | Different users submit concurrently | No unintended shared lock/entitlement interference | Postgres sessions |
| FAIL-1 | Invalid/too-short essay, missing/inactive practice | No study-pass debit/provider call; validation error not 402 when draft invalid | Route negative tests |
| FAIL-2 | Provider raises/timeouts/malformed output | No permanent consumption; active draft remains; retry can succeed | Mock failure and retry |
| FAIL-3 | DB write/commit fails after provider returns | No successful response without persisted result; reservation not silently available for concurrent duplicate calls; documented recovery | Fault injection |
| FAIL-4 | Process dies with reservation in progress | Document/test recovery or explicit stuck-state limitation; cannot silently grant infinite retries or permanently burn credit | Recovery test/design |
| FAIL-5 | Daily provider budget exhausted/legacy quota 429 | No paid/free study-pass consumption and correct distinct error | Route test |
| REPLAY-1 | Retry after successful response lost | Existing result can be recovered; no second consumption/provider call | Idempotency test |
| UI-1 | 402 from writing submit | Draft text, mode, practice ID and timer preserved; readable study-pass-required message; no generic object error | RTL/browser interaction |
| UI-2 | Error panel close/cancel/back | Do not remount/reset essay just to close panel; browser back/forward behavior documented | RTL/browser interaction |
| UI-3 | 401/network/503/429 | Not mislabeled payment-required; 402 does not log out | API client + view tests |
| UI-4 | Double click/repeated submit | One in-flight UI request; server still protects duplicates | RTL + backend |
| UI-5 | Successful result persists but secondary progress API fails | Render grading success, never invite a charged regrade as though initial submit failed | Mock secondary failure |
| UI-6 | Feature off/on + 430px viewport | Feature controls absent/off appropriately; status and CTA fit, usable keyboard/focus state | Local render evidence |
| NOCHARGE-1 | All visible CTAs and endpoints | No real checkout, live Stripe, provider secrets, self-grant route or client-granted pass | Route inventory + code review |
| NOCHARGE-2 | Test seed/admin fixture | Not shipped as externally callable production grant capability; no default enabled flag | Config/test review |
| SCHEMA-1 | Existing DB schema, fresh DB, deploy rollback | New state schema migration explicit; no swallowed migration failure opens grants; off doesn't require valid paid records | Migration fixture |
| PG-1 | Postgres unavailable | Paid-access path must not silently authorize via SQLite fallback/fail-open | Integration/config assertions |

## Current infrastructure observation

Workspace has no psql/postgres/initdb/pg_ctl, Docker or Podman. No existing Python
psycopg/psycopg2 driver. Debian apt lists absent; apt reports a permission-denied
config file. No installation, credential setup or bypass attempted.

Repository CI already provisions postgres:16 with ephemeral test_user/test_pass
and test_db, but backend/tests/conftest.py hardcodes sqlite:///test.db and uses a
shared file. Setting DATABASE_URL alone does not make those tests PostgreSQL.

Practical integration lane: use the existing CI PostgreSQL service with the
existing psycopg2-binary requirement. Add a separate explicitly-selected fixture
using a TEST_POSTGRES_URL, assert engine.dialect.name == 'postgresql', assert it
is the disposable expected target, and use a unique test schema/transaction.
Use genuinely separate sessions/connections plus a deterministic thread barrier
for reservation concurrency; do not count two calls on a single connection as
concurrency. Isolate schema teardown from production and normal app init. Mock
all LLM/TTS/background generation and patch the route DB dependency so no other
app engine is consulted. Ensure tests can't silently fall back to SQLite.
A CI file change needs the commander's publication lane, not this read-only QA
worker. GitHub-run tests must not deploy; only PR checks, not main push.

Do not use an embedded WASM database or SQLite as proof of actual PostgreSQL row
locking/advisory locking semantics. A locally installed official PostgreSQL can
also work if installation is separately authorized, but is not presently set up.

## Authoritative commander decisions

Feature off: enabled=false, status=none, remaining=null; legacy VIP mocks as
before. Feature on: legacy VIP bypasses allowance but remains duplicate-protected.
One lifetime free review, not retroactively charged from historical completions.
Expired pass with an unused trial can use it. Active pass remaining means only
paid allowance; zero remaining still permits full mocks. Pending duplicate: 409.
Completed unchanged essay/mode replay returns saved result; elapsed-time telemetry
is not semantic identity. Different completed answer never triggers a regrade.
Exhausted allowance: 402 detail.code=study_pass_required. No checkout/grant route.

Manual reconciliation for crashed pending work is an explicit preview limitation;
there is no automatic timer release, because a slow worker may still be grading.
