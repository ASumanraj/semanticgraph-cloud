# T-202 · Mandatory provenance spans

**Stage** 2 · **Type** work · **Status** open · **Owner** — · **Branch** `t-202-provenance-spans`

**Scope**
- `alembic/**`
- `src/semanticgraph/domain/provenance/**`
- `src/semanticgraph/domain/models/entities.py`
- `src/semanticgraph/adapters/outbound/postgres/**`

**Blocked by** T-201 · **Blocks** T-203, T-206

## Goal
Build the chain `document → chunk → mention(span) → fact_assertion → fact`, with the
span **non-nullable**. Irreversible rule 1, and the most expensive thing in the
project to get wrong: without complete spans, deletion, citation, hallucination
detection and incremental update are all retroactively impossible, and the only fix
is re-extracting every corpus at full cost.

## Acceptance
- [ ] `fact_assertion` carries `fact_id`, `chunk_id`, span and `extraction_run_id`, all non-nullable
- [ ] A fact is alive while at least one live assertion supports it
- [ ] The span is mandatory in the extraction schema handed to the model, not only in the table
- [ ] A helper verifies a claimed span actually exists in its chunk text
- [ ] A test proves a fact cannot be written without an assertion

## Notes
Span verification is a deterministic, zero-cost hallucination detector — it catches a
large class of fabrication for free. ENTERPRISE_PLAN.md Part 2.1.
