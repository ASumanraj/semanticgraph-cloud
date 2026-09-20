# T-202 · Span-backed assertions, located deterministically

**Stage** 2 · **Type** work · **Status** open · **Owner** — · **Branch** `t-202-provenance-spans`

**Scope**
- `alembic/**`
- `src/semanticgraph/domain/provenance/**`
- `src/semanticgraph/adapters/outbound/postgres/**`
- `src/semanticgraph/adapters/outbound/extraction/**`
- `tests/unit/domain/**`
- `tests/integration/adapters/postgres/**`

**Blocked by** T-105, T-201 · **Blocks** T-203, T-206

## Goal

Persist the chain `document → chunk → assertion → evidence span → fact`, where a fact
lives only while some assertion still supports it. Irreversible rule 1, and the most
expensive thing in the project to get wrong — without it, deletion, citation and
hallucination detection are all retroactively impossible, and the only repair is
re-extracting every corpus at full cost.

**The model does not emit character offsets.** Language models are unreliable at
counting characters, so an offset it returns is a promise, not a fact. Ask instead for:

```
claim            what the fact asserts
verbatim_quote   the exact text supporting it
chunk_id         where to look
```

Then **locate the quote deterministically** inside that chunk and compute the offsets
yourself. If the quote is not found, the assertion is rejected or flagged — never
stored. That turns provenance from something the model promises into something the code
enforces, and it is a free hallucination detector: a fabricated claim rarely comes with
a quote that exists.

**One assertion carries many spans.** A contract claim supported by two sentences is
ordinary. Modelling a single span and widening later is a schema rewrite.

## Acceptance

- [ ] `Assertion` holds `EvidenceSpan[]`, each with `chunk_id`, `start_offset`, `end_offset`, `quote` — the collection is non-empty by construction
- [ ] The extraction contract requests claim + verbatim quote + chunk id, and **never** an offset
- [ ] Offsets are computed by locating the quote in the chunk; a quote that cannot be located is rejected or flagged, and a test proves a fabricated quote does not reach the database
- [ ] Normalisation that shifts offsets (whitespace, unicode, ligatures) is applied **before** offsets are computed, and a round-trip test proves `chunk.text[start:end] == quote` after storage
- [ ] A fact is alive while at least one live assertion supports it
- [ ] An assertion spanning two sentences round-trips both spans
- [ ] Provenance completeness is 100% — enforced by the schema, not measured by a report

## Notes

Nothing in the field does this. Read at `main` on 2026-09-20: GraphRAG uses
`text_unit_ids`, Graphiti `episodes: list[str]`, Cognee `source_task` stamps, RAGFlow
`source_id` — all chunk-granularity — and LightRAG actively discards provenance past 200
source ids per entity (`DEFAULT_MAX_SOURCE_IDS_PER_ENTITY`). See
[`docs/research/pipeline-comparison-and-acceptance.md`](../../research/pipeline-comparison-and-acceptance.md).

This is the differentiator with the least competition and the shortest path to a demo no
competitor can screenshot: click a fact, land on the sentence.
