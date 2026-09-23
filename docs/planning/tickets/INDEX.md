# Ticket board

`README.md` has the protocol. Scope is the lock: **two tickets run in parallel
exactly when their Scopes are disjoint.**

## Live status

Status and owner live in each ticket's header, and nowhere else — duplicating them
here drifted within a day of the board existing. To see the current state:

```bash
grep -H "^\*\*Stage\*\*" docs/planning/tickets/T-*.md
```

What this file carries instead is the part that rarely changes: which tickets can
run together, and what blocks what.

## Run order — done as of 2026-09-22

The full backend lane is complete: T-105, T-106, T-107, T-110, T-200 through T-212, T-214,
T-215, T-208, T-209 and T-210 are all `Status: done`, each independently reverified against a
real running Postgres/HTTP stack (not just their own unit tests) — T-208, T-209 and T-210 were
each reopened once for a defect the original "done" report missed, fixed, and reverified before
acceptance. See each ticket's `## Review` section for the reproduction and fix.

```
T-106 narrow the seams
  → T-214 one owner for model routing; price versions that only append
    → T-110 wire the record into the running system
      → T-208 audit log ✓ done, reopened once, refixed
        → T-209 OTel ✓ done, reopened once, refixed
          → T-210 spend cap ✓ done, reopened once, refixed
```

[T-215](T-215-gemini-opt-in-provider.md) (Gemini, opt-in) is also done, and unblocks
[T-909](T-909-cuad-verifier-bakeoff.md) below — the first real (non-double) extractor now exists.
[T-909] itself is done too, reopened once for a CSV-loader defect, fixed and reverified.

**CI actually runs now (2026-09-23)** — the Actions-permissions block that silently failed every
run since 2026-09-19 is lifted. First real run turned up
[T-216](T-216-alembic-env-ignores-explicit-test-urls.md): `alembic/env.py` lets `DATABASE_URL`
override any URL a test fixture explicitly set, so every fixture that migrates its own throwaway
database (testcontainers Postgres or a scratch SQLite file) silently migrates the wrong one instead
whenever `DATABASE_URL` is set — which the CI job always does. This is why the "done, reverified
against a real Postgres" claims above still stand (those reviews connected by hand, never through
this fixture family) but the automated isolation-proof suite itself has apparently never passed
unattended. T-216's fix is accepted (Review section, independently reverified) but **CI still
doesn't show green** — the real cause turned out to be upstream of T-216 entirely:
[T-219](T-219-declare-google-genai-and-ragas-dependencies.md), `pyproject.toml` never declared
`google-genai`/`ragas` as dependencies, so `pip install -e ".[dev]"` in CI's clean environment
never installs them and `pytest` fails at collection before a single test runs — meaning T-216's
own fix has never actually been exercised by CI yet either. **Land T-219 first**, then re-check
whether T-216's isolation-proof step actually goes green, then start T-213 — which also picked up
a fourth item (`frontend` job needs `actions/setup-python` before its E2E step, since T-111's
dual-webServer Playwright config needs a real `.venv` that job never provisions).

**Tracing the T-111 `GraphExplorer` gap turned up two more real ones, filed as
[T-217](T-217-wire-real-extractor-into-postgres-profile.md) and
[T-218](T-218-persist-graph-and-expose-it-over-http.md).** `Container.postgres()` still hardcodes
the deterministic double as its extractor (T-215's own unchecked acceptance box said as much) and
still uses `InMemoryEntityStore`/`InMemorySubgraphReader` for the actual knowledge graph — there is
no `entities`/`edges` table in Postgres at all yet, so nothing extracted from a real document
survives a restart or is queryable. `SearchEngine`'s two methods are empty stub bodies by design
("Stage 3 fills them"). T-218 builds real persistence and a truthful, unranked
`GET /api/v1/graph`; T-217 is smaller and separate (which extractor `Container.postgres()` uses).
Both touch `composition/container.py` — sequence them, don't parallelize.

**Beside it, each disjoint from the lane:**
[T-111](T-111-frontend-stop-misrepresenting-the-product.md) (`frontend/**`, done — the frontend
`Lint` failure seen in the same first CI run is main not yet having T-111 merged, not a new defect),
[T-213](T-213-ci-isolation-step-must-fail-on-failure.md)
(`ci.yml`, start after T-216), [T-905](T-905-gleif-coverage-spike.md), [T-906](T-906-batch-versus-interactive-ingestion.md),
[T-900](T-900-verify-whyhow-ai.md), [T-901](T-901-temporal-cloud-cost.md) (all `docs/**` or
`evals/**`), and [T-600](T-600-split-infra-stacks.md) (`infra/**`).

[T-904](T-904-evaluation-corpus.md) waits on a decision to fund a qualified reviewer.
[T-907](T-907-contract-ai-market-and-customer-one.md) (market research, done) chose no customer;
[T-908](T-908-dora-register-field-source-check.md) (done) removed the DORA-register segment as customer
one: about 14% of its mandatory fields come from contracts.

Two agents at once need separate git worktrees; they share one checkout otherwise, and a
branch switch by one silently moves the other's commits.

## Fix before the spend cap

[T-214](T-214-one-owner-for-model-routing.md) blocks T-210. The ledger prices the right models
now, but old price versions cannot be resolved for a correction, and model routing has two
owners. A cap built on that would fail on its first correction.

## Groundwork that needs no pipeline

None of these touch `src/`, so they run beside anything.

| Ticket | Scope |
|---|---|
| [T-107](T-107-isolation-proofs-must-not-skip.md) Isolation proofs must fail, not skip | `ci.yml`, `tests/conftest.py`, `tests/integration/adapters/postgres/**` |
| [T-904](T-904-evaluation-corpus.md) Four-track evaluation corpus | `evals/**`, `docs/research/**` |
| [T-905](T-905-gleif-coverage-spike.md) Registry coverage on real counterparties | `evals/gleif/**`, `docs/research/**` |
| [T-908](T-908-dora-register-field-source-check.md) Is the DORA register built from contracts? | `docs/research/**` |
| [T-909](T-909-cuad-verifier-bakeoff.md) CUAD eval harness (unblocked by T-215) | `evals/cuad/**`, `tests/unit/evals/**` |

## First wave — five agents, no collisions

Nothing here blocks anything else here, and no two share a path.

| Ticket | Scope |
|---|---|
| [T-101](T-101-compose-runs-real-services.md) Run the real API and worker in compose | `docker-compose.yml`, `*.Dockerfile`, its test |
| [T-102](T-102-async-postgres-repository.md) Stop blocking the event loop | `adapters/outbound/postgres/**`, its port, its tests |
| [T-209](T-209-otel-tenant-attribution.md) OTel with tenant attribution | `observability/**`, `composition/`, `adapters/inbound/**` |
| [T-600](T-600-split-infra-stacks.md) Split infra into three stacks | `infra/**` |
| [T-900](T-900-verify-whyhow-ai.md) · [T-901](T-901-temporal-cloud-cost.md) Research | `docs/**` |

T-102 and T-209 both reach into `adapters/`, but different subtrees —
`outbound/postgres/` and `inbound/`. Disjoint.

## Unlocked by the first wave

| Ticket | Needs | Then runs beside |
|---|---|---|
| [T-103](T-103-postgres-backed-ingestion-test.md) Prove ingestion on real Postgres | T-101, T-102 | T-104 |
| [T-104](T-104-playwright-upload-journey.md) Drive the upload control in a browser | T-101 | T-103 |

T-103 owns `tests/e2e/**`, T-104 owns `frontend/**`. Two agents, no overlap.

## The serial chain — one agent at a time

Every ticket here adds an Alembic revision. Two agents generating revisions
concurrently produce two heads and a chain that gets rebuilt by hand. **They also
carry all five irreversible rules**, so this is the wrong place to move fast.

```
T-200 baseline + tenant_id ──► T-201 FORCE RLS ──► T-202 provenance spans
                                     │                      │
                                     │                      ├──► T-203 bi-temporal
                                     │                      │         │
                                     │                      │         ▼
                                     │                      │    T-204 decision log
                                     │                      │         │
                                     │                      │         ▼
                                     │                      │    T-205 ontology versions
                                     │                      │
                                     │                      └──► T-206 deletion cascade
                                     │
                                     └──► T-207 usage ledger ──► T-208 audit log
                                                  │
                                                  └──► T-210 spend cap
```

T-200 needs T-102 finished first — Stage 1 and Stage 2 both touch
`adapters/outbound/postgres/`, and the async decision has to settle before the
schema does.

T-206 branches off T-202 rather than the tail, so deletion can be built while the
temporal and resolution work proceeds — but both add revisions, so they still take
turns.

## Where this comes from

Tickets slice [`ENTERPRISE_PLAN.md`](../../architecture/ENTERPRISE_PLAN.md) into
work. The plan's progress tracker stays the top-level view — tick its line when a
ticket reaches `done`. Decisions go to [`docs/adr/`](../../adr/README.md), not into
a ticket.

## Decisions log

- 2026-09-21: the docker-compose host ports were remapped to 8003 and 3003 (`9e13a83`). Nobody
  asked for it; it is internally consistent and stays. History is not rewritten.
- 2026-09-21: `uv.lock` stays untracked while CI installs with pip.
- 2026-09-21: Gemini is used on public or synthetic data only until paid terms are confirmed (T-215).
- 2026-09-21: T-904 wave 1 approved as a 10-document pilot capped at 40 paid reviewer hours.
