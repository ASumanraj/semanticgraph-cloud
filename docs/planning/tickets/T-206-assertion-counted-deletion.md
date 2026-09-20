# T-206 · Assertion-counted deletion

**Stage** 2 · **Type** work · **Status** claimed · **Owner** Antigravity · **Branch** `t-206-assertion-counted-deletion`

**Scope**
- `alembic/**`
- `src/semanticgraph/application/use_cases/delete_document.py`
- `src/semanticgraph/adapters/outbound/postgres/**`
- `tests/unit/use_cases/**`
- `tests/integration/adapters/postgres/**`

**Blocked by** T-202 · **Blocks** —

## Goal
Deleting a document removes exactly its contribution. Cascade to chunks, then to
`fact_assertion`, then garbage-collect facts and cluster memberships with zero
remaining assertions, re-materialize affected Golden Records and invalidate the
summaries that quoted the removed text — in one transaction. Irreversible rule 4.

## Acceptance
- [ ] A fact supported by documents D and E survives deleting D
- [ ] The same fact disappears when E is also deleted
- [ ] The cascade reaches embeddings, caches and community summaries
- [ ] The whole cascade is one transaction
- [ ] Eval fixtures are tagged by source document so erasure can reach them too
- [ ] A test asserts provenance completeness stays 100% afterwards

## Notes
The EDPB made right-to-erasure its 2025 coordinated enforcement action, and the
Hamburg DPA's position is that embeddings may remain re-identifiable — "we deleted
the text but kept the vectors" is not a defensible answer. ENTERPRISE_PLAN.md Part
2.3.
