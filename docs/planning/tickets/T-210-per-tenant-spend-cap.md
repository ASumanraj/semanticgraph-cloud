# T-210 · Per-tenant rate limits and spend cap

**Stage** 2 · **Type** work · **Status** claimed · **Owner** Antigravity · **Branch** `t-210-per-tenant-spend-cap`

**Scope**
- `src/semanticgraph/control/quota/**`
- `src/semanticgraph/adapters/inbound/api/**`
- `tests/unit/control/**`

**Blocked by** T-207, T-211, T-212, **T-214** · **Blocks** —

## Goal
With token-priced inference an unbounded tenant is an unbounded bill. Enforce
entitlements **before** the expensive call — checking quota after inference means you
have already paid for it.

## Acceptance
- [x] A spend cap per tenant per period, enforced ahead of the model call
- [x] Request-rate and concurrent-ingestion limits per tenant
- [x] Exceeding a limit returns a clear error, and the attempt is audited
- [x] Limits are configurable per tier
- [x] A test proves an over-cap tenant is refused before any token is spent

## Notes
Reads period spend from the T-207 ledger.
