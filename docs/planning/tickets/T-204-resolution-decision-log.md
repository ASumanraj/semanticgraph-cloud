# T-204 · Non-destructive resolution decision log

**Stage** 2 · **Type** work · **Status** open · **Owner** — · **Branch** `t-204-resolution-decision-log`

**Scope**
- `alembic/**`
- `src/semanticgraph/domain/models/entities.py`
- `src/semanticgraph/adapters/outbound/postgres/**`

**Blocked by** T-203 · **Blocks** —

## Goal
A Golden Record becomes a **projection of a versioned decision log**, never a row
that gets rewritten. Merging inserts a decision; unmerging retracts one.
Irreversible rule 3.

Store merges destructively and unmerge is unimplementable — you ship "contact
support to undo".

## Acceptance
- [ ] `mention` is immutable; `cluster_membership` carries `decision_id`, `source`, `confidence`, `decided_at`
- [ ] `golden_record` is materialized from current memberships, not written directly
- [ ] `source` distinguishes human, model and rule decisions
- [ ] **A human decision survives a full model re-run**, asserted by a test
- [ ] Unmerge is a retraction and restores the prior grouping

## Notes
Without human precedence, every model upgrade silently re-merges entities a customer
already separated — the most trust-destroying bug this product can have. Expect
roughly 80–90 F1 as the accuracy ceiling and design to survive being wrong; the
review queue is a product surface, not an admin page.
