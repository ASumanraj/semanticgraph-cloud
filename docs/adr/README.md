# Architecture Decision Records

| ADR | Title | Status | Date |
|-----|-------|--------|------|
| [0001](0001-hexagonal-architecture.md) | Hexagonal Architecture for SemanticGraph Cloud | Accepted — graph-store choice superseded by 0002 | 2026-09-20 |
| [0002](0002-postgres-as-the-graph-store.md) | Postgres as the canonical graph store, not Neo4j | Accepted | 2026-09-20 |
| [0003](0003-temporal-for-the-document-pipeline.md) | Temporal for the document pipeline, not Celery | Accepted | 2026-09-20 |
| [0004](0004-external-knowledge-formats-are-projections.md) | External knowledge formats are projections, not canonical storage | Accepted | 2026-09-20 |

The architecture these decisions compose into, and the work queue that implements them, is
[`docs/architecture/ENTERPRISE_PLAN.md`](../architecture/ENTERPRISE_PLAN.md).
