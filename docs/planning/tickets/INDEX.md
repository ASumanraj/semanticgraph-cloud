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
