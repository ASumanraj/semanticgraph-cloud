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

## Do this before the migration chain opens

[T-105](T-105-domain-invariants.md) blocks T-200 and every Stage 2 ticket after it.
`domain/models/entities.py` contradicts all five irreversible rules today, and a
baseline migration generated from it encodes every contradiction into the schema.
T-200 is claimed and its `alembic/versions/` is still empty — that is the window.

| Ticket | Scope |
|---|---|
| [T-105](T-105-domain-invariants.md) Domain invariants | `domain/**`, `application/**`, in-memory adapters, `tests/unit/**` |
| [T-106](T-106-narrow-the-graph-seams.md) Narrow the graph seams | `application/ports/**`, use cases, in-memory adapters |

## Run order

T-107, T-211 and T-212 are done. **One backend lane, one agent, in this order** — every
ticket touches `src/`, the migration chain, or both:

```
T-106 narrow the seams
  → T-214 one owner for model routing; price versions that only append
    → T-110 wire the record into the running system     ← first thing worth showing
      → T-208 audit log
        → T-209 OTel
          → T-210 spend cap
```

After T-110, [T-215](T-215-gemini-opt-in-provider.md) adds the first real provider adapter
(Gemini, opt-in). It is not in the lane above because nothing else waits on it.

T-106 and T-214 have disjoint scopes and could run in separate worktrees; one agent takes
them in this order.

**Beside it, each disjoint from the lane:**
[T-111](T-111-frontend-stop-misrepresenting-the-product.md) (`frontend/**`, and now also makes
the upload reach the real API), [T-213](T-213-ci-isolation-step-must-fail-on-failure.md)
(`ci.yml`), [T-905](T-905-gleif-coverage-spike.md), [T-906](T-906-batch-versus-interactive-ingestion.md),
[T-900](T-900-verify-whyhow-ai.md), [T-901](T-901-temporal-cloud-cost.md) (all `docs/**` or
`evals/**`), and [T-600](T-600-split-infra-stacks.md) (`infra/**`).

[T-904](T-904-evaluation-corpus.md) waits on a decision to fund a qualified reviewer.
[T-907](T-907-contract-ai-market-and-customer-one.md) (market research, done) chose no customer;
[T-908](T-908-dora-register-field-source-check.md) (`docs/research/**`) is the free check that
can remove one candidate segment before any interview.

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
