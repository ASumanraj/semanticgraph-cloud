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
- `src/semanticgraph/application/use_cases/ingest_document.py` (added 2026-09-25, see slice 2 review)
- `tests/unit/use_cases/**` (added 2026-09-25)

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

## Review, slice 1 (tables, migration, RLS tests) — 2026-09-24

Reviewed branch `t-218-postgres-graph-and-route` at `0524a8f`. The schema is sound: one new revision
(`65f7a3919e0a`) off `e8f1a2c3b4d5`, a single head, `tenant_id` leading every composite index,
`FORCE ROW LEVEL SECURITY` and a tenant policy copied exactly from the existing migrations' pattern,
`GRANT ... TO semanticgraph_app`, provenance columns non-null on both tables, valid_from/valid_to kept
on edges. `ruff check .` clean. Two of the three new isolation tests pass against a real Postgres.
**Slice 1 is not accepted; two defects, both reproduced against a real Postgres (testcontainers), not
argued.**

**1. Deleting a document that has extracted entities now fails (Irreversible Rule 4).**
`entities.chunk_id` and `edges.chunk_id` are foreign keys to `semantic_chunks` with no `ON DELETE`,
and `PostgresDeletionRepository.delete_document_cascade` knows nothing about the new tables. Repro:
migrate to head, save a document + chunk, insert one entity and one edge pointing at that chunk (as
`IngestDocumentUseCase` will once slice 2 wires the store), call `delete_document_cascade`. Result:
`ForeignKeyViolation: update or delete on table "semantic_chunks" violates foreign key constraint
"entities_chunk_id_fkey"`, at the "Delete chunks" step. Today nothing writes these rows, so nothing
breaks yet; the moment slice 2 wires `PostgresEntityStore`, **every document with an extracted entity
becomes undeletable**, which is the GDPR path. The cascade must reach these tables in the same
transaction, like embeddings, caches and summaries already do (`deletion_repository.py`, steps 5-9),
and `test_deletion_cascade.py` needs a case for it (its `clean_db` table list too).
Design points the fix must settle and prove: entity/edge rows are per-chunk assertions, so delete the
ones whose `chunk_id` belongs to the document; an edge from *another* document may reference an
entity id of the deleted one (no FK on `source_entity_id`/`target_entity_id`) — state which it is
(shared ids or per-mention ids) and test that no dangling edge survives and that a fact still asserted
by a second document is untouched.

**2. One of the three new isolation tests fails when it actually runs.**
`test_tenant_a_cannot_read_or_spoof_tenant_b_entities_and_edges` fails with
`InFailedSqlTransaction: current transaction is aborted` at the edge insert: the first
`pytest.raises(InsufficientPrivilege)` insert aborts the enclosing transaction, so the second statement
cannot run. Each expected-failure statement needs its own savepoint (`with conn.transaction():`
inside the `pytest.raises`), or its own connection. The report said "356 passed, 53 skipped" — those
skips are the Postgres-backed tests, so this test was never executed before being reported. Run the
integration directory with a real Postgres (Docker is available) before reporting.

**Minor, fix in the same pass:** `start_offset`, `end_offset` and `quote` default to `0`/`""` on both
models. Rule 1 says the span is mandatory, including at the ORM: an extractor that forgets it should
fail, not persist `(0, 0, "")`. `SQLEvidenceSpan` has no such defaults. Remove them (model-only; the
migration has no server default).

**Fix direction:** same branch, slice 1 only: cascade in `deletion_repository.py` + a deletion test,
the savepoint fix, drop the provenance defaults. Then show `pytest tests/integration/adapters/postgres/
-q` under a real Postgres with the counts, and a CI run. Do not start slice 2 until this is accepted.

## Review, slice 1 fix verified — 2026-09-24

Reviewed PR #19 (`89d9af4`). All three findings are fixed and independently reproduced, not read off
the report:

- **Deletion cascade.** `delete_document_cascade` now deletes the document's entities and every edge
  asserted by its chunks or touching its entity ids, before the chunk delete, in the same transaction.
  The new test proves the delete succeeds, no dangling edge survives (including an incoming edge from
  a second document), and a fact asserted by two documents keeps the second assertion. It is not
  vacuous: with `deletion_repository.py` reverted to `main`, that test fails with the exact
  `ForeignKeyViolation ... entities_chunk_id_fkey` from the original defect. Entity ids are
  per-mention (per-chunk), as the report states; cross-document identity lives at the Golden Record.
- **Savepoint test.** Passes; the whole `tests/integration/adapters/postgres/` directory under a real
  Postgres is **43 passed, 0 skipped** on my run, matching the report.
- **Provenance defaults** removed from both models; the migration is unchanged, still one head
  (`65f7a3919e0a`), `ruff check .` clean.

CI [run 36043772040](https://github.com/ASumanraj/semanticgraph-cloud/actions/runs/36043772040) on
`89d9af4`: green on both jobs, Isolation proofs and Control-plane proofs each `success`.

One note, accepted: `application/ports/outbound/deletion_repository.py` gained `deleted_entities_count`
and `deleted_edges_count` (default 0, included in `total_records_erased`). It is outside the ticket's
literal Scope but is the necessary result-shape change for the cascade; no other adapter is affected.

Slice 1 accepted; slice 2 (repository + `Container.postgres()` wiring) may begin once PR #19 is
merged. Status stays `claimed` until the HTTP route lands.

## Review, slice 2 (store + reader + wiring) — 2026-09-25

Reviewed PR #20 (`f7f8925`). CI is green and the store code is careful (span validation, endpoint
existence check, tenant session copied from the house pattern, cycle-safe recursive CTE). **Not
accepted: the idempotency claim is false on the real ingestion path, and the test that should have
caught it does not exist.** Both reproduced against a real Postgres with a scratch test (removed).

**1. Running the real use case twice duplicates everything.** `test_graph_repository.py`'s docstring
lists "IngestDocumentUseCase execution against real Postgres" as test 6; the use case is imported and
never called. I ran `IngestDocumentUseCase.execute` twice with the same command (same document id)
against the Postgres store: after run 1, `semantic_chunks`/`entities`/`edges` = 2/2/2; after run 2 =
**4/4/4**. Cause: `_chunk_document` gives every chunk a fresh random id on each run, `save_chunks` is a
plain insert, so the retry writes new chunks, and the store's "same chunk_id + name + span" dedupe
never matches because `chunk_id` differs. The store-level test passes only because it reuses one
`chunk_id` by hand. The duplicated chunks predate this ticket, but AGENTS.md requires idempotent,
retry-safe steps and my slice-2 instruction required it end to end.

**2. A duplicate mention in one batch makes edge saving fail.** `save_raw_entities` re-links a
duplicate `(chunk, name, span)` by mutating `entity.id`, but edges hold their own copy of the old id.
With `[Acme, Acme(dup), Beta]` plus an edge from the duplicate to Beta, `save_edges` raises
`ValueError: ... source_entity_id ... does not exist in entities table`, after the entities and chunks
are already committed. An extractor emitting the same mention twice is realistic. The store cannot fix
the edge objects it never sees; the ids must be reconciled where both lists are in hand, in
`IngestDocumentUseCase`.

**Scope extended** (nobody else holds these; T-105 is done): `application/use_cases/ingest_document.py`
and `tests/unit/use_cases/**`.

**Fix direction:**
- Deterministic chunk ids: `uuid5(document_id, chunk_index)` (facts already use `uuid5`, same idea),
  and make `save_chunks` an upsert so a retry is a no-op. Same document twice must give 2/2/2, not 4/4/4.
- In the use case, dedupe extracted entities by `(chunk_id, name, start, end)` and rewrite edge
  endpoints to the surviving id before saving; drop edges that become exact duplicates.
- Add the missing real-Postgres test that calls `IngestDocumentUseCase.execute` (twice) and reads
  entity/edge/chunk counts with raw SQL, plus the duplicate-mention case.

**Also fix in this pass (small):** escape `%`, `_` and `\` in the seed-match and `find_similar_entities`
`ILIKE` patterns (a query of `%` currently matches every entity in the tenant); `find_similar_entities`
maps each row twice and ignores `threshold`, so say so in its docstring or use it.

**For slice 3, not now:** the recursive CTE enumerates paths, which grows fast on dense graphs. The
HTTP route must clamp `depth` (max 3) and cap returned rows, and say when a result was truncated.

## Review, slice 2 fix verified — 2026-09-25

Reviewed PR #20 (`f88495a`). Independently reproduced, not read off the report:

- The five new tests (three real-Postgres, two unit) **fail against the previous source** (`f7f8925`)
  and pass on the fix, so they test the defects. Running `IngestDocumentUseCase.execute` twice against
  Postgres now leaves `semantic_chunks`/`entities`/`edges` at 2/2/2 (was 4/4/4). The duplicate-mention
  batch with an edge saves cleanly. A `%` or `_` query no longer matches everything.
- `tests/integration/adapters/postgres/`: **56 passed, 0 skipped**. Fast suite: 425 passed, 1 skipped,
  2 deselected. `ruff check .` clean, one Alembic head (`65f7a3919e0a`).
- CI [run 36052230341](https://github.com/ASumanraj/semanticgraph-cloud/actions/runs/36052230341) on
  `f88495a`: green on both jobs, Isolation proofs, Control-plane proofs and E2E each `success`.

**Known gap, not blocking this slice:** the same double-run leaves `assertions` and `evidence_spans` at
4 for 2 facts. Facts are deterministic (`uuid5`), assertions are not, so a retry adds a second assertion
per fact. It predates this ticket and does not affect correctness of the delete cascade (the document's
assertions all go together), but it inflates assertion counts and breaks "retry-safe". Filed as T-222;
it touches `ingest_document.py`, so it starts after T-218.

Slice 2 accepted. Slice 3 (HTTP route) may begin once PR #20 is merged.
