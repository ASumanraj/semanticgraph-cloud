# T-201 · Make tenant isolation fail closed

**Stage** 2 · **Type** work · **Status** claimed · **Owner** Antigravity · **Branch** `t-201-force-rls`

**Scope**
- `alembic/**`
- `src/semanticgraph/adapters/outbound/postgres/**`
- `tests/integration/adapters/postgres/**`

**Blocked by** T-200 · **Blocks** T-202

## Goal
Isolation is application-level `WHERE tenant_id = ...` only, so one forgotten
predicate is a cross-tenant leak. Move it into the engine. Irreversible rule 2.

`ENABLE ROW LEVEL SECURITY` alone is silently bypassed by the table owner — the most
common production pitfall — so this needs `FORCE` and an application role that does
not own the tables.

## Acceptance
- [ ] Every tenant-scoped table has `ENABLE` **and** `FORCE ROW LEVEL SECURITY` with a tenant policy
- [ ] The application connects as a role that does not own the tables and lacks `BYPASSRLS`
- [ ] Tenant context is set with `SET LOCAL` **inside the transaction**, never session-level
- [ ] A test asserts every table returns **zero rows** with no tenant context set
- [ ] A test issues a query with no `WHERE tenant_id` and gets nothing back
- [ ] A test proves tenant A's context cannot read tenant B's rows

## Notes
Session-level `SET` under transaction-mode PgBouncer persists on the pooled
connection and hands the next caller the previous tenant's context — a breach, not a
bug. This restores the coverage lost when `test_tenant_isolation.py` was deleted in
`eb98235`.
