# SemanticGraph Cloud: System Design & Architecture

> **ADR:** See [docs/adr/](docs/adr/README.md) for all recorded architecture decisions.

## 1. Executive Summary

SemanticGraph Cloud is a multi-tenant Managed GraphRAG SaaS platform. It ingests unstructured **Documents**, partitions them into **Semantic Chunks**, and extracts **Entities** and **Edges** strictly adhering to a predefined **Ontology**. It performs complex **Resolution** and **Disambiguation** to maintain a clean graph of **Golden Records**, resolving queries by mathematically evaluating retrieved **Subgraphs**.

---

## 2. Canonical Directory Structure (Hexagonal Architecture)

> **ADR-0001:** We use Hexagonal Architecture (Ports & Adapters).  
> `domain/` and `application/` NEVER import framework or infrastructure code.

```text
semanticgraph-cloud/
│
├── src/semanticgraph/                   # The application
│   ├── domain/                          # Pure business logic (ZERO framework imports)
│   │   ├── models/
│   │   │   └── entities.py              # Document, SemanticChunk, RawEntity, GoldenRecord, Edge, Ontology
│   │   ├── value_objects/               # TenantId, ChunkId, EntityId
│   │   └── exceptions.py               # DomainException hierarchy
│   │
│   ├── application/                     # Use case orchestration + Port definitions
│   │   ├── ports/
│   │   │   ├── inbound/                 # Commands & queries (use case interfaces)
│   │   │   └── outbound/               # Abstract dependencies (Protocols)
│   │   │       ├── graph_repository.py  # Neo4j abstraction (tenant-aware)
│   │   │       ├── llm_gateway.py       # LLM extraction abstraction
│   │   │       └── task_publisher.py    # Celery/SQS abstraction
│   │   └── use_cases/
│   │       └── ingest_document.py       # Deep Module: bytes + ontology -> graph
│   │
│   ├── adapters/                        # Infrastructure implementations
│   │   ├── inbound/
│   │   │   ├── api/                     # FastAPI routers, middleware, DI
│   │   │   │   ├── dependencies.py      # Annotated DI (CurrentTenantDep, SessionDep)
│   │   │   │   ├── middleware.py        # Tenant resolution
│   │   │   │   └── v1/                  # Versioned route modules
│   │   │   └── workers/                 # Celery task consumers
│   │   │       └── tasks/
│   │   └── outbound/
│   │       ├── neo4j/                   # GraphRepositoryPort implementation
│   │       ├── postgres/                # SQLModel / RDS adapter
│   │       ├── llm/                     # Instructor-wrapped LLM adapter
│   │       └── celery/                  # TaskPublisherPort implementation
│   │
│   └── composition/                     # Wiring: connects adapters to ports
│       └── container.py                 # FastAPI Depends() factory chain
│
├── tests/
│   ├── unit/                            # Fast (<50ms), no infra
│   │   ├── domain/                      # Pure entity/value object tests
│   │   └── use_cases/                   # Use case tests with in-memory fakes
│   ├── integration/                     # Real DB/API tests
│   │   └── adapters/
│   │       ├── api/                     # FastAPI TestClient
│   │       ├── neo4j/                   # Cypher + tenant isolation
│   │       └── celery/                  # Eager-mode task tests
│   └── e2e/                             # Full user journeys
│
├── frontend/                            # Vanilla HTML/CSS/JS prototype (Vite)
├── infra/                               # AWS CDK (NetworkStack, DatabaseStack, ComputeStack)
├── docs/adr/                            # Architecture Decision Records
├── ECC/                                 # Engineering Command Center (skills library)
├── .agents/                             # Agent skills & memory
├── DOMAIN_SPEC.md                       # Ubiquitous language glossary
├── AGENTS.md                            # Agent execution guidelines
└── ARCHITECTURE.md                      # This file
```

### Legacy Directories (To Be Deprecated)
The following directories contain older scaffolds and should NOT be used for new code:
- `backend/` — Replaced by `src/semanticgraph/`
- `src/api/` — Replaced by `src/semanticgraph/adapters/inbound/api/`
- `src/pipeline/` — Replaced by `src/semanticgraph/application/use_cases/`
- `infrastructure/` — Replaced by `infra/`
- `models/` — Replaced by `src/semanticgraph/domain/models/`

---

## 3. Key Architectural Decisions

### 3.1 Multi-Tenant Isolation (Defense in Depth)
| Layer | Mechanism |
|-------|-----------|
| **API** | `Annotated[Tenant, Depends(get_current_tenant)]` at `APIRouter` level |
| **Postgres** | Row-Level Security (RLS) via `current_setting('app.current_tenant_id')` |
| **Neo4j** | `tenant_id` property on every node and edge; Cypher filters enforced in repository |
| **Redis** | Hierarchical key prefix: `tenant:{id}:*` |
| **Celery** | `tenant_id` embedded in task payload; workers validate before execution |

### 3.2 Deep Modules (Codebase Design)
| Module | Interface | Hidden Complexity |
|--------|-----------|-------------------|
| `IngestDocumentUseCase.execute()` | `(bytes, Ontology) -> Document` | Parsing, chunking, LLM calls, retries, graph writes |
| `GraphRepositoryPort` | 5 methods | Cypher queries, connection pooling, tenant filtering, transactions |
| `LLMGatewayPort` | 1 method | Prompt engineering, Instructor wrapping, token limits, retries |

### 3.3 Database Patterns (from ECC Skills)
- **Postgres:** `bigint` PKs, `timestamptz`, `jsonb` for metadata, GIN indexes, cursor pagination, `FOR UPDATE SKIP LOCKED` for job queues
- **Redis:** Cache-aside with TTLs, tag-based invalidation, distributed locks, Redis Streams for ingestion pipeline
- **Neo4j:** Repository pattern mapping Cypher records to domain entities

### 3.4 Production Readiness Gates
1. Build verification (zero errors)
2. Static type checking (`pyright`)
3. Linting (`ruff`)
4. Test suite (80%+ coverage)
5. Security scanning (no leaked keys)
6. Diff review

---

## 4. Development Execution Plan (Vertical Slices)

### Phase 1: Core Foundation & Multi-Tenant Silo ✅
### Phase 2: Document Ingestion & Task Queue
### Phase 3: Pydantic/Instructor Extraction Pipeline
### Phase 4: Resolution & Disambiguation Engine
### Phase 5: Querying & Ragas Evaluation
