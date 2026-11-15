# Study Pass: offline checkout acceptance

This increment proves entitlement fulfillment without a real merchant,
checkout link, API key, payment event or charge. The fake gateway and
fixture offer exist in tests, not in an HTTP endpoint. Do not use the
fixture price or allowance as a public offer. No one can buy or unlock a
pass on the live site because of this branch.

## Acceptance boundaries

- The authenticated owner can start and inspect their order. The server
  chooses the offer and freezes its price, currency, duration and review
  allowance. An order return page can only read status.
- A pending, abandoned or failed payment does not grant entitlements.
  Settlement is verified first and matched in full against the order.
- Concurrent or repeated events do not issue multiple passes. Recording
  the event, settling the order and issuing the entitlement are one
  database transaction. Allow retry after a failed transaction.
- The first version does not support stacking or simultaneous paid passes.
  A second pending checkout can't accidentally create another grant.
- A confirmed full refund revokes future access, not saved study work;
  a later duplicate/delayed settlement must not undo revocation.
- Unknown, disputed or partial-refund payment states need reconciliation,
  not automatic charge/refund or an inferred credit policy.

## Still separate

A future merchant integration needs real signature verification and
authoritative provider-side reconciliation, hosted redirect validation,
cancellation and recovery UX, and staged payment tests using an approved
test account. The preview provides no public checkout endpoint. Before a
live sale, decide price/currency, review quantity and refund terms based on
actual learner activity and cost. Keep provider credentials out of the
repo and all fixtures. Deployment, commercial terms and live activation
are separate from this development branch.
