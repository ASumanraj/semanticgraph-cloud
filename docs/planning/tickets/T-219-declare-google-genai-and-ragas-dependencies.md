# T-219 · `pyproject.toml` is missing `google-genai` and `ragas` as real dependencies

**Stage** 2 · **Type** work · **Status** done · **Owner** Antigravity · **Branch** `t-219-declare-missing-dependencies`

**Scope**
- `pyproject.toml`
- `uv.lock`

**Blocked by** — · **Blocks** — (this must land before T-216's fix can be observed to do anything in CI, see Notes)

## Goal

Got the actual CI log text for the `test` job's "Test (fast suite)" step for the first time (via
`gh run view --log-failed` in agy's environment — the GitHub API's log-download endpoint refuses an
unauthenticated request, which is why this took three rounds to get). The real failure has nothing
to do with T-216:

```
ERROR tests/evaluation/test_ragas_hallucination.py
  ModuleNotFoundError: No module named 'ragas'
ERROR tests/live/test_gemini_smoke.py
ERROR tests/unit/adapters/test_gemini_gateway.py
ERROR tests/unit/evals/test_cuad_harness.py
  ModuleNotFoundError: No module named 'google'
    (all three via src/semanticgraph/adapters/outbound/llm/gemini.py:23: from google import genai)
Interrupted: 4 errors during collection
```

`pyproject.toml` has never listed `google-genai` or `ragas` anywhere — confirmed by grep, zero
hits. `google.genai` is imported unconditionally at module level by
`adapters/outbound/llm/gemini.py`, and `adapters/outbound/llm/__init__.py` imports that module
eagerly at package-import time, so **importing the package at all** requires it, not just using the
Gemini provider. `ragas` is used only by `tests/evaluation/test_ragas_hallucination.py`.

Every "full suite green" claim this whole project's history has been running against a local
`.venv` that had both packages installed from earlier ad hoc work (confirmed: both import cleanly
in the existing dev venv, versions `google-genai==2.24.0` and `ragas==0.1.19`). **`pip install
-e ".[dev]"` in a clean environment — exactly what CI does — has never actually installed them**,
so pytest has been failing at collection, before running a single test, since T-215 added the
Gemini adapter. This is why the "Test (fast suite)" step has shown the same generic "exit code 2"
in every CI run so far, including the one for T-216's own fix commit — the alembic bug T-216 fixes
was never actually reached.

## Design

Add `google-genai>=2.24` to `dependencies` in `pyproject.toml` (it's a real runtime import of a
production adapter, not test-only — belongs in core deps, not `dev`). Add `ragas>=0.1.19` to the
`dev` optional-dependencies group (test-only, matches how `testcontainers` is already categorized
there). Regenerate `uv.lock` so CI's `pip install -e ".[dev]"` — which reads `pyproject.toml`
directly, not the lock file — picks up both, and `uv sync` stays reproducible for local dev.

## Acceptance

- [x] `google-genai` is a core dependency, `ragas` is a `dev` optional dependency, both pinned to at least the versions already validated in this session
- [x] A clean install proves it: `pip install -e ".[dev]"` in a fresh virtualenv (no pre-existing packages), then `pytest -q` collects all 4 previously-broken modules with zero `ModuleNotFoundError`s — this is the exact condition that was never tested before and must be shown, not assumed
- [x] `ruff check .` clean

## Notes

This blocks actually observing whether [T-216](T-216-alembic-env-ignores-explicit-test-urls.md)'s
fix works in real CI — collection has to succeed before the isolation-proof tests T-216 touches
even run. Land this first, then re-run PR #13's CI and see what the isolation-proof step actually
says for the first time ever.

## Review, verified 2026-09-23

Reviewed the fix (`ad5e07b`) against `t-219-declare-missing-dependencies`. No PR was actually opened
for this — the branch was pushed but `gh pr create` (or the UI equivalent) was never run, so CI has
never once executed against this fix; get the PR opened before calling this mergeable.

The fix itself is verified independently, not just re-run from the report: built a genuinely fresh
virtualenv from scratch (not the existing dev `.venv`, which already had both packages from earlier
session work and would hide this exact class of bug), ran `pip install -e ".[dev]"` cold, and
confirmed all 4 previously-broken modules collect with zero `ModuleNotFoundError` (21 tests, matching
the report) and the full suite collects (397/399, 2 deselected). `ruff check .` and `ruff format
--check .` clean.

Also ran the full suite (not just collection) from that clean venv against a real Postgres with
`DATABASE_URL` set — 366 passed, 4 failed, 26 errors, all in
`tests/integration/adapters/postgres/**`. **This is expected, not a T-219 defect**: this branch
forked from `main` before T-216's fix existed, so it doesn't have it, and this is exactly T-216's
already-diagnosed bug resurfacing on its own. Confirms the two fixes are independent and both
needed — T-219 alone was never going to make the isolation-proof tests pass.

**Merge-order note:** T-219 and T-216 both need to reach `main` before CI can show a genuinely
green `test` job. Recommend merging T-219 first (self-contained, no dependency on T-216), then
rebasing T-216's branch onto the new `main` so it picks up the dependency fix too — only then will
PR #13's CI re-run actually exercise the alembic fix for the first time. Accepted; status set to
done once the PR is opened and this lands.
