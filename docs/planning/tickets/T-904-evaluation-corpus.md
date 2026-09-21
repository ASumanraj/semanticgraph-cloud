# T-904 · Build the four-track evaluation corpus

**Stage** 4 · **Type** work · **Status** claimed · **Owner** claude · **Branch** `t-904-evaluation-corpus`

**Scope**
- `evals/**`
- `tests/unit/evals/**`
- `docs/research/**`

**Blocked by** — (wave 1) · **Blocks** the Stage 4 gold set

## Goal

Build the corpus and the labelling protocol that everything after Stage 3 is measured
against, before more is built on guesses.

Two things prompted this. The contracts ontology pack was started with no labelled data:
`ontologies/contracts/corpus/` holds two contracts between fictional companies that appear
to be synthetic and written alongside the extractor, and a system scored on documents its
author wrote will look good. And the pack's `Obligation.obligation_type` is a free `string`
with nothing modelling a liability cap, auto-renewal or termination right — so the flagship
question, *"which agreements have uncapped liability and auto-renewal?"*, cannot run as a
graph query. **The corpus should decide which clause types exist, not the other way round.**

## Design

| Track | Source | Use it for | Not for |
|---|---|---|---|
| A · CUAD | 510 EDGAR contracts, 41 clause categories, 13,000+ labels, CC BY 4.0 | clause-extraction recall; choosing the clause types | span exactness (labels are paragraph-level — verify), OCR |
| B · ContractNLI | 607 NDAs, 17 fixed hypotheses, evidence as character-offset sentence / list-item spans, CC BY 4.0 | a smoke test for the verifier; checking span location on NDAs | anything beyond NDAs; task shape differs (whole-contract premise, fixed hypotheses) |
| C · EDGAR | about ten companies' EX-10 exhibits, including amendments and restatements | pipeline realism, long documents, amendments, cross-document entity mentions | scans — official filings are HTML or ASCII, PDFs are unofficial copies |
| D · Scanned | the same documents rendered and degraded, plus about 20 real scanned contracts | OCR robustness | — |

**Splits.** By company, contract family or period — never by random document. Track C is
6 development / 2 validation / 2 sealed holdout. Ontology changes, prompts and resolution
rules may use development data only.

**Two waves of labels.**
- *Wave 1, now, no pipeline needed:* system-independent ground truth — gold clauses, gold
  party names and gold questions with document, page and quote. This is the recall side.
- *Wave 2, after the Stage 3 extractor exists:* label the system's own outputs as
  supports / partially supports / contradicts / unrelated, errors included. This is the
  precision side and the set the verifier bake-off needs. Assertions cannot be labelled
  before something produces them.

**What this corpus is.** Public contracts are very likely in model pretraining data — an
inference, not a checked fact. It is a reproducible engineering benchmark. Only a design
partner's documents are genuinely unseen, and results must be reported that way.

## Acceptance

- [ ] Every document has a manifest row: id, source URL, licence, content hash, track, split
- [ ] A test fails if any company or contract family appears in more than one split
- [ ] Ten companies are chosen across industries, at least three with amendments or restatements, with the rationale recorded
- [ ] A shortlist of 10–20 clause types is derived from CUAD and the demo questions, showing how each demo question maps onto them
- [ ] The wave-1 protocol states who labels, what counts as a match, and reports agreement on a 30-question overlap. Labels come from a **paid, qualified commercial-contract reviewer** (a contract manager, legal-operations analyst, paralegal or commercial lawyer), with a second such reviewer on the overlap. Labels produced by a model or an untrained annotator are called *draft* or *silver* and are never described as gold
- [ ] Track D uses the same document clean and degraded, documents how offsets are re-aligned after OCR, and states that synthetic degradation understates real scans
- [ ] Each source's licence and terms are read from the source itself, not from a summary
- [ ] The corpus README states what the corpus can and cannot show

## Notes

**Decision, 2026-09-21 (product owner):** wave 1 starts as a **10-document pilot with a cap of 40 paid
reviewer hours**, reassessed against actual effort before expanding. Labels from the paid,
qualified reviewer are gold. Labels from the product owner and friends are **draft** and are used to
rehearse the protocol and to produce an agreement figure; they are never described as gold.

Out of scope: pipeline code, and changes to the ontology — hand the clause-type shortlist to
whoever owns the contracts pack as a recommendation, not an edit.

**Follow-on experiments, opened when the Stage 3 extractor lands:**
- *Verifier bake-off.* A verifier port, then Jev, Haiku and a small local NLI model on
  wave-2 labels, with ContractNLI as the smoke test. Timeout, low confidence and malformed
  output all mean **unverified**, never false. Jev only on public data until it documents
  retention, training, subprocessors and regions, and an air-gapped tier needs a local
  alternative regardless.
- *Wiki baseline.* A deliberately competent folder-of-Markdown agent on the same model and
  token budget, run at 50, 200, 500 and 2,000 documents. The output is the **crossover
  point** where it stops keeping up, not a scoreboard. Tenant isolation is a feature
  comparison, not an experiment — a folder has none.
- *Local-alternative evaluation.* Run the local models named in `ModelRouting` against the wave-1
  labels for extraction, adjudication and embeddings, and record accuracy, hardware footprint
  and licence for each. Until then they are candidates, not alternatives, and an air-gapped
  customer cannot be promised one.
- *Registry coverage:* see [T-905](T-905-gleif-coverage-spike.md), which needs no pipeline.
