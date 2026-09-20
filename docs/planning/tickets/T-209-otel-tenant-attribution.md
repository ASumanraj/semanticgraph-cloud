# T-209 · OpenTelemetry with tenant attribution

**Stage** 2 · **Type** work · **Status** open · **Owner** — · **Branch** `t-209-otel-tenant-attribution`

**Scope**
- `src/semanticgraph/observability/**`
- `src/semanticgraph/composition/container.py`
- `src/semanticgraph/adapters/inbound/**`

**Blocked by** — · **Blocks** —

## Goal
`tenant_id` on every span, metric and log line, propagated explicitly through worker
headers — it does not cross the broker on its own, and that is the usual gap.
Retrofitting tenant attribution across an existing trace surface is miserable, and
it always happens under deadline pressure from a billing dispute.

Runs in parallel with the migration chain: no Alembic revision, disjoint paths.

## Acceptance
- [ ] `tenant_id` is a resource or span attribute on every span, metric and log line
- [ ] Tenant context crosses the worker boundary explicitly
- [ ] The stable `gen_ai.*` core is instrumented: operation, provider, model, input and output tokens
- [ ] **Document text never reaches telemetry** — ids and hashes only
- [ ] A lint or review rule enforces that, before the codebase has 200 log statements

## Notes
These attributes are also the cost-attribution substrate: cloud billing cannot
attribute model tokens to a tenant, and AWS Application Cost Profiler is
discontinued. Only this instrumentation can.
