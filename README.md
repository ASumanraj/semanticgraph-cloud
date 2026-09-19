# SemanticGraph Cloud

A multi-tenant knowledge-graph substrate. Documents go in; they are parsed, chunked, and passed
through ontology-constrained extraction; entities are resolved into **Golden Records** against
controlled vocabularies; and questions are answered from retrieved subgraphs with citations back
to the exact source span.

Built as an API for teams building AI products that need a private, auditable knowledge graph per
customer.

> **Status: pre-alpha.** The hexagonal core, the API surface and the test harness exist. The
> extraction, resolution and retrieval pipeline is Stage 3 of
> [the plan](docs/architecture/ENTERPRISE_PLAN.md).

## Why a graph

Vector retrieval answers most questions well and is cheaper. A knowledge graph earns its cost on
exactly three query classes, and this product is built for those and nothing else:

- **Relational** — "which agreements share a counterparty with this one?"
- **Temporal** — "who was the signatory *at the time* of the amendment?"
- **Aggregate** — "which MSAs have uncapped liability and auto-renew in Q1?"

Every answer carries its provenance, because a fact without a traceable source is not auditable
and cannot be deleted on request.

## Getting started

```bash
git clone https://github.com/ASumanraj/semanticgraph-cloud.git
cd semanticgraph-cloud

python -m venv .venv && .venv/Scripts/activate   # PowerShell: .venv\Scripts\Activate.ps1
pip install -e ".[dev]"

pytest -q          # 39 passing
ruff check .
```

Frontend:

```bash
cd frontend && npm ci && npm run dev
```

## Layout

```
src/semanticgraph/     the application — hexagonal, see ADR-0001
  domain/              pure business objects; imports no framework
  application/         use cases and outbound Protocol ports
  adapters/            FastAPI and workers in; Postgres, LLM, vocabularies out
  composition/         the single wiring point
frontend/              Next.js dashboard — ontology, explorer, evaluations
infra/                 AWS CDK
tests/                 unit / integration / e2e, mirroring the architecture
docs/                  architecture, ADRs, planning
```

## Architecture

Postgres is the system of record for everything — documents, chunks, facts, edges, vectors,
resolution decisions, usage and audit. Tenant isolation is enforced by the database through
row-level security rather than by application predicates, because a forgotten predicate should
return nothing rather than someone else's data.

Five properties are fixed at the schema level because they have no backfill path: mandatory
provenance spans, fail-closed tenant isolation, non-destructive resolution, assertion-counted
deletion, and immutable ontology versions. They are stated in
[`AGENTS.md`](AGENTS.md) and specified in the plan.

- **[`docs/architecture/ENTERPRISE_PLAN.md`](docs/architecture/ENTERPRISE_PLAN.md)** — the
  authoritative architecture and the work queue, with a progress tracker
- **[`docs/adr/`](docs/adr/README.md)** — the individual decisions and what they cost
- **[`DOMAIN_SPEC.md`](DOMAIN_SPEC.md)** — the glossary; terms here are used exactly

## Contributing

`AGENTS.md` is the contract for both humans and coding agents. Tests come first, the hexagon
boundary is enforced by a test, and commit messages explain why.
