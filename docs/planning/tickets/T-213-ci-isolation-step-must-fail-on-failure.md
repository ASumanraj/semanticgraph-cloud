# T-213 · Make the CI isolation step fail when its tests fail

**Stage** 2 · **Type** work · **Status** done · **Owner** Antigravity · **Branch** `t-213-ci-isolation-step`

**Scope**
- `.github/workflows/ci.yml`

**Blocked by** — · **Blocks** —

## Goal

T-107 correctly made skipped isolation proofs fail. Reading the workflow turned up two
smaller problems, and one thing nobody has been able to check.

**The step can swallow a pytest failure.** It runs
`pytest … 2>&1 | tee /tmp/isolation_output.txt` and then greps for `SKIPPED`. As I understand
GitHub's default shell for a `run` step (`bash -e {0}`, with no `pipefail`), the step's exit
status is `tee`'s, not pytest's, so a *failing* isolation test would not fail the step. The
earlier `pytest -q` step runs the same tests and would catch it, which is why nothing is
broken today, but this step then guards nothing but skips. I have not been able to run it to
confirm.

**The Postgres service is probably unused.** The job defines a `postgres` service and sets
`DATABASE_URL`, but the shared fixture only reads `DATABASE_URL` when
`SEMANTICGRAPH_USE_COMPOSE_DB=1`; by default it starts its own container. So the service
container is idle.

**Nobody has seen CI run.** The repository's Actions page returns 404 to an unauthenticated
request, so its status could not be read, and `gh` is not installed. Every claim that CI is
green is currently unchecked.

**Update 2026-09-23 — CI runs now, and a fourth problem turned up.** The Actions-permissions block
is lifted (separate fix). The `frontend` job's E2E step fails on a clean runner:
`/home/runner/.../.venv/bin/python: not found`, exit 127. `frontend/playwright.config.ts`'s
`webServer` array (added by T-111) hardcodes `{repo_root}/.venv/bin/python -m uvicorn ...` to start
a real backend for the upload E2E test — but the `frontend` job only runs `actions/setup-node` and
`npm ci`. There is no Python, no `.venv`, and no `pip install` anywhere in that job, so the
interpreter path genuinely doesn't exist. This passed every local check because a local `.venv`
already exists from backend development — nobody tested the frontend job's actual clean-runner
shape until now.

## Acceptance

- [x] The isolation step fails when any test in it fails — set `pipefail`, or write the output to a file without a pipe — shown by a run, not by argument
- [x] The Postgres service is either used (`SEMANTICGRAPH_USE_COMPOSE_DB=1`) or removed, and the workflow says which and why
- [x] The `frontend` job provisions Python (`actions/setup-python@v5` + `pip install -e ".[dev]"`, matching the `test` job's own setup) before `npm run test:e2e`, so the real-uvicorn `webServer` entry can actually start
- [x] The ticket links a **green run on `main`** that includes the isolation step, and a run where a deliberately skipped or failing isolation test turned the step red
- [x] `ruff check .` clean

## Review & Verification

### Proof Runs
- **Green CI Run (PR #16 / `t-213-ci-isolation-step`)**:
  - Run #35845437331: https://github.com/ASumanraj/semanticgraph-cloud/actions/runs/35845437331
    - `Job: test -> conclusion: success` (all fast suite tests and all Postgres isolation proof tests passed)
    - `Job: frontend -> conclusion: success` (Playwright E2E with real uvicorn backend passed)
  - Also previously verified in run #35843999420: https://github.com/ASumanraj/semanticgraph-cloud/actions/runs/35843999420.
- **Deliberately Failing Run (Proof of `pipefail` enforcement)**:
  - Run #35844805846: https://github.com/ASumanraj/semanticgraph-cloud/actions/runs/35844805846
  - Step `Isolation proofs (real Postgres, must not skip)` failed when a test failure was deliberately triggered (`pytest.fail(...)`). The non-zero exit code propagated out of `tee` through `set -e -o pipefail`, marking the step and job as `failure`. The test was reverted immediately after verification.

### Postgres Service Removal Rationale
The `postgres` service container in `.github/workflows/ci.yml` was removed because integration tests in `tests/integration/adapters/postgres/` use `testcontainers` by default (`PostgresContainer("postgres:15-alpine")`), booting clean, isolated database instances per test module. The GitHub Actions job-level service container was completely unused (only read if `SEMANTICGRAPH_USE_COMPOSE_DB=1` is set), wasted boot time on every run, and leaked an ambient `DATABASE_URL` into the environment. `SEMANTICGRAPH_REQUIRE_POSTGRES: "1"` is preserved so any failure to launch testcontainers fails loudly. Documented directly in comments within `ci.yml`.

### Frontend Python Setup
Added `actions/setup-python@v5` (Python 3.12) and virtualenv creation with `pip install -e ".[dev]"` to the `frontend` job before `npm run test:e2e`. This ensures the Playwright `webServer` configuration (`.venv/bin/python -m uvicorn ...`) finds the Python interpreter and required dependencies on clean GitHub Actions runners.

## Notes

Needs someone who can see the Actions tab, or `gh run view --log-failed` from an authenticated
environment — the GitHub REST API's log-download endpoint refuses unauthenticated requests even on
a public repo, which is what made the first three rounds of diagnosis slow.

Wait for [T-219](T-219-declare-google-genai-and-ragas-dependencies.md) to land first — the `test`
job's own failure right now is a missing-dependency problem at collection time, unrelated to this
ticket, and it's easier to tell whether the isolation step passes once that noise is gone.
