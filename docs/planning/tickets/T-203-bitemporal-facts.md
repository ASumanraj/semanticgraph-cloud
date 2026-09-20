# T-203 · Bi-temporal facts with edge invalidation

**Stage** 2 · **Type** work · **Status** done · **Owner** Antigravity · **Branch** `t-203-bitemporal-facts`

**Scope**
- `alembic/**`
- `src/semanticgraph/domain/temporal/**`
- `src/semanticgraph/adapters/outbound/postgres/**`
- `tests/unit/domain/**`
- `tests/integration/adapters/postgres/**`

**Blocked by** T-202 · **Blocks** —

## Goal
Two timelines: when a fact was true in the world (`valid_from`/`valid_to`) and when
the system learned it (`created_at`/`expired_at`). A contradicting fact **closes the
old one's validity window** rather than deleting it, so "who was CFO at the time of
the filing" stays answerable.

## Acceptance
- [x] Facts carry both intervals
- [x] Superseding a fact closes the prior validity window and leaves the row in place
- [x] A query can ask for the graph as it was believed at a past instant
- [x] A test asserts a superseded fact is still retrievable with its closed window

## Notes
Graphiti's model is the reference (arXiv 2501.13956). Temporal correctness at
document scale is one of the four defensible differentiators in Part 0.1.
