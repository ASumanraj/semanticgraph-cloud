# T-225 · Migrations silently disable the application loggers; generated test output is tracked

**Stage** 2 · **Type** work · **Status** claimed · **Owner** Antigravity · **Branch** `t-225-alembic-logger-and-generated-files`

**Scope**
- `alembic/env.py`
- `tests/conftest.py`
- `.gitignore`
- `frontend/playwright-report/**`
- `frontend/test-results/**`

**Blocked by** [T-218](T-218-persist-graph-and-expose-it-over-http.md) merging (its PR adds the `conftest.py` workaround and modifies `playwright-report`) · **Blocks** —

## Goal

Found while reviewing T-218 slice 3. Two small, unrelated problems.

**1. `alembic/env.py` disables existing loggers.** It calls `fileConfig(config.config_file_name)`, and
`logging.config.fileConfig` defaults to `disable_existing_loggers=True`. Any in-process migration run
(every test fixture that calls `command.upgrade`) therefore disables the `semanticgraph` logger for the
rest of the process. Reproduced: after the Postgres graph API tests, the existing log-assertion test
`test_hosted_model_dependencies_logged_and_visible` fails. T-218 worked around it with an autouse fixture
in `tests/conftest.py`; the workaround hides the cause and leaves any in-process migration in application
code with the same behaviour. Running `alembic` from the CLI is a separate process, so production CLI use
is unaffected.

**2. Generated Playwright output is tracked.** `frontend/playwright-report/index.html` and
`frontend/test-results/.last-run.json` are committed and not ignored, so every E2E run leaves the tree
dirty and unrelated PRs pick up diffs in them. The spec also writes screenshots to
`frontend/e2e/screenshots/`, which is neither tracked nor ignored.

## Design

- `fileConfig(config.config_file_name, disable_existing_loggers=False)`; remove the autouse logger
  fixture from `tests/conftest.py`.
- `git rm --cached` the two generated files and ignore `playwright-report/`, `test-results/` and
  `e2e/screenshots/` (decide whether the one screenshot worth keeping as evidence goes under `docs/`).

## Acceptance

- [ ] With the `conftest.py` fixture removed, the Postgres graph API tests followed by `tests/integration/adapters/api/test_facts_and_deletion_api.py` pass in one process (they fail without the `env.py` fix)
- [ ] Full suite green under a real Postgres, 0 skipped from `tests/integration/control`, `ruff check .` clean
- [ ] A fresh `npm run test:e2e` leaves `git status` clean
- [ ] CI green
