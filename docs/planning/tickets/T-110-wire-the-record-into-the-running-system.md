# T-110 · Wire the record into the running system — the first vertical slice

**Stage** 3 · **Type** work · **Status** done · **Owner** Antigravity · **Branch** `t-110-wire-the-record`

**Scope**
- `src/semanticgraph/composition/**`
- `src/semanticgraph/adapters/inbound/api/**`
- `src/semanticgraph/adapters/outbound/inmemory/**`
- `src/semanticgraph/application/ports/outbound/**`
- `src/semanticgraph/application/use_cases/**`
- `src/semanticgraph/domain/models/**`
- `tests/e2e/**`
- `tests/integration/adapters/api/**`
- `tests/unit/ports/**`
- `tests/unit/use_cases/**`

**Blocked by** T-106, T-214 · **Blocks** T-209, T-904 wave 2

## Goal

Stage 2 built six Postgres repositories and all five irreversible rules, and the running
system cannot reach any of them. Checked on `main` at `91775e8`:

- `Container` has five fields — document repository, graph repository, LLM gateway, task
  publisher, object storage — and none is a Stage 2 repository
- the API has **one** route, `POST /ingest`; nothing reads a fact, and nothing deletes a
  document
- the `postgres` profile persists documents and chunks, and still builds an in-memory graph
  repository, LLM gateway and task publisher
- the rules are proven by integration tests and `scripts/demo_contract_workflow.py`, which
  call the repositories directly

That is real work and the schema is right, but the product a customer touches doesn't have
it yet. This ticket closes the gap with one thin slice, no wider than it needs to be:

```
upload a contract
  → extract (a test double returning claim + verbatim quote taken from the chunk)
  → persist assertions with located spans, in Postgres
  → GET a fact and receive its evidence spans          "click a fact, land on the sentence"
  → DELETE a document → facts fall by assertion count  "delete one, only its unsupported facts die"
```

## Acceptance

- [x] The `postgres` profile builds the real Postgres adapters for assertions and facts, resolution, ontology and deletion; that profile contains no in-memory graph repository
- [x] `GET /api/v1/facts/{id}` returns the claim and its evidence spans (chunk id, offsets, quote), and the test asserts `chunk.text[start:end] == quote` on the HTTP response
- [x] `DELETE /api/v1/documents/{id}` runs the assertion-counted cascade: a fact asserted by two documents survives the first delete and is gone after the second
- [x] One end-to-end test drives this over HTTP against a real Postgres and asserts row and assertion counts **with raw SQL**, not through the repository that wrote them
- [x] Over HTTP, tenant B gets nothing for tenant A's fact and document ids, and an unfiltered SQL query as the application role returns no rows
- [x] The tenant still comes from the unsigned `X-Tenant-ID` header; the ticket states that this is a stand-in until Stage 5 and is not presented as authentication
- [x] `GraphRepositoryPort`, the combined shim T-106 left behind, is deleted. `IngestDocumentUseCase` and the search use case take **required** narrow ports (`EntityStore`, `SubgraphReader`, and the rest) — no union or `None`-default dependency parameters, so constructing one without a gateway or store is a `TypeError`, not a runtime surprise
- [x] The container has one field per narrow port, and the Stage 2 repositories are wired into those fields
- [x] A test compares each port with its Postgres implementation by **signature** — method names, parameter order and async-ness — not with `isinstance`, which on a runtime-checkable Protocol only proves the names exist. (The T-106 review found no mismatches; this keeps it that way)
- [x] The container builds `ModelRouting` (T-214) and hands it to the extraction double; no model id appears in `src/` outside that configuration and the price schedules, and the app refuses to start if a routable model is unpriced
- [x] The response or startup log makes visible which model dependencies are hosted, so no customer text reaches a hosted model implicitly
- [x] No route beyond these two, no UI, and no live model call
- [x] Full suite green and `ruff check .` clean

## Notes

Overlaps T-209's scope (`composition/container.py`, `adapters/inbound/**`). **Do not run them
together** — T-209 instruments what this ticket builds, so this goes first.

The extraction double must return a quote that exists in the chunk; a fabricated quote has to
be rejected by the span locator from T-202, and one test should prove it through the API.

This is the milestone the outside review named: document, chunk, span-backed assertion,
graph rows in Postgres, cited result. It is also the first thing worth showing anyone.
