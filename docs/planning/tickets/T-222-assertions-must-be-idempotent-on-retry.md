# T-222 · Retrying ingestion adds a second assertion per fact

**Stage** 3 · **Type** work · **Status** open · **Owner** — · **Branch** `t-222-idempotent-assertions`

**Scope**
- `src/semanticgraph/application/use_cases/ingest_document.py`
- `src/semanticgraph/adapters/outbound/postgres/provenance_repository.py`
- `src/semanticgraph/adapters/outbound/inmemory/assertion_store.py`
- `tests/unit/use_cases/**`
- `tests/integration/adapters/postgres/**`

**Blocked by** [T-218](T-218-persist-graph-and-expose-it-over-http.md) (shares `ingest_document.py`) · **Blocks** —

## Goal

Found while reviewing T-218 slice 2. After T-218 made chunks, entities and edges retry-safe, running
`IngestDocumentUseCase.execute` twice with the same command against a real Postgres gives:

```
after run 1: semantic_chunks 2, entities 2, edges 2, facts 2, assertions 2, evidence_spans 2
after run 2: semantic_chunks 2, entities 2, edges 2, facts 2, assertions 4, evidence_spans 4
```

Fact ids are `uuid5(tenant, claim)`, so they are stable. Assertion ids come from the extractor's fresh
`uuid4()` each run, and `save_fact` adds them, so every retry adds a duplicate assertion and evidence
span to each fact. AGENTS.md requires ingestion steps to be idempotent and retry-safe. Rule 4 says a
fact lives while assertions remain; a retry must not inflate that count.

## Design

Make an assertion's identity depend on what it asserts, not on when it was extracted: a stable id (for
example `uuid5` of document, chunk, fact and span), or an upsert keyed on (tenant, fact, document,
chunk, span). The in-memory and Postgres stores must behave the same. Keep the ontology-conformance and
span-verification behaviour untouched.

## Acceptance

- [ ] Ingesting the same document twice leaves `facts`, `assertions` and `evidence_spans` unchanged after the second run, proven with raw SQL on a real Postgres (not the store's own reader)
- [ ] The test fails on `main` before the fix
- [ ] Two different documents asserting the same claim still give one fact with two assertions (Rule 4 unaffected), and deleting one leaves the fact alive
- [ ] The in-memory adapter behaves the same, with a unit test
- [ ] Full suite green under a real Postgres, `ruff check .` clean
