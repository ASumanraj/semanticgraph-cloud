# ADR-0001: Hexagonal Architecture for SemanticGraph Cloud

## Status
**Accepted** — 2026-09-20

## Deciders
- Platform Team

## Context
The SemanticGraph Cloud platform has accumulated duplicate scaffolds (`backend/`, `src/api/`, `src/semanticgraph/`, `infrastructure/`, `infra/`) from parallel agent sessions, making the codebase impossible to navigate. We need a single, authoritative structure that separates business logic from infrastructure and enables testability without real databases or LLMs.

## Decision
We adopt **Hexagonal Architecture (Ports & Adapters)** as the canonical structure:

```
src/semanticgraph/
├── domain/          # Pure business entities (NO framework imports)
├── application/     # Use cases + Port definitions (Protocols)
├── adapters/        # Inbound (FastAPI, Celery) & Outbound (Neo4j, LLM, Postgres)
└── composition/     # Wiring: connects adapters to ports
```

**Key rules:**
1. `domain/` and `application/` NEVER import `fastapi`, `celery`, `neo4j`, or any adapter.
2. All infrastructure dependencies are injected through Ports (Python `Protocol` or `ABC`).
3. Tests exercise the use case through the Port interface, using in-memory fakes.

## Alternatives Considered
- **Flat module structure** — Rejected: leads to god objects and circular imports at scale.
- **Microservices** — Rejected: premature for current team size. Monolith-first, extract later.
- **Clean Architecture (Uncle Bob layers)** — Considered: functionally equivalent but Hexagonal's port/adapter vocabulary maps better to our multi-database reality (Neo4j + Postgres + Redis).

## Consequences
- **Positive:** Domain logic is testable in <50ms with zero infrastructure. Adding a new database (e.g., swapping Neo4j for FalkorDB) only requires a new adapter.
- **Trade-off:** Slightly more boilerplate (port definitions). Justified by the leverage across all future phases.
- **Risk:** Developers must resist the urge to import `fastapi` inside `domain/`. Enforced via linting rules.
