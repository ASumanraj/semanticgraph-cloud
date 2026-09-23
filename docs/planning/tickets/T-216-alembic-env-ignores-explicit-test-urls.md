# T-216 · Alembic migrations silently target the wrong database under `DATABASE_URL`

**Stage** 2 · **Type** work · **Status** claimed · **Owner** Antigravity · **Branch** `t-216-alembic-env-url-precedence`

**Scope**
- `alembic/env.py`
- `tests/integration/adapters/postgres/**`
- `tests/integration/adapters/api/test_documents_api.py`
- `tests/e2e/conftest.py`

**Blocked by** — · **Blocks** —

## Goal

Now that CI actually executes (the Actions-permissions block is lifted), the `test` job's
"Test (fast suite)" step fails on `main`, reproduced locally against a real Postgres with the
exact same env CI uses. Root cause is in `alembic/env.py`, not in any of the tests it broke.

```python
# alembic/env.py, get_url()
db_url = os.environ.get("DATABASE_URL") or config.get_main_option("sqlalchemy.url")
```

`DATABASE_URL` always wins over whatever URL a caller explicitly set on the `Config` object via
`cfg.set_main_option("sqlalchemy.url", ...)`. That's backwards for every test fixture that spins
up its own throwaway database (a testcontainers Postgres, or a SQLite file) and calls
`command.upgrade(cfg, "head")` expecting **that** database to be migrated. Whenever `DATABASE_URL`
is set in the environment — which `ci.yml`'s `test` job now always does, at job level, for a
`postgres` service most of these fixtures don't even use — the migration silently runs against
**the wrong database**: the fixture's throwaway one is left with no schema at all, and the CI
`postgres` service (or whatever `DATABASE_URL` happens to point to) gets migrated instead, unused.

**Reproduced three ways, isolating the same root cause each time:**

1. `tests/integration/adapters/postgres/test_tenant_isolation.py::test_rls_enabled_and_forced_on_all_tenant_tables`
   — its `migrated_postgres` fixture spins up a **testcontainers** Postgres and calls
   `cfg.set_main_option("sqlalchemy.url", postgres_admin_url)`. With `DATABASE_URL` set, migrations
   went to `DATABASE_URL`'s target instead; the test then queries the testcontainers database for
   `pg_class` and finds no `documents` table at all — not an RLS defect, the schema was never
   applied to the database under test.
2. `tests/integration/adapters/api/test_documents_api.py::TestQuotaEnforcementThroughAPI::test_spend_cap_exceeded_returns_402_and_no_ledger_row_via_raw_sql`
   — builds a throwaway **SQLite** file and does the same `set_main_option` + `command.upgrade`.
   Fails with `sqlite3.OperationalError: no such table: usage_events` — migrations went to
   `DATABASE_URL` (a Postgres), leaving the SQLite file schema-less.
3. Same fixture family in `test_deletion_cascade.py`, `test_ontology_repository.py`,
   `test_provenance_repository.py`, `test_resolution_repository.py`, `test_temporal_repository.py`,
   `test_migrations.py`, and `tests/e2e/conftest.py` — all duplicate the identical
   `set_main_option("sqlalchemy.url", ...)` + `command.upgrade(cfg, "head")` pattern and are broken
   the same way. 26 errors plus these named failures in a from-scratch `pytest -q` run confirm it.

**Three files are *not* affected** and should not be touched: `tests/integration/control/test_audit_log.py`,
`test_usage_event_ledger.py`, `test_usage_event_attribution.py`. Their `postgres_setup` fixture
never calls `set_main_option` — it migrates whatever `DATABASE_URL`/the compose default already
points to and then connects to that same target, so there's no mismatch. This also means the CI
`postgres` service is not entirely idle, contrary to T-213's note — it's exactly what these three
files' fixtures use, just not gated by `SEMANTICGRAPH_USE_COMPOSE_DB` the way the docstring in
`tests/integration/adapters/postgres/conftest.py` implies it should be. Worth a line in T-213 when
that ticket is picked up, not a reason to touch these three files here.

**Why this was invisible until now:** the testcontainers-backed fixtures only exercise this path
on a machine where testcontainers actually reaches a Docker daemon. Locally that's been
inconsistent enough that these tests mostly skipped instead of running, and nobody's shell had
`DATABASE_URL` exported by accident at the same time. CI is the first environment where Docker
reliably works **and** `DATABASE_URL` is always set, so it's the first environment to hit this on
every run. **Every prior "done" Stage 2 ticket's claim of a clean real-Postgres run (T-201, T-203,
T-205, T-206, T-210's own new API test) was verified by hand against a manually-migrated database,
never by this suite running unattended** — the manual verifications this session did for T-208/
T-209/T-210 stand because they used direct `psycopg`/compose connections, not this fixture family,
but the isolation-proof *tests themselves*, as CI would run them, have apparently never passed for
real.

## Design

Fix the precedence in `alembic/env.py` without breaking the real deploy/CLI use of `DATABASE_URL`
(where nobody calls `set_main_option` and the env var is exactly what should apply). Use
`Config.attributes` — a dict separate from ini options, meant for exactly this — as the highest
priority, checked before the environment variable:

```python
def get_url() -> str:
    override = config.attributes.get("sqlalchemy.url")
    db_url = override or os.environ.get("DATABASE_URL") or config.get_main_option("sqlalchemy.url")
    ...
```

Then in every affected fixture, set `cfg.attributes["sqlalchemy.url"] = url` alongside (or instead
of) the existing `cfg.set_main_option("sqlalchemy.url", url)` call, so the override actually takes
effect. `set_main_option` can stay for anything else that reads it, but `attributes` is what makes
`env.py` respect it.

## Acceptance

- [ ] `alembic/env.py`'s `get_url()` gives an explicit `config.attributes["sqlalchemy.url"]` priority over `DATABASE_URL`
- [ ] Every fixture in scope that calls `set_main_option("sqlalchemy.url", ...)` on a throwaway database also sets `cfg.attributes["sqlalchemy.url"]`
- [ ] With `DATABASE_URL` set to an unrelated real Postgres in the environment, `pytest tests/integration/adapters/postgres/ tests/integration/adapters/api/test_documents_api.py tests/e2e/ -v` passes with zero errors and zero unexpected skips — this is the exact condition CI runs under, and the ticket must show a run under it, not just a run with `DATABASE_URL` unset
- [ ] `pytest -q` (the fast-suite step) is clean under the same `DATABASE_URL`-set condition
- [ ] `ruff check .` clean

## Notes

This blocks trusting CI's own `test` job at all until fixed — right now it fails at "Test (fast
suite)" before "Isolation proofs" ever runs, so T-213's own acceptance criteria (a green isolation
run, a deliberately-broken run turning it red) can't be attempted yet. Fix this one first.
