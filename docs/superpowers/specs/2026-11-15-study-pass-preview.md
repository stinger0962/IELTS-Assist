# 30-day IELTS Study Pass: preview and launch gates

## First offer

A one-time 30-day pass with full-length reading and listening mock tests
and a fixed number of AI Task 2 writing reviews. No auto-renewal. Keep
basic practice and previous results available. An account without the pass
can try one full writing review after the feature is enabled; preserve legacy
VIP access. Label AI scores as estimates, not official IELTS grades.

Do not put a live price, fixed allowance or checkout link into the preview.
Set the offer using actual usage, grader cost/quality and customer geography
before public launch. Speaking remains out of the first pass; measure it
separately before committing to a high-cost allowance.

## Preview boundary

The feature defaults off. Preview testing uses an isolated development/test
database, synthetic accounts, seeded entitlements and a mocked grading
provider. The preview cannot buy a pass or accept real payments. There is
no public self-grant route and no change to production configuration,
deployment, credentials or existing customer data.

Expected paths to verify together:

- Feature off: existing free and VIP UX and API behavior stay the same.
- Enabled: a new free account can finish one review; a later valid
  submission reaches the upgrade state without losing the draft.
- Active pass: full reading/listening mocks unlock even with zero reviews
  left; an expired pass stops unlocking mocks. This preview checks access at
  both allocation and submission, so a full mock must be submitted before
  expiry. Review the best expiry UX before public launch. Legacy VIP access
  remains.
- Duplicate requests and concurrent submissions do not double-charge
  credits. Provider failure and invalid submissions do not take a credit.
  A process crash after reservation needs reconciliation; don't release a
  pending reservation on a timer while a worker could still be grading.
- Status responses never leak another account's pass or writing.
- On a phone-sized screen, opening, leaving and reopening the offer
  doesn't accidentally submit or erase a draft. No real charge can occur.

## Before live sale

1. Run the read-only activity report separately, with operator/test
   accounts excluded. Compare browser visits, account signups and repeat
   completions. Check the app's own provider project/key and separate
   scheduled content-generation costs from writing reviews. Confirm
   recovery email is configured and delivery works.
2. Verify writing feedback against independent examiner-scored examples,
   confirm what the score can and cannot claim, and choose a bounded
   allowance, displayed price/currency and refund terms.
3. Add a payment-provider sandbox in separate work. Grant only from a
   verified, successful payment event; a browser return URL cannot grant
   access. Reconcile idempotent order/grant, retry, expiry and refund
   handling. Handle incomplete or abandoned checkout without granting.
4. Run the whole flow with a disposable Postgres database, including
   concurrent writes and failed transactions. Smoke-test desktop and
   mobile before any rollout; production and live payment activation are
   separate from approving this feature branch.
5. Before switching the feature on for real people, ensure learners can
   see the free allowance and the paid terms before submitting, practice
   progress is preserved, and checkout is actually available. A rollback
   disables the offer, not already-earned work or records.
