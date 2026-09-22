# T-210 · Per-tenant rate limits and spend cap

**Stage** 2 · **Type** work · **Status** done · **Owner** Antigravity · **Branch** `t-210-per-tenant-spend-cap`

**Scope**
- `src/semanticgraph/control/quota/**`
- `src/semanticgraph/adapters/inbound/api/**`
- `src/semanticgraph/composition/container.py`
- `src/semanticgraph/adapters/outbound/inmemory/**`
- `tests/unit/control/**`
- `tests/integration/adapters/api/**`

**Blocked by** T-207, T-211, T-212, **T-214** · **Blocks** —

## Goal
With token-priced inference an unbounded tenant is an unbounded bill. Enforce
entitlements **before** the expensive call — checking quota after inference means you
have already paid for it.

## Acceptance
- [x] A spend cap per tenant per period, enforced ahead of the model call — wired into composition root and FastAPI lifespan, active on `app.state.quota_enforcer`
- [x] Request-rate and concurrent-ingestion limits per tenant — enforced on every ingest call via `documents.py` through `QuotaEnforcer`
- [x] Exceeding a limit returns a clear error, and the attempt is audited
- [x] Limits are configurable per tier
- [x] A test proves an over-cap tenant is refused before any token is spent — tested through HTTP API with raw-SQL check verifying 0 new ledger rows for refused request and refusal audited

## Notes
Reads period spend from the T-207 ledger.
Rate-limit and concurrent-ingestion counters are currently maintained in-process via `asyncio.Lock` (per process / worker instance). Cross-worker/distributed enforcement across horizontal replicas can back onto Redis/Postgres in a future scale milestone.

## Review

Reviewed 2026-09-22 against `main` at `699816a`. `enforce_spend_cap` correctly reads
`UsageLedger.get_tenant_usage_summary` — a real, Postgres-backed, cross-process source of truth —
so the spend-cap number itself is sound. The rate-limit and concurrent-ingestion counters
(`_rate_limit_windows`, `_active_ingestions`) are plain in-process Python dicts guarded by one
`asyncio.Lock`, so they reset per process and are not shared across multiple workers or
replicas — a real limitation for anything beyond a single process, not documented anywhere as a
known constraint. Worth a line in the notes once this is fixed, though it is not this review's
main finding.

**Reopened for the defect that matters: `QuotaEnforcer` is built and unit-tested, and is never
connected to the running application at all.**

`documents.py`'s ingest route reads it as
`enforcer = getattr(request.app.state, "quota_enforcer", None)` and only enforces anything
`if enforcer:`. Nothing in `composition/container.py` or `adapters/inbound/api/app.py` ever sets
`app.state.quota_enforcer` — grepped for the string across both files, zero matches. So in the
actual running app, `enforcer` is always `None`, the `if enforcer:` block never executes, and
every request skips the spend cap, the rate limit and the concurrency check silently. Confirmed by
starting the real app and sending 80 rapid requests from one tenant against the free tier's
60-requests-per-minute cap:

```
app.state has quota_enforcer: False
status code counts across 80 rapid requests (free tier RPM cap = 60): Counter({200: 80})
```

Zero refusals. This is the same shape of defect T-110 existed to fix for the graph repositories:
a use case built and tested against the port directly, with production wiring that was never
written, so the acceptance criteria are true of the class and false of the product. The only test
that exists (`tests/unit/control/test_tenant_quota.py`) constructs `QuotaEnforcer` and calls its
methods directly — it cannot catch this, because it never goes through `app.state` the way a real
request does.

This ticket's own Scope already lists `src/semanticgraph/adapters/inbound/api/**`, so wiring is
squarely inside it, not deferred to another ticket.

**Fix direction:** build `QuotaEnforcer` in the composition root (it needs the usage ledger and,
optionally, the audit log — both already container fields) and set it on `app.state` in the
lifespan, the same way `app.state.container` is set today. Add an integration test that drives the
real app over HTTP — not the enforcer directly — past a configured limit and asserts the HTTP 402
or 429 the ticket already specifies, plus a raw-SQL check that no ledger row for the refused
attempt exists. That HTTP-level test is the one the current suite has no version of at all, and
it's the only kind that would have caught this.

Continue on a new branch off `main`.
