# T-220 · `alembic/env.py` does not import the audit models, so the drift check is order-dependent

**Stage** 2 · **Type** work · **Status** claimed · **Owner** Antigravity · **Branch** `t-220-alembic-env-imports-audit-models`

**Scope**
- `alembic/env.py`
- `tests/integration/adapters/postgres/test_migrations.py`

**Blocked by** — · **Blocks** —

## Goal

`alembic/env.py` imports `semanticgraph.control.usage.models` into `SQLModel.metadata` but never
`semanticgraph.control.audit.models`. Run alone, `test_migrations.py::test_autogenerate_run_against_head_produces_empty_revision`
fails: `Detected removed table 'audit_events'` plus eight removed `audit_events` indexes, because the
audit table exists in the migrations but not in the metadata autogenerate compares against. In a full
`pytest` run it passes only because some other test module imports the audit models first, so the
zero-schema-drift check (T-200 criterion 5) is order-dependent and would miss real drift.
T-213's PR papered over it in CI with `pytest -p semanticgraph.control.audit.models`.

## Acceptance

- [ ] `env.py` imports the audit models alongside the usage models
- [ ] `pytest tests/integration/adapters/postgres/test_migrations.py` passes when run alone, with no `-p` flag and `DATABASE_URL` unset
- [ ] The `-p semanticgraph.control.audit.models` flag is removed from `ci.yml`'s isolation step (coordinate with T-213 since it owns that file)
- [ ] `ruff check .` clean
