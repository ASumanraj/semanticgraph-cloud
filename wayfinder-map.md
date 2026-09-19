## Destination

Phase 1 Backend architecture, AWS infrastructure definitions, and Frontend prototyping strategy are rigorously defined, researched, and locked in so that development execution can safely begin without ambiguity.

## Notes

Domain: Managed GraphRAG Multi-Tenant System
Skills required: `fastapi`, `aws-cdk`, `modern-web-guidance`
Standing preferences: TDD (Red/Amber/Green), Subgraphs evaluated by Ragas/TruLens, strict Ontology enforcement.

## Decisions so far

- [Backend Architecture Pattern](file:///S:/semanticgraph-cloud/tickets/ticket-backend-design.md) — FastAPI DI via `Annotated`, SQLModel schemas, strict `APIRouter` `tenant_id` isolation.
- [AWS CDK Infrastructure Layout](file:///S:/semanticgraph-cloud/tickets/ticket-infra-design.md) — Multi-stack (Network, Database, Compute), weak cross-stack references, SSM lookups, L2 grants.
- [Frontend Prototyping APIs](file:///S:/semanticgraph-cloud/tickets/ticket-frontend-prototype.md) — Vanilla JS/Vite, native `<dialog>`, Popover API, CSS Anchor Positioning, and View Transitions.

- How will the `tenant_id` context propagate through Celery background tasks securely without leaking?
- Graph migrations: How are Ontology schema updates managed in Neo4j safely across tenants?

## Out of scope

- Implementation of Ragas/TruLens evaluation (Phase 6).
- Resolution & Disambiguation logic (Phase 4 & 5).
