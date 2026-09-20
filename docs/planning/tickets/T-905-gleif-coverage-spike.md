# T-905 · Measure how many contract counterparties a legal-entity registry can resolve

**Stage** 3 · **Type** research · **Status** open · **Owner** — · **Branch** `t-905-gleif-coverage-spike`

**Scope**
- `evals/gleif/**`
- `tests/unit/evals/**`
- `docs/research/**`
- `docs/architecture/ENTERPRISE_PLAN.md` (Part 0.1 only)

**Blocked by** — · **Blocks** any resolution code that assumes registry anchoring

## Question

Of the organisations named in real contracts, what fraction can be resolved to a GLEIF LEI,
and with what precision?

This decides how loudly the registry-anchored-resolution claim can be made. A CIK does not
help: on an EDGAR exhibit it identifies the filer, not the counterparties, and many
counterparties are private.

**Measure it without the pipeline.** Start from *gold* party names — CUAD's `Parties`
labels, if that category exists as I believe (the Zenodo page does not list the 41 categories,
so confirm it; otherwise hand-label about 200 party mentions). Using gold names separates
registry coverage from extraction quality; using our own extractor's output would blur them.

## Resolution

_Open._ Normalise each name, then match against the GLEIF Golden Copy Level 1 records and
bucket every mention as:

- exact LEI match
- candidate needing human confirmation
- unresolved
- private entity with no LEI
- subsidiary / parent ambiguity
- inactive or lapsed LEI

Check precision on a hand-verified sample per bucket.

**Decision rules, fixed before running.** The thresholds are my judgement — adjust them
before the run, not after:

| Coverage (exact + confirmed candidate) with ≥98% precision | Consequence |
|---|---|
| ≥ 70% | Registry anchoring is the headline |
| 40–70% | An enrichment; Splink plus adjudication is the primary resolver, and *unresolved* is shown prominently |
| < 40% | Optional integration; do not market it as a differentiator |

Any false merge in the exact-match tier stops the work until it is understood.

**Caveats to state in the report.** Public-company contracts skew towards larger
counterparties, so this is an upper bound for a real customer. GLEIF's Level 2 ownership data
depends on entities reporting their parents, and reporting exceptions exist. The Golden Copy
page did not state a licence — **confirm GLEIF's terms from GLEIF before any commercial
use.**

## Acceptance

- [ ] The measurement script is reproducible from `evals/gleif/`, with a unit test on the matching logic
- [ ] GLEIF's licence and terms are read from GLEIF and recorded
- [ ] Every bucket has a count, and precision from a hand-checked sample
- [ ] The decision rule above is applied and the outcome written into ENTERPRISE_PLAN.md Part 0.1
- [ ] No dependency on pipeline code
