# Wayfinder map

## Destination

A multi-tenant knowledge-graph substrate sold as an API, with one pre-built
contracts ontology proving a customer needs no forward-deployed engineer to get
value. Entity resolution grounded in an external controlled vocabulary, facts that
carry their provenance and their validity window, and isolation the database
enforces rather than the application remembers.

## Notes

Domain: managed GraphRAG, multi-tenant.
Skills: see the table in [`AGENTS.md`](../../AGENTS.md).
Standing preferences: TDD red-before-green; one vertical slice at a time; every
stage earns one path proven end to end on real infrastructure.

## Decisions so far

- [ADR-0001](../adr/0001-hexagonal-architecture.md) — hexagonal architecture; the boundary is enforced by a test
- [ADR-0002](../adr/0002-postgres-as-the-graph-store.md) — Postgres, pgvector and RLS as the canonical store, not Neo4j
- [ADR-0003](../adr/0003-temporal-for-the-document-pipeline.md) — Temporal for the pipeline, not Celery or Step Functions
- [Infrastructure layout](ticket-infra-design.md) — Network / Database / Compute stacks, one-way dependency flow

## Open questions

- [T-900](tickets/T-900-verify-whyhow-ai.md) — what happened to WhyHow.AI, and does the answer change the wedge?
- [T-901](tickets/T-901-temporal-cloud-cost.md) — what does Temporal Cloud actually cost at our document volume?
- Which controlled vocabulary ships first? LEI/CIK is the recommendation — free, authoritative, and the contracts ontology is reusable across every customer.
- How does tenant context cross the worker boundary without leaking? [T-209](tickets/T-209-otel-tenant-attribution.md) answers half of it; the security half is still open.

## Out of scope

- Resolution and disambiguation algorithms beyond the decision log — Stage 3
- Ragas or DeepEval evaluation — Stage 4
- SSO, SCIM and billing — Stage 5
- BYOC, and any certification audit — Stage 7

## Where work lives

[`tickets/INDEX.md`](tickets/INDEX.md) is the board.
[`ENTERPRISE_PLAN.md`](../architecture/ENTERPRISE_PLAN.md) is the architecture and
the stage ordering. Superseded planning material is in
[`superseded/`](superseded/README.md).
