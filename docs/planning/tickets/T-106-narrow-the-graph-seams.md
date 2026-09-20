# T-106 · Split GraphRepositoryPort into seams that mean something

**Stage** 1 · **Type** work · **Status** open · **Owner** — · **Branch** `t-106-narrow-the-graph-seams`

**Scope**
- `src/semanticgraph/application/ports/outbound/**`
- `src/semanticgraph/application/use_cases/**`
- `src/semanticgraph/adapters/outbound/inmemory/**`
- `tests/unit/**`

**Blocked by** T-105 · **Blocks** —

## Goal

`GraphRepositoryPort` declares five methods spanning three unrelated concerns:

```python
save_raw_entities(...)  # persistence
save_edges(...)  # persistence
find_similar_entities(...)  # search
merge_into_golden_record(...)  # resolution policy
search_subgraph(...)  # retrieval
```

A caller has to learn all of it to use any of it, which is the definition of a shallow
interface — the port is nearly as complex as what it hides.

The `merge_into_golden_record` method is the real problem: it lets a caller merge
directly, while irreversible rule 3 says a Golden Record is a **projection of a decision
log**. The port contradicts the rule it is supposed to serve. Resolution should insert a
decision; the record materializes from active decisions.

Split into seams that each hide something:

```
AssertionStore          assertions and their evidence spans
EntityStore             raw entities and edges
ResolutionDecisionStore decisions in, projections out — no direct merge
SubgraphReader          retrieval
```

## Acceptance

- [ ] `merge_into_golden_record` is gone; merging is recorded as a decision
- [ ] Golden Records are materialized from active decisions, never written directly
- [ ] Each new port hides more than it exposes — the deletion test applies: removing it should make complexity reappear across callers
- [ ] The in-memory adapters satisfy the new ports and stay the same implementation the unit tests use
- [ ] Architecture-fitness tests still pass
- [ ] Full suite green, `ruff check .` clean

## Notes

Does not block T-200 — it touches `application/` and the in-memory adapters, while T-200
owns `alembic/**` and `adapters/outbound/postgres/models.py`. It does depend on T-105,
which changes the domain objects these ports carry.

The `codebase-design` skill has the vocabulary: depth as leverage, the deletion test,
and one adapter meaning a hypothetical seam.
