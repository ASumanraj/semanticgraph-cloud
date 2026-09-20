# T-105 · Make the domain model obey the five irreversible rules

**Stage** 1 · **Type** work · **Status** open · **Owner** — · **Branch** `t-105-domain-invariants`

**Scope**
- `src/semanticgraph/domain/**`
- `src/semanticgraph/application/**`
- `src/semanticgraph/adapters/outbound/inmemory/**`
- `tests/unit/**`

**Blocked by** — · **Blocks** T-200, T-202, T-203, T-204, T-205, T-206

## Goal

`domain/models/entities.py` contradicts every one of the five irreversible rules in
`AGENTS.md`. It is 120 lines and cheap to fix now. Once T-200 generates the baseline
migration, these contradictions are encoded in the schema and fixing them becomes a
data migration plus a rewrite of every ticket downstream.

The worst of them, because it fails *open* directly above the RLS built to fail closed:

```python
tenant_id: TenantId = field(default_factory=lambda: TenantId(uuid4()))
```

Six entities carry that. Construct any of them without a tenant and you get a fresh,
valid-looking, random tenant instead of an error — plausible data belonging to nobody.

The rest, rule by rule:

| Rule | Contradiction today |
|---|---|
| 1 — provenance is mandatory | `RawEntity.source_chunk_id: ChunkId \| None = None`; `Edge` has no provenance at all |
| 2 — isolation fails closed | the `tenant_id` default above, on six entities |
| 3 — resolution is non-destructive | `GoldenRecord.merged_from: list[EntityId]` is destructive history on the record |
| 4 — facts die by assertion count | nothing models an assertion, so nothing can be counted |
| 5 — ontologies are immutable | `Ontology` has no version |

Also collapse the two ingestion paths. `ingest_document.py` and `process_document.py`
overlap; the API, the worker and any future workflow engine must enter through one
canonical pipeline or behaviour diverges between them.

## Acceptance

- [ ] `tenant_id` is required on every domain entity — constructing one without it raises `TypeError`, asserted by a test
- [ ] Provenance is a **collection** of evidence spans, not a nullable chunk id: `Assertion → EvidenceSpan[]` with `chunk_id`, `start_offset`, `end_offset`, `quote`
- [ ] `Edge` carries provenance and a validity interval
- [ ] `GoldenRecord.merged_from` is gone; the record is a projection of decisions
- [ ] `Ontology` carries an immutable `version`
- [ ] **Unresolved is a first-class state** — a `RawEntity` need not belong to a `GoldenRecord`, and the model distinguishes resolved, probable, unresolved and explicitly-disambiguated
- [ ] One canonical ingestion path; the API and the worker call the same interface
- [ ] Domain tests reject incomplete objects rather than accepting them
- [ ] `ruff check .` clean and the full suite green

## Notes

Multiple spans now, not one. A claim supported by two sentences is normal in contracts,
and moving from one span to many later is a schema rewrite — the exact class of change
this ticket exists to prevent.

Scope is wider than usual on purpose: removing a default from a domain dataclass ripples
into every caller, so the use cases, the in-memory adapters and the unit tests move with
it. It stays disjoint from T-200, which owns `alembic/**` and
`adapters/outbound/postgres/models.py`.

**T-200 is claimed and in progress on `t-200-alembic-baseline`. Its `alembic/versions/`
is still empty.** This ticket must land on `main` and T-200 rebase onto it before the
baseline migration is generated.
