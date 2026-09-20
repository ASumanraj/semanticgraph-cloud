# T-207 · Usage event ledger

**Stage** 2 · **Type** work · **Status** done · **Owner** Antigravity · **Branch** `t-207-usage-event-ledger`

**Scope**
- `alembic/**`
- `src/semanticgraph/control/usage/**`
- `tests/integration/control/**`

**Blocked by** T-201 · **Blocks** T-210

## Goal
One immutable row per cost-driving event. **Usage you did not record is revenue you
cannot bill, and there is no backfill.**

## Acceptance
- [x] Client-generated `event_id` with a unique constraint, so retries count once
- [x] `occurred_at` separate from `recorded_at`, so late events land in the right period
- [x] Token counts read from the provider response, never estimated
- [x] The price version is stamped on the event, so an old invoice reproduces exactly
- [x] Rows are never updated or deleted; corrections are offsetting rows
- [x] Events are emitted server-side at the call site that incurs the cost
- [x] A test proves a duplicate `event_id` is counted once

## Notes
Metering at the API boundary misses cost incurred three layers down in a retrying
worker, which is the usual retrofit disaster. ENTERPRISE_PLAN.md Stage 2.
