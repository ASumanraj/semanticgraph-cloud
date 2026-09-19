# SemanticGraph Cloud

Multi-tenant knowledge-graph substrate. Documents in, ontology-constrained extraction,
resolution into Golden Records, subgraph retrieval with citations.

`docs/architecture/ENTERPRISE_PLAN.md` is the authoritative architecture and the work
queue — read it before designing anything, and tick its progress tracker as items land.
`DOMAIN_SPEC.md` is the glossary. `docs/adr/` holds the individual decisions.

`ARCHITECTURE.md` is the pre-research design and is **stale**: it specifies Neo4j and
Celery, both replaced. Trust `ENTERPRISE_PLAN.md` wherever the two disagree.

## The five irreversible rules

These are schema properties with no backfill path. Violating one is not a bug to fix
later — it is a full re-ingestion of every customer's corpus. Hold them in mind on every
change that touches persistence.

1. **Provenance is mandatory.** Every fact carries `chunk_id` and the character span it
   came from, non-nullable, including in the extraction schema handed to the model. Spans
   are what make deletion, citation, and hallucination-checking possible at all.
2. **Tenant isolation fails closed.** `tenant_id` on every table, leading every composite
   index. `FORCE ROW LEVEL SECURITY`, an app role that does not own the tables, and tenant
   context set with `SET LOCAL` *inside the transaction* — a session-level `SET` survives on
   a pooled connection and hands the next caller the previous tenant's data.
3. **Resolution is non-destructive.** A Golden Record is a projection of a versioned
   decision log. Merging inserts a decision; unmerging retracts one. A human decision
   outranks every model decision, permanently and across model upgrades.
4. **Facts die by assertion count.** Deleting a document removes its assertions; a fact
   survives while any other document still asserts it. The cascade reaches embeddings,
   caches, community summaries, and eval fixtures, in one transaction.
5. **Ontologies are immutable.** Editing publishes a new version. Every extraction run
   records the `ontology_version` it ran under.

## Architecture

Hexagonal, and the hexagon is enforced by a test: `domain/` and `application/` import no
framework, no driver, no SDK. Dependencies enter through Protocol ports in
`application/ports/outbound/`, are implemented in `adapters/outbound/`, and are wired in
one place — `composition/`.

Postgres holds everything: documents, chunks, mentions, facts, edges, vectors, decisions,
usage, audit. Graph algorithms run in-process over a per-tenant subgraph. Temporal runs
the document pipeline; its activities are the expensive, retryable units.

Build **deep modules** — a large hidden implementation behind a small interface. Extraction,
resolution, and retrieval each earn one entry point.

## Vocabulary

Use `DOMAIN_SPEC.md`'s terms exactly — *Document*, *Semantic Chunk*, *Raw Entity*,
*Golden Record*, *Edge*, *Ontology*, *Resolution*. A term absent from that file does not
exist in this domain; add it there first, then use it.

## Working rhythm

Take one vertical slice at a time: a failing test, the code that passes it, then stop.

Write the failing test first, against the port or the HTTP surface — the test exercises the
interface a caller would use, with real fakes at the boundary rather than patched internals.

Drive through failures on your own. A failing test or a build error is the next input, not
a reason to check in. When the *same* error survives three consecutive attempts, stop and
report the trace and what you think is blocking it.

Report at the end of the slice, in a few lines: what changed and what the tests say.

## Cost discipline

LLM extraction is 65–80% of the cost of running this product, so treat tokens as a budget
you are spending on the user's behalf.

Keep the cached prefix byte-identical across calls — a timestamp, a UUID, or an unsorted
`json.dumps()` in the prompt prefix drops the cache hit rate to zero silently and costs
roughly 10× more. Assert `usage.cache_read_input_tokens > 0` in integration tests.

Route by difficulty: Haiku for contextual blurbs and resolution adjudication, Sonnet for
extraction, Opus only on escalation. Use the Batch API for anything in the ingest path —
it stacks with caching and nothing there needs sub-24h latency.

## Conventions

Commit messages explain what changed and why, and carry no tool attribution.

Telemetry carries IDs and hashes. Document text stays out of logs, traces, and span
attributes — observability retention is a disclosed GDPR exposure.
