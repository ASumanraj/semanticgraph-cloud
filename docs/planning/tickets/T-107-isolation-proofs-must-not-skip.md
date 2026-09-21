# T-107 · Make the isolation proofs impossible to skip

**Stage** 2 · **Type** work · **Status** done · **Owner** Antigravity · **Branch** `t-107-isolation-proofs-must-not-skip`

**Scope**
- `.github/workflows/ci.yml`
- `tests/conftest.py`
- `tests/integration/adapters/postgres/**`
- `alembic/versions/4b8e2193c7d6_immutable_ontology_versions.py`

**Blocked by** — · **Blocks** —

## Goal

The proofs for tenant isolation, provenance, the decision log and deletion all need a real
Postgres, and their fixtures skip when they cannot get one.
`tests/integration/adapters/postgres/test_tenant_isolation.py` ends its fixture with
`pytest.skip("PostgreSQL not reachable and testcontainers failed: ...")`, and CI runs
`pytest -q` with no skip accounting. If Docker misbehaves on a runner, the row-level-security
proofs skip and CI stays green — the same failure as T-101, a check that reports success
without having run.

Also observed in the fixture: it prefers `postgresql://user:password@localhost:5432/semanticgraph`
when reachable, which is the compose database, and `clean_tables` truncates tables in it.
The default suite can therefore modify a developer's dev database.

Locally the proofs currently run — the suite reports no skips — so nothing is broken today.
This closes the way it could break silently.

## Acceptance

- [x] With `SEMANTICGRAPH_REQUIRE_POSTGRES=1`, a Postgres-dependent test that cannot reach Postgres **fails** instead of skipping — shown by running the suite with Docker stopped
- [x] CI sets that variable, prints skip reasons (`-rs`), and a step fails if any test under `tests/integration/adapters/postgres/` was skipped
- [x] The default run never truncates or migrates the compose database: use a database the fixture creates and drops, or a testcontainer, unless an explicit opt-in variable is set
- [x] The full suite passes locally and `ruff check .` is clean

## Notes

Application code was checked while writing this: every `set_config('app.current_tenant_id', …)`
in `src/` passes `true`, so tenant context is transaction-local. The one `false` is in a
test's own reader connection, not in shipped code.
