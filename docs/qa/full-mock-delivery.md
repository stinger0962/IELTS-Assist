# Synthetic full-mock delivery acceptance

`backend/tests/test_full_mock_delivery.py` uses an isolated SQLite test database,
synthetic authenticated account and internal test-only entitlement grant. It
inserts original toy exercises into that test database only. There is no staging
seed command or public grant endpoint here. Scheduler and replenishment are
suppressed; outbound socket connections fail. No payment, AI or speech provider
is contacted. No runtime behavior is changed.

Run from a disposable, unique working directory because shared `conftest.py`
uses relative `test.db`. Set `DATABASE_URL` to another disposable SQLite path
**before pytest imports the app** (app startup creates tables). For example,
with `$REPO` the checkout and `$PYTEST` its installed pytest executable:

```sh
QA_DIR=$(mktemp -d)
cd "$QA_DIR"
DATABASE_URL="sqlite:///$QA_DIR/app.db" DAILY_GENERATION_ENABLED=false \
  "$PYTEST" "$REPO/backend/tests/test_full_mock_delivery.py" -q
```

The tests prove API delivery of complete view-shaped payloads, one assignment
on repeated listing, scoring/submission, history recovery and duplicate-submit
rejection. Reading uses three sections with grouped questions; listening uses
four sections with flat completion questions. These small original fixtures
are not calibrated IELTS exams. Existing study-pass tests separately cover
free/expired/disabled gates.

A clean database with an active entitlement can still contain **no full mock
inventory**. Entitlement success alone does not prove the paid feature is usable.
Do not enable real generation jobs or provision provider credentials merely to
make this test pass.

For the proposed next content/scoring acceptance contract, see
[full-mock content and scoring](full-mock-content-scoring.md). That proposal is
not implemented by these delivery tests and does not validate their legacy band
expectations or 30-question Reading fixture as official-format scoring.

## Audio and staging limits

The wave-generated 0.1-second tone proves only the local media contract: fixture
URL returns the expected MIME type and valid WAV bytes. A temporary StaticFiles
mount exists only inside the test and is removed afterward. The application
itself does not mount `/audio`. This does not prove deployed proxy/static
mapping, byte-range seeking, browser playback, speech relevance or exam quality.

After separately authorized isolated staging exists, verify its external static
mapping and access controls, then open one original reading mock and one
listening mock in the actual browser. Check passage/questions, audio playback
and seeking, submission and result reopening with a synthetic pass holder.
Confirm free/expired users remain gated. Keep production data and valid AI
credentials out; keep scheduled generation and request-driven replenishment
suppressed or safely stubbed. Any staging fixture import needs an explicitly
verified disposable target. This document does not assert staging exists or
authorize a deployment, tunnel, account, credential or external mutation.
