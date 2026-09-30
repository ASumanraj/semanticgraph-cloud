# T-226 · CI installs from `uv.lock`, so the lockfile guarantees what CI tests

**Stage** 2 · **Type** work · **Status** open · **Owner** — · **Branch** `t-226-ci-installs-from-uv-lock`

**Scope**
- `.github/workflows/ci.yml`
- `README.md` (one short paragraph on updating the lock; only if no better home exists)

**Blocked by** — · **Blocks** —

## Goal

Decision 2026-09-30: `uv.lock` stays tracked (T-219 committed it), and CI installs from it. Today both CI
jobs run `pip install -e ".[dev]"`, which resolves `pyproject.toml` afresh on every run and ignores the
lock. The lockfile therefore guarantees nothing: a new transitive release can break CI, or pass it, while
a developer on the lock tests something different. Two earlier CI failures (T-219's missing dependencies,
masked by a hand-built venv) were this class of problem.

Checked before writing this ticket: `uv lock --check` passes on `main`; `uv sync --locked --extra dev`
builds a working environment from a clean directory in about 27 s (imports of `semanticgraph`,
`google.genai`, `ragas` and `testcontainers` succeed); and `uv sync --locked` refuses a `pyproject.toml`
that no longer matches the lock ("To update the lockfile, run `uv lock`"), which is the behaviour wanted.

## Design

- Use `astral-sh/setup-uv` with a pinned uv version and its cache, and install with
  `uv sync --locked --extra dev` in the `test` job and in the `frontend` job's "Setup virtualenv" step
  (`frontend/playwright.config.ts` expects `.venv/bin/python` at the repo root, which `uv sync` creates).
- Run backend steps through `uv run --locked` (or an activated `.venv`) so they use that environment.
- Keep the skip guards and `pipefail` from T-213 untouched.
- Say in one paragraph where a contributor learns that any change to `pyproject.toml` dependencies needs
  `uv lock` committed in the same PR, and that CI fails if it is stale.

## Acceptance

- [ ] Both jobs install with `uv sync --locked`, with no `pip install -e ".[dev]"` left in `ci.yml`
- [ ] A deliberately stale lock (a `pyproject.toml` dependency bound changed without `uv lock`) turns the install step red, shown by a run, then reverted
- [ ] A green run on the PR with "Isolation proofs" and "Control-plane proofs" still passing with the same counts, and the frontend E2E step still green
- [ ] `ruff check .` clean

## Notes

This is the only file the ticket may write besides the README paragraph; do not regenerate `uv.lock`
here. Local developers keep using `uv sync`. An editable install is implied by `uv sync`; confirm the
package imports from `src/` in both jobs.
