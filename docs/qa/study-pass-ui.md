# Study-pass frontend QA

The feature depends on the authenticated `GET /api/study-pass` response.
The server is authoritative for expiry, mock-test access and review allowance.
The UI does not sell, grant, activate, renew or charge for a pass.

## Automated checks

- `cd frontend && npm test`: all 30 tests pass, including 10 new focused
  checks covering disabled/unavailable endpoints, invalid responses, stale
  responses after logout, English/Chinese panel content, exhausted active and
  expired passes, legacy VIP, details dismissal and 402/409 essay preservation.
- `npm run build`: TypeScript and production build pass; existing large bundle
  warning remains.
- `npm run lint`: cannot run because the repository has no ESLint 9 flat config.
- `git diff --check`: passes.

## Manual preview checklist (not yet verified)

Use a local/test backend with synthetic accounts. Do not point these checks at
production or invoke real paid grading services.

Start at 430px mobile width, then desktop:
1. Flag off or missing endpoint: ordinary practice and legacy VIP paths unchanged.
2. Enabled free account: free-review message; details expand/collapse without
   navigation; clear “Purchasing is not available yet” with no buy button.
3. Used trial / expired pass: do not promise a second free trial.
4. Active pass with 0 reviews: full mocks still accessible; 0 shown accurately.
5. English/Chinese and narrow viewport: no horizontal overflow.
6. Submit a 20-word essay into stubbed 402 and 409 responses: editor returns with
   exact text, readable error and retry; do not consume/rewrite draft content.
7. Rapid duplicate submit: only one in-flight call. A successful mocked review
   refreshes the status. Focus reloads status; logging out ignores a late result.
8. Existing Back/Finish behavior is unchanged. In-memory essay state is not a
   cross-navigation/reload draft store; copy unfinished work before leaving.
9. Verify real integration response and error shape against backend contract.

A direct Chromium 430px screenshot attempt was blocked by the execution
sandbox (`socket() failed: Operation not permitted`). No screenshot/visual
pass is claimed. Temporary preview harness removed.
