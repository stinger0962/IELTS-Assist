# Stale writing reservation: conservative operator runbook

Scope: launch preparation and synthetic/local rehearsal only. This document does
not authorize production access or mutation. There is no public recovery endpoint,
automatic expiry job, or approved production recovery command. Before any real
repair, obtain the environment-specific approval and have an engineer review the
concrete record and stopped-worker evidence. Never run a bulk timeout release.

## Why a pending review can remain

The allowance debit and pending reservation commit before grading begins. The
result and reservation completion commit together. A process crash between these
boundaries can leave an allowance reserved. A slow request, disconnected browser,
HTTP timeout, old timestamp, or absent log line does **not** prove a crash. The
provider can have processed work even when no response was received. Restoring a
review does not refund provider cost and does not promise exactly-once provider use.

## Read-only triage and stop conditions

Record an incident reference, exact environment/database, deployed revision, and
UTC inspection time. Do not copy essays, feedback, credentials, or full user
records into tickets. Keep attempt tokens only in restricted operator evidence.

Inspect together, using fresh database reads:

- Reservation ID, **exact current token**, state, owner, `user_practice_id`,
  `grant_id`, `created_at`, and `updated_at`.
- Linked card ID, owner, practice ID and writing skill. Check `submitted_at`,
  `user_answers`, score and all result fields for any persisted output.
- Original grant owner, kind, remaining/granted allowance, expiry and revocation.
  VIP reservations may have no grant. Do not attach another grant or create credit.
- Execution evidence correlating that attempt to the serving process/request and
  whether that process can still complete, reconnect, or resume.

Reservation rows are reused: **ID alone is not attempt identity**. A retry changes
the token and `updated_at`, but leaves `created_at` unchanged. Neither timestamp
is a heartbeat or a lease expiry. This schema does not persist a worker/job ID;
if external execution evidence cannot identify and prove the old worker stopped,
leave the reservation pending and escalate. Do not infer it from age.

| Observed state | Action |
| --- | --- |
| Completed with coherent saved result | Preserve it; use normal saved-result replay/history, never release or regrade. |
| Pending, worker possibly running or identity uncertain | No release. Investigate execution state; do not invite a second submission. |
| Pending with any saved result, mismatched ownership, missing linked row, or inconsistent balance | Stop for engineering reconciliation. Never delete output or overwrite balances to make the helper work. |
| Released with no result and same inspected token | No further release needed. Verify prior recovery; normal retry can create a new attempt. |
| Token changed since inspection | Stop: this is a different attempt. Never substitute the new token automatically. |
| Pending, no result, exact attempt confirmed stopped | Candidate for narrowly approved recovery below. |

## Recovery decision and transaction boundaries

1. Establish that the old serving worker is stopped and cannot resume its commit.
   Coordinate a per-user/card maintenance window with no new submissions or other
   repairs, using approved operational controls. There is no in-app repair lock.
   If this isolation cannot be established, do not proceed.
2. Reinspect all linked state immediately before the approved action. Require the
   same owner/card/reservation/token, pending state and no saved result. Preserve
   the observed original grant identity and balance for verification.
3. An engineer may use the existing internal `release_writing_review` helper with
   the **captured reservation ID and token** in a fresh dedicated session, only
   after these gates. No raw balance increment, grant creation, row deletion,
   token edit, or completed-to-pending reset is an acceptable substitute.
4. The helper rolls back its session first. Consequently a caller's prior lock or
   transaction is **not** a retained safety fence. Do not claim that wrapping
   inspection plus this call in a transaction makes recovery atomic. The stopped
   worker and maintenance gates above are necessary; the helper is not a complete
   operator recovery API. It does not enforce age, saved-result checks, worker
   liveness, ownership approval, or operator audit records.
5. Internally, release conditionally changes only the matching pending token to
   released and returns one review to its original grant in the same transaction.
   Repeat calls, completed rows and old tokens do nothing. A null VIP grant means
   no credit update. It returns no success flag, so **verify fresh persisted state**
   rather than assuming a normal return means a change occurred.
6. Re-read reservation/card/grant after commit. Confirm no saved result was
   discarded, the original token is released, and at most one original credit was
   returned. An expired or revoked grant stays expired/revoked; this is not a new
   entitlement. Record the before/after states and stop on unexpected changes.
7. End the maintenance window only after verification. A normal user retry can
   reserve with a new token and current entitlement. A stale completion must fail
   finalization with 409; its uncommitted result must roll back. Never bypass that
   failure or commit the stale result anyway. A recovery retry must continue using
   the **original captured token**, not whichever token is now in the row.

If a result was already committed but the browser response was lost, recover the
saved response through the application's existing replay path. That is a different
case from restoring an unused reservation. Do not manually fabricate AI feedback.

## Local regression and isolated staging rehearsal

[The synthetic regression suite](../../backend/tests/test_writing_reservation_recovery.py)
exercises the production reserve/finalize/release primitives without any AI or
payment network calls. Run it with the repository's test-only database setup,
alongside `test_study_pass.py` and `test_writing_study_pass.py`. Never point tests at
an existing deployment database: the shared test fixture drops its own tables.

Covered: old pending state stays blocked, repeated release credits once, reused
row/new token preserves attempt identity, stale completion's already-flushed
result rolls back, old release cannot refund a new attempt, completed output is
preserved, incorrect tokens are inert, and expired/revoked grants are not revived.
These deterministic SQLite cases are not proof of PostgreSQL concurrency safety
or proof that a real worker has stopped.

Before a live launch, rehearse only in an explicitly authorized isolated staging
environment using a synthetic account and a stub grader (no provider calls): hold
one attempt, observe pending/409, stop its worker with verifiable process evidence,
follow the reviewed recovery gates, verify one restored allowance, retry once and
verify one stored result. Also simulate a late stale completion and verify no
result overwrite/extra credit. Keep the protected evidence and record the deployed
revision. This document does not execute that staging exercise or authorize
changing production access, flags, credentials, or worker processes.
