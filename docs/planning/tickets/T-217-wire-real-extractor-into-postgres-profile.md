# T-217 · Wire a real LLM provider into `Container.postgres()`

**Stage** 3 · **Type** work · **Status** claimed · **Owner** Antigravity · **Branch** `t-217-real-provider-in-postgres-profile`

**Scope**
- `src/semanticgraph/composition/container.py`
- `src/semanticgraph/composition/model_routing.py`
- `.env.example`
- `tests/unit/composition/**`

**Blocked by** — · **Blocks** T-218 (touches `container.py` too — do not run in parallel, see Notes)

## Goal

T-215 added a real Gemini adapter behind `LLMGatewayPort` and explicitly left this gap open in its
own acceptance criteria (item 2, still unchecked): *"the container refuses to start [without a paid
key in a customer-facing profile] is not [tested], because `composition/container.py` never
constructs a Gemini gateway at all (grepped, zero references)... no provider is selected by profile
yet for any vendor."*

Confirmed still true: `Container.postgres()` (`composition/container.py:206`) hardcodes
`llm_gateway=InstrumentedLLMGateway(DeterministicLLMGateway(routing=model_routing))` — the
deterministic test double, unconditionally, regardless of `GEMINI_API_KEY`/`GEMINI_TIER` being set.
**The "production" composition root never calls a real model.** Every document ingested through
the real Postgres profile today is "extracted" by a fixed, fake extractor.

## Design

Add a profile-selection seam so `Container.postgres()` picks a real provider when one is
configured, falling back to the deterministic double only when none is:

- If `GEMINI_API_KEY` is set, construct `InstrumentedLLMGateway(GeminiLLMGateway(config=GeminiConfig.from_env()))`.
- T-215's own free/paid guard (`GEMINI_TIER`) already exists at the adapter's class level — wire it
  so `Container.postgres()` actually enforces it: refuse to start if `GEMINI_TIER` is unset or
  `free` and the profile is one that will see real tenant documents. Use whatever signal the
  codebase already has for "this profile handles customer tenants" (check `model_routing.py` and
  how other profile checks are done) rather than inventing a new one.
- No provider configured at all → keep the deterministic double as the explicit fallback, not a
  silent default masquerading as a real one — log which extractor got selected at startup, once,
  without leaking the key.
- Leave the port and every other provider's absence alone; this is provider-selection wiring, not a
  new adapter.

## Acceptance

- [x] `Container.postgres()` constructs a real `GeminiLLMGateway` when `GEMINI_API_KEY` is present, proven by a test that asserts the constructed gateway's type, not just that no exception was raised
- [x] `Container.postgres()` refuses to start with `GEMINI_TIER=free` (or unset) in a profile that handles customer tenants — the exact case T-215 flagged as untested
- [x] With no provider configured, the deterministic double is still used, and this is observable (a log line or a `Container` attribute), not silent
- [x] Full suite green, `ruff check .` clean — reopened for one unrelated regression found in the same diff, see Review

## Notes

Disjoint in intent from [T-218](T-218-persist-graph-and-expose-it-over-http.md) but both touch
`composition/container.py` — claim and finish one before the other starts, or expect a merge
conflict on that file. This one is smaller; doing it first means T-218's real extractor output is
worth persisting rather than more deterministic fixture data.

## Review

Reviewed PR #14 (`e9b695a`) against `t-217-real-provider-in-postgres-profile`. The actual ask is
done correctly: `Container.postgres()` constructs a real `GeminiLLMGateway` (with
`profile="postgres"`, which is in `GeminiLLMGateway.CUSTOMER_PROFILES`) when `GEMINI_API_KEY` is
set, refuses to start under `GEMINI_TIER=free`/unset via the real `GeminiFreeTierDisallowedError`
guard (not a new, parallel check — reuses T-215's own class-level guard as intended), and falls
back to the deterministic double with an observable `llm_provider` field and a log line when no
key is configured. Ran the new tests myself: `tests/unit/composition/` 16/16 passed, full suite 402
passed / 1 skipped / 2 deselected, `ruff check .` and `ruff format --check .` clean — all matching
the report exactly.

**Reopened for one defect, outside the ticket's stated scope, reproduced directly:**
`Container.postgres()` used to read `database_url = os.environ["DATABASE_URL"]` — a required key,
raising `KeyError` immediately if unset. This diff silently changed it to
`os.environ.get("DATABASE_URL", "postgresql://user:password@localhost:5432/semanticgraph")`.
Confirmed directly: with `DATABASE_URL` unset entirely, `Container.postgres()` no longer raises —
it silently builds a working engine pointed at `localhost:5432` with hardcoded dev credentials
baked into application code. No test in `test_container.py` needs this (every one of the four new
tests explicitly sets `DATABASE_URL` via `monkeypatch.setenv`), so the change wasn't necessary to
make the new tests pass — it looks like an incidental edit, not a considered one. This is the wrong
direction for a "postgres" (customer-facing) profile: a missing `DATABASE_URL` in a real deployment
should fail loudly at startup, the same way the `GEMINI_TIER` guard this same ticket added is
designed to fail loudly on misconfiguration, not silently connect to whatever happens to be at
`localhost:5432`.

**Fix direction:** revert that one line back to `os.environ["DATABASE_URL"]`. Nothing else in this
diff touches it or depends on the fallback. Continue on the same branch.
