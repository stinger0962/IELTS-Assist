# Disposable PostgreSQL study-pass acceptance tests

These tests intentionally live outside `backend/tests` so its SQLite-only
`conftest.py` is not loaded. They do not import `app.main` or `app.database`, and
never call OpenAI, TTS, email, checkout or production. They test entitlement
transactions directly, not HTTP/frontend behavior.

Use only the existing **disposable local CI Postgres 16 service** and the normal
backend test dependencies. From the repo root:

```sh
IELTS_TEST_POSTGRES_ALLOW_DISPOSABLE=1 \
IELTS_TEST_POSTGRES_URL='postgresql+psycopg2://test_user:test_pass@127.0.0.1:5432/test_db' \
python -m pytest backend_pg_tests -v --tb=short
```

The example credentials are the repository's ephemeral CI fixture, never real
credentials. No supplied URL means skipped, **not passed**. A supplied URL must
be loopback, `test_user` / `test_db`, port 5432 or 5433, with no URL query options,
and the explicit disposable opt-in. Otherwise it fails. Database-reported user
and name are verified before writes. Every test creates a randomized schema,
selects it via connection search_path, creates ORM tables there, then drops only
that schema. No application initializer or SQLite fallback is used. Statement,
lock, connection and barrier timeouts bound hangs. This is not authorization to
point the test at another database or change persistent credentials.

Concurrency uses independent connections/sessions. The last-paid-credit race
forces both sessions to read the pre-debit grant before either proceeds. Other
cases cover first-trial creation races, duplicate same-card requests (including
legacy VIP), idempotent failure release, stale-token protection, finalization
rollback, expiry boundaries, free fallback, paid zero balance with mock access,
feature-off behavior, and cross-user ownership. There are 11 cases including
the parameterized VIP case. They must be run against the integrated core.

Do not report success based on default SQLite CI. No PostgreSQL runtime was
available in the initial local QA environment; initial local verification was
syntax compilation and collection with 11 explicit skips only.
