# T-906 · Decide how ingestion trades cost against time-to-first-answer

**Stage** 3 · **Type** research · **Status** open · **Owner** — · **Branch** `t-906-batch-versus-interactive`

**Scope**
- `docs/research/**`
- `docs/adr/**`

**Blocked by** — · **Blocks** Stage 3 extraction design

## Question

ENTERPRISE_PLAN.md Part 5 puts everything in the ingest path on the model provider's Batch
API for the discount, which stacks with prompt caching. The acceptance protocol from T-903
promises a design partner a corpus that is queryable within hours. Batch results take up to
a day, so both cannot hold for the same document.

Which documents go through which path, and what does that do to price?

Candidates to weigh:

- Batch for bulk backfill, interactive for a new tenant's first N documents
- Interactive for everything, priced accordingly
- Batch only, with the onboarding promise changed

## Resolution

_Open._ Read the provider's Batch documentation itself: the stated completion window and
whether there is any faster typical figure, the discount, whether it stacks with prompt
caching, request-size and count limits, and what happens to an expired batch. Then work
through:

- what a design partner's first 500 documents cost on each path, using the per-document
  model in Part 5
- what "queryable" has to mean on day one — perhaps only the first 20 documents, not all
- whether the workflow engine's retry model (ADR-0003) copes with an expired batch

Record the choice as ADR-0005 with the numbers, and update Part 5 if the unit economics move.
