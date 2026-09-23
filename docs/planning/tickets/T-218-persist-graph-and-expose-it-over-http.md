# T-218 · Persist the extracted graph to Postgres and expose it over HTTP

**Stage** 3 · **Type** work · **Status** claimed · **Owner** Antigravity · **Branch** `t-218-postgres-graph-and-route`

**Scope**
- `alembic/versions/**` (one new revision — take a turn per `README.md`)
- `src/semanticgraph/adapters/outbound/postgres/**`
- `src/semanticgraph/application/use_cases/search_subgraph.py`
- `src/semanticgraph/adapters/inbound/api/v1/**` (new route file)
- `src/semanticgraph/composition/container.py`
- `tests/integration/adapters/postgres/**`
- `tests/integration/adapters/api/**`

**Blocked by** T-217 should land first if both are claimed (shared file, see its Notes) · **Blocks** —

## Goal

`frontend/src/components/GraphExplorer.tsx` (T-111) now honestly fetches `GET /api/v1/graph` and
shows an empty state when there's nothing to show — which is every time, because **that route
doesn't exist, and the graph it would read has nowhere real to live even if it did.**

Traced the full chain before writing this:

1. `IngestDocumentUseCase.execute()` (`application/use_cases/ingest_document.py:126-169`) **already
   calls** `llm_gateway.extract_entities_and_edges(...)` and **already calls**
   `entity_store.save_raw_entities(...)` / `entity_store.save_edges(...)` for every ingested
   document. This part of the pipeline is real and wired.
2. But `Container.postgres()` (`composition/container.py:204-205`) sets
   `entity_store=InMemoryEntityStore()` and `subgraph_reader=InMemorySubgraphReader()` —
   **unconditionally, even in the Postgres profile.** Every real document's extracted entities and
   edges are written to a process-local dict and vanish on restart. There is no `entities` or
   `edges` table in `adapters/outbound/postgres/models.py` at all — the `EntityStore` port's own
   docstring says adapters live "in `adapters/outbound/inmemory/` and `adapters/outbound/postgres/`"
   but the Postgres one was never built.
3. `SearchEngine` (`application/use_cases/search_subgraph.py`) — `local_search`/`global_search` call
   `run_semantic_pagerank`/`run_leiden_community_detection`, both empty stub function bodies that
   return `None`. The module docstring says so explicitly: *"Both are stubs. The shape is fixed
   here so the seam exists; Stage 3 fills them."*
4. No route in `adapters/inbound/api/v1/` reads a subgraph at all today (`documents.py`, `facts.py`
   are the only two files).

So this is not a thin plumbing ticket. **This ticket does not attempt full Stage 3 retrieval** —
personalized PageRank ranking and Leiden community summaries stay stubbed, per
`ENTERPRISE_PLAN.md`'s own stance that global search should be lazy and built later. What it does
build: a real, durable, tenant-isolated place for extracted entities and edges to live, and a
truthful, unranked read of them — enough for `GraphExplorer` to show the graph that was actually
extracted from a tenant's real documents, with real provenance, instead of nothing.

## Design

**Persistence** — new `SQLRawEntity`/`SQLEdge` tables in `models.py`, one Alembic revision:
`tenant_id` leading every composite index, `FORCE ROW LEVEL SECURITY` with a tenant policy, the
`semanticgraph_app` role and `SET LOCAL`-inside-transaction pattern already established in
`provenance_repository.py` (irreversible rules 2 and the `_tenant_session` convention used there and
in every other Postgres repository). `Edge` rows carry `valid_from`/`valid_to` per the existing
domain model — persist them as columns, don't collapse the temporal fields away.

**Write side** — `PostgresEntityStore` implementing `EntityStore`
(`save_raw_entities`, `save_edges`, `find_similar_entities`). Wire it into `Container.postgres()` in
place of `InMemoryEntityStore()`.

**Read side** — `PostgresSubgraphReader` implementing `SubgraphReader.search_subgraph(tenant_id,
query, depth=2)`: a real, bounded SQL query — match seed entities by name against the query
(`ILIKE` or `pg_trgm` is enough for this slice, no vector search yet), then expand `depth` hops over
the `edges` table via a recursive CTE, tenant-scoped by RLS like every other repository. No ranking,
no deduplication beyond what's already at the row level — return what's really there. Wire it into
`Container.postgres()` in place of `InMemorySubgraphReader()`.

**HTTP** — new `adapters/inbound/api/v1/graph.py`, `GET /api/v1/graph?query=...` (match the path
`GraphExplorer.tsx` already calls — don't rename it out from under the frontend), same
`CurrentTenantDep` pattern as `facts.py`, returns nodes and edges with their provenance spans. Empty
result is a real empty result (no data yet for that tenant), not a stub returning nothing because
nothing is implemented.

## Acceptance

- [ ] `entities`/`edges` tables exist via one Alembic migration, `tenant_id` leads every composite index, FORCE RLS + non-owner app role, matching the pattern in `test_tenant_isolation.py`
- [ ] `PostgresEntityStore` and `PostgresSubgraphReader` are wired into `Container.postgres()`, replacing both in-memory adapters
- [ ] Ingesting a real document through the HTTP API, then querying `GET /api/v1/graph`, returns the entities and edges actually extracted from it — proven against a real Postgres, not the in-memory profile
- [ ] Tenant isolation proven the same way `test_tenant_isolation.py` proves it for other tables: zero rows with no tenant context, tenant A cannot read tenant B's entities/edges
- [ ] `frontend/src/components/GraphExplorer.tsx` needs no change if the route path matches what it already calls — confirm this before merging, don't silently rename the endpoint
- [ ] Full suite green under `DATABASE_URL` set (see T-216 — write this ticket's tests assuming that fix has landed), `ruff check .` clean

## Notes

Explicitly out of scope, deferred to whenever Stage 3's retrieval design gets its own ticket:
personalized PageRank ranking, Leiden community detection, reranking, vector-seeded search. This
ticket's job is making the graph real and readable, not making it smart.

See also [T-217](T-217-wire-real-extractor-into-postgres-profile.md) — same
`composition/container.py`, don't run both at once.
