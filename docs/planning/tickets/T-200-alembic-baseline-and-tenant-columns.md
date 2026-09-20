# T-200 · Alembic baseline with tenant_id on every table

**Stage** 2 · **Type** work · **Status** open · **Owner** — · **Branch** `t-200-alembic-baseline`

**Scope**
- `alembic/**`
- `alembic.ini`
- `src/semanticgraph/adapters/outbound/postgres/models.py`
- `tests/integration/adapters/postgres/**`

**Blocked by** T-102 · **Blocks** T-201

## Goal
There are no migrations. Tables come from `create_all`, which is not viable for a
multi-tenant production database. Open the migration chain, and put `tenant_id` on
every table — including where it looks redundant — as the **leading column of every
composite index**. A missing leading `tenant_id` is the single biggest RLS
performance killer, and adding the column later rewrites every index.

## Acceptance
- [ ] `alembic upgrade head` builds the schema from empty
- [ ] `alembic downgrade base` reverses it
- [ ] Every table has `tenant_id`, and every composite index leads with it
- [ ] `create_all` is no longer the path by which tables appear
- [ ] An autogenerate run against head produces an empty revision

## Notes
First link in the serial chain — T-200 through T-208 each add revisions and must run
one at a time. See ENTERPRISE_PLAN.md Part 2.5.
