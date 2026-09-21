# T-214 · One owner for model routing, and price versions that only append

**Stage** 2 · **Type** work · **Status** done · **Owner** Antigravity · **Branch** `t-214-model-routing-and-price-versions`

**Scope**
- `src/semanticgraph/composition/model_routing.py`
- `src/semanticgraph/control/usage/**`
- `tests/unit/control/**`
- `tests/unit/composition/**`

**Blocked by** — · **Blocks** T-110, T-210

## Goal

Two defects found reviewing T-212, one of them mine.

**1 · Model routing has the wrong owner.** `control/usage/routing.py` defines the default
routing configuration, and `ROUTABLE_MODELS` is derived from it. Its docstring says the LLM
gateway reads it. No gateway does — the gateway is a test double — so today the usage package
decides which model runs and then checks its own prices against that decision. The moment a
real gateway is written there are two sources of truth. The configuration that selects models
belongs with the gateway and the composition root, and pricing has to be checked against *it*.

**2 · Price versions are removed, which breaks reproducibility.** Every ledger event is stamped
with a `price_version` so an old invoice can be reproduced, and `record_correction` prices its
offsetting row from the **original** event's version. T-212 moved the old schedules into
`SAVED_SUPERSEDED_PRICE_SCHEDULES`, which nothing can select, so a correction to a row stamped
`2026-Q1` would raise `UnknownPriceVersionError`. Nothing is broken today because every row so
far comes from tests and the demo — but the rule has to be right before the first real row is
written. (I suggested deleting the old schedules in review. That was wrong for exactly this
reason.) The same block still carries numbers whose source could not be recovered, stamped
"retrieved 2026-03-01".

## Design

- A frozen `ModelRouting` in `composition/model_routing.py`: the extraction, escalation,
  adjudication, summarisation, contextual-blurb and embedding models. Each dependency also
  records `hosted: bool` and a `local_alternative`, so which models send customer text off the
  machine is visible in configuration rather than implicit.
- The container builds it from configuration. `control/usage` takes it as an argument and does
  not import from composition.
- Price schedules have two states. **Active**: may be stamped on new events. **Historical**:
  still resolvable for existing rows and their corrections, rejected for new events. A version
  that any event references is immutable — publish a new version, never edit or delete one.

## Acceptance

- [x] Model selection is defined once, in composition. `control/usage` has no default routing configuration and no model id outside the price schedules
- [x] `verify_routable_models_priced` takes a routing as an argument; a test supplies one with an unpriced model and fails. The check is a plain function that T-110 calls at startup; this ticket does not edit `composition/container.py`, which T-110 owns
- [x] Each price schedule carries an explicit state. A correction to a row stamped with a historical version prices correctly, and stamping a **new** event with a historical version raises a typed error
- [x] A checksum of each published version's numbers is committed, and a test fails if any of them changes — the mechanical form of "a referenced version is immutable"
- [x] The unsourced 2026-Q1 and 2026-Q2 numbers stay only as historical, labelled "source not recovered", with no retrieval date claimed for them
- [x] `ModelRouting` records, for every model, whether it is hosted and its local alternative. The default embedding model is a hosted OpenAI one: either name a local alternative, or record here why it is deferred and add it to the Stage 7 subprocessor checklist. Customer text must not reach a hosted model without that being visible in configuration
- [x] Full suite green and `ruff check .` clean

## Notes

ADR-0005, rule 6: every model dependency needs a local or customer-hosted alternative before
it can be required. T-110 depends on this because its container wiring consumes `ModelRouting`,
and T-210 depends on it because a spend cap that reads a ledger whose old versions cannot be
resolved will fail on the first correction.

Hosted embedding model decision (Acceptance 6):
The default embedding model `text-embedding-3-small` is hosted by OpenAI (`hosted=True`).
Local alternative named: `BAAI/bge-small-en-v1.5` (or `nomic-ai/nomic-embed-text-v1.5`).
OpenAI is recorded as a hosted model provider on the Stage 7 subprocessor checklist alongside Anthropic.
