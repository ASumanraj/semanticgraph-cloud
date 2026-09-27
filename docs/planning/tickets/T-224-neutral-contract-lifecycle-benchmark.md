# T-224 · A neutral, event-level benchmark for contract-lifecycle graphs

**Stage** 4 · **Type** work · **Status** open · **Owner** — · **Branch** `t-224-lifecycle-benchmark`

**Scope**
- `evals/lifecycle/**` (new directory)
- `docs/research/**`

**Blocked by** [T-218](T-218-persist-graph-and-expose-it-over-http.md) and [T-222](T-222-assertions-must-be-idempotent-on-retry.md)
for our own adapter; the spec and the Graphiti adapter can start earlier · **Blocks** any published
"first" claim

## Goal

The prior-art note found one concrete competitor gap: in Graphiti 0.30.2 (commit `47f6482`),
`remove_episode` deletes an edge when its **first** asserting episode is removed even if a later episode
still asserts it (reproduced with embedded Kuzu, `docs/research/artifacts/graphiti-remove-episode-repro.py`).
That is one deletion path in one product. It cannot carry a claim. What can is a **neutral, published,
reproducible benchmark** of several event types, run fairly against more than one implementation, including
ours.

## Design

Event-level cases, each with a written oracle (the correct answer), over public documents:

1. **Point-in-time:** the state of a fact, party or obligation as of a stated date before and after a change.
2. **Amendment and supersession:** an amendment changes a term; which text is current, and which is superseded.
3. **Two-source support and deletion:** a fact supported by two documents; delete one, then the other.
   Graphiti's first-asserter behaviour is one instance, not the test.
4. **Entity-resolution corrections:** a merge, an unmerge, a human "these are different", and a model
   upgrade that must not undo it.
5. **Downstream impact:** given a changed source, list the affected facts, parties and deadlines, each with
   the supporting text.

Fairness rules, written down before running: every system runs in its documented default deployment;
where a case isolates lifecycle behaviour, extraction is replaced by a shared fixed extraction fixture so
model quality does not decide the result; pin every version and commit; publish the harness, fixtures and
oracles; a system that cannot express a case is marked "not supported", not "failed"; run each case several
times and report variance. Hypothesis to check before adopting the corpus: amended credit agreements filed
publicly on SEC EDGAR, plus CUAD contracts.

## Acceptance

- [ ] A written spec (event types, oracles, fairness rules, corpus choice with licences) reviewed before any code
- [ ] A harness with one adapter per system behind a small interface; adapters for Graphiti (embedded Kuzu, pinned commit) and for ours
- [ ] Every case runs against both, results reproducible from a clean checkout with one documented command
- [ ] Results reported per case with "not supported" distinguished from "failed", and the Graphiti `remove_episode` case shown as one row among the others
- [ ] A short note stating what the benchmark does and does not show, and the exact wording of any claim it supports

## Notes

Do not turn this into a marketing artifact: cases where our system fails or is unsupported are published
too. Retire or reword the narrow claim in the prior-art note if a competitor documents the combination.
