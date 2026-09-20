# Superseded planning documents

Kept for provenance. Where these disagree with
[`ENTERPRISE_PLAN.md`](../../architecture/ENTERPRISE_PLAN.md) or
[`docs/adr/`](../../adr/README.md), the plan and the ADRs are correct.

| Document | Superseded because |
|---|---|
| `ticket-backend-design.md` | Specifies a `backend/` directory, `services/worker.py`, Celery, and `models/sql.py` — all deleted — and puts tenant isolation in `.where(tenant_id == ...)` predicates. [ADR-0002](../../adr/0002-postgres-as-the-graph-store.md) moved isolation into the engine with `FORCE ROW LEVEL SECURITY`, because an application predicate fails open |
| `ticket-frontend-prototype.md` | Recommends vanilla JS, Vite and Alpine.js. The repo consolidated on the existing Next 16 / React 19 app in `frontend/` (commit `25568a1`) |
| `MASTER_RESEARCH_INDEX.md` | Neo4j-centred, and recommends FalkorDB — which ADR-0002 rejected on **SSPLv1**, whose terms require releasing the source of a service built on it |
| `PHASE_1_TICKETS.md` | Phase 1 as originally scoped, against the pre-research architecture |

`ticket-infra-design.md` stayed in `../` — its three-stack split and deadly-embrace
guidance survived the architecture change and is the spec for
[T-600](../tickets/T-600-split-infra-stacks.md).
