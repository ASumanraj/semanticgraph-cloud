# SemanticGraph Cloud

Multi-tenant knowledge-graph substrate. Documents in, ontology-constrained extraction,
resolution into Golden Records, subgraph retrieval with citations.

`docs/architecture/ENTERPRISE_PLAN.md` is the authoritative architecture and the work
queue — read it before designing anything, and tick its progress tracker as items land.
`DOMAIN_SPEC.md` is the glossary. `docs/adr/` holds the individual decisions.

Pre-research documents live in `docs/architecture/superseded/` — they specify Neo4j and Celery,
both replaced. `ENTERPRISE_PLAN.md` wins wherever they disagree.

## Skills

Check the available skills before starting and run the one that fits. They carry
conventions this file has no room for, and they are cheaper than rediscovering the
same pattern.

| Working on | Reach for |
|---|---|
| A feature, a bug, a refactor | `tdd-workflow` |
| Routes, dependencies, response models | `fastapi`, `api-design` |
| Repositories, queries, migrations | `backend-patterns` |
| Anything under `frontend/` | `frontend-patterns`, `nextjs-turbopack` |
| Driving the UI in a browser | `e2e-testing` |
| CDK stacks under `infra/` | `aws-cdk` |

`.agents/skills/README.md` lists the rest and where each came from.

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
usage, audit. Graph algorithms run in-process over a per-tenant subgraph. The pipeline runs on
Celery today; ADR-0003 moves it to Temporal once a workflow has to pause for a human decision,
and until then steps are idempotent and retry-safe and no Temporal code is added.

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

## Working in parallel

Several agents run at once. `docs/planning/tickets/INDEX.md` is the board and
`docs/planning/tickets/README.md` is the protocol; the short version:

**Scope is the lock.** Every ticket lists the paths it may write. Work only inside
your ticket's Scope — a change that belongs elsewhere is a new ticket, because the
agent holding that path is mid-slice and will lose it in a merge.

**Claim before you branch.** Set `Status: claimed` and `Owner`, commit that one file
to `main`, push. A rejected push means someone claimed first: pull and pick another.
Then branch as the ticket names.

**Migrations take turns.** Anything adding an Alembic revision shares one chain.
Follow the `Blocked by` order; two revisions generated concurrently leave two heads.

**Finish through a PR.** Tests green, `ruff check .` clean, Acceptance ticked, then
review. Review is what catches a test that passes without testing anything.

## Proving it works

Passing against the in-memory adapters shows the shape is right. It does not show
the system runs. Every stage also earns one path exercised end to end, on real
infrastructure.

**Backend** — a real Postgres, from `docker compose` or testcontainers, rather than
SQLite or the in-memory profile. Post a document to the HTTP API, let the worker
process it, then query the database directly and assert the rows arrived with the
right `tenant_id`, provenance spans and status. Reading the rows back through the
same repository that wrote them proves less than reading them with SQL.

**Frontend** — a real browser. Drive the actual upload control, watch the request
reach the API, and assert what the user sees afterwards. `e2e-testing` covers page
objects, fixtures and flake control. After a UI change, a screenshot of the page is
the cheapest evidence it still renders.

The fast suite keeps the loop tight; the end-to-end path is what shows ingestion
works.

## Cost discipline

LLM extraction is 65–80% of the cost of running this product, so treat tokens as a budget
you are spending on the user's behalf.

Keep the cached prefix byte-identical across calls — a timestamp, a UUID, or an unsorted
`json.dumps()` in the prompt prefix drops the cache hit rate to zero silently and costs
roughly 10× more. Assert `usage.cache_read_input_tokens > 0` in integration tests.

Route by difficulty: Haiku for contextual blurbs and resolution adjudication, Sonnet for
extraction, Opus only on escalation. Use the Batch API for bulk ingest; it stacks with caching.
Whether a new tenant's first documents go interactive instead is undecided (T-906), so do not
assume nothing in ingest is latency-sensitive.

## Conventions

Commit messages explain what changed and why, and carry no tool attribution.

Telemetry carries IDs and hashes. Document text stays out of logs, traces, and span
attributes — observability retention is a disclosed GDPR exposure.
