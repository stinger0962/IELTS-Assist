# Read-only learner activity audit

`learner_activity_30d.sql` answers a narrower, more useful question than page hits:
**How many accounts completed exercises, and came back on another date?**
It is not a bot detector, a revenue forecast, or permission to access production.
Nothing here is wired into the app, CI deployment, a cron job, or billing.

## Safety and operation

An authorized operator can run it with **existing read-only database access**.
Do not create credentials, export the database, use the application startup, or
import `app.database` to run this audit. That module can initialize tables and
fall back to a different database. Confirm the target is the intended Postgres
primary or an acceptably fresh read replica. Use an existing `PGSERVICE`/secure
connection setup, not a password in command-line arguments, chat or this repo.

Example from the repository root, with a previously configured read-only service:

```sh
PGSERVICE=ielts_readonly psql -X -q --csv \
  -v report_as_of_utc='2026-11-15T00:00:00Z' \
  -v exclude_user_ids='1,2' \
  -f ops/reports/learner_activity_30d.sql
```

The IDs above are **examples**, not identified owner accounts. Supply confirmed
operator/test account IDs privately. The exclusion parameter must be explicitly
provided; use `-v exclude_user_ids=''` only when no exclusions are intended, and
label the result accordingly. No email-address lookup is included. Invalid
non-numeric exclusions fail the query instead of silently including accounts.
Use an explicit UTC `Z` timestamp for the report endpoint. The start is exactly
30 days earlier; start is inclusive and end is exclusive. The session timezone
is UTC. The schema's naive timestamps are interpreted as UTC, matching the
submission routes' `datetime.utcnow()` writes; validate that assumption for any
legacy/imported data before interpreting date boundaries.

The script enforces a read-only transaction, 30-second statement timeout,
3-second lock timeout and final rollback. It outputs **one aggregate row only**:
no account identifiers, email, IP, essay, audio, answers, scores or credentials.
Keep even aggregate results private; very small cohorts are not anonymization.
Do not run `EXPLAIN ANALYZE`, create indexes or raise timeouts automatically if
the query is too expensive. A timeout is a reason to review an approved replica
or execution window, not to change production. `psql -X` ignores local psqlrc.

## What the columns mean

- `signups`: non-excluded users created in the window. A signup alone is weak
  evidence of demand; it can be a test or automated account.
- `active_learners_with_completion`: distinct non-excluded accounts with at least
  one `user_practices.submitted_at` in the window, joined to its generated
  practice to identify the skill. This deliberately excludes merely dealt cards.
- `returning_learners_two_utc_dates`: those accounts completed on at least two
  distinct UTC dates **within this window**. This is not D7 retention or evidence
  that a person has only one account.
- `completed_practices`: submitted `user_practices` rows across all skills;
  per-skill completion counts and writing/speaking distinct learner counts show
  where personalized feedback is actually used. Skill labels are normalized to
  lower case. Writing means the implemented Task 2 flow, not every writing task.
- `content_pool_rows_created_not_learner_activity`: all generated-practice rows
  created in the window, shown separately. Pool generation can be scheduled,
  seeded or replenished after a request. It is **not a user count or proof of
  bots**, is not restricted by operator account exclusions, and cannot reliably
  be assigned to those accounts because these rows have no creator user ID.

The report does not count legacy/static `practice_results`, study timers,
logins, page visits or unsubmitted activity. Label its scope as **completed
AI-generated exercises**, not all visitors or all active users. It also cannot
prove an account is human: scripted clients may submit exercises. Repeat
completed study is stronger evidence than raw hits, but not conclusive.

## Why provider usage is not learner traffic

OpenAI, speech and TTS bills show resource consumption, not unique learners:

- Shared exercise pools can be generated automatically, then reused by many
  accounts; a learner can also trigger replenishment.
- Writing scoring and annotations are separate model calls. Speaking may use
  transcription, grading and an optional pronunciation request.
- Retries, operator tests, cached lookups and different model prices break a
  simple calls-to-users or dollars-to-users conversion.
- `usage_counters` aggregates categories per account/day but uses rough cost
  weights, can refund cache hits, and counts some attempts before validation.
  Its current fail-open behavior means it is neither a billing ledger nor an
  exact cost record. Provider invoice totals may also cover other applications
  sharing a project/key; do not assume all usage belongs to this app.

Next, reconcile a matching date window of **aggregate** edge/web analytics
(human-filtered visits if available), signups, completed/returning learners and
app-specific provider costs. Check traffic source and country before choosing
pricing/payment methods. Do not export raw access logs or customer content.
The current repository does not implement an acquisition/conversion funnel, so
this report intentionally does not invent one from provider usage.

## Verification and limits

```sh
python -m unittest discover -s ops/reports/tests -v
```

The standard-library tests run only synthetic in-memory SQLite fixtures. They
execute the aggregate CTE/SELECT core unchanged and replace only the Postgres
parameter/exclusion CTE with bound fixture parameters. Cases cover empty data,
window boundaries, owner/test exclusions, uppercase skills, unsubmitted cards,
same-day repeat submissions, distinct returning dates and untouched generated
pool content. They also check the read-only/output contract. No app import,
network, real provider call, production data or live database is involved.

**Not verified by these tests:** psql variable parsing, Postgres array/timestamp
conversion, transaction commands, the deployed schema, production runtime or
query performance. Before operational use, an authorized operator should smoke
test the complete script against a disposable Postgres fixture with the same
columns and expected counts. Do not represent the SQLite fixture pass as a
Postgres execution or a production traffic measurement.

## Repository basis

- `backend/app/models/models.py`: `User`, `GeneratedPractice`, `UserPractice` and
  `UsageCounter`; `GeneratedPractice.skill` is a string, not the skill enum.
- `backend/app/routers/writing.py`, `speaking.py`, `reading.py`, `listening.py`,
  `reading_exam.py`, `listening_exam.py`, `grammar.py`: submission paths.
- `backend/app/routers/generate.py` and writing replenishment: generation/lookup
  behavior; `backend/app/services/ai/writing_grader.py`: multiple grading calls.
- `backend/app/services/quota.py`: rough weights and failure semantics.
