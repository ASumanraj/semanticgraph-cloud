# T-903 · Compare the pipeline to competitors and define the customer acceptance test

**Stage** — · **Type** research · **Status** done · **Owner** claude · **Branch** `t-903-pipeline-comparison-and-acceptance`

**Scope**
- `docs/research/**`
- `docs/adr/**` (a new ADR, if the findings warrant one)

**Blocked by** — · **Blocks** —

## Question
Two halves, both about whether the product survives contact with a real buyer.

1. **Pipeline mechanics.** ENTERPRISE_PLAN.md Part 0.1 compares competitors at the
   product level. This is the level below: how do Graphiti, Cognee, LlamaIndex
   PropertyGraphIndex, RAGFlow and Microsoft GraphRAG actually ingest a document —
   parse, chunk, extract, resolve, index — and where does the design in Stage 3
   genuinely differ rather than differ in wording? Name the steps that are
   table stakes and the ones that are ours.

2. **The acceptance test.** If a design partner hands over a corpus next month,
   what proves the product works for *them*? Not unit tests — the evaluation a
   buyer would run: a golden corpus, the questions it must answer, the accuracy and
   cost thresholds, and what a failed onboarding looks like early enough to fix.

## Resolution
**Done** — [`docs/research/pipeline-comparison-and-acceptance.md`](../../research/pipeline-comparison-and-acceptance.md).

Source read at `main` on 2026-09-20 for Graphiti/Zep, Cognee, LlamaIndex
PropertyGraphIndex, RAGFlow, Microsoft GraphRAG and LightRAG, plus the papers.
The report carries a stage-by-stage table (parse · chunk · contextualize · extract ·
resolve · store · retrieve), a verdict on each claimed differentiator, a six-week
design-partner protocol with thresholds, and a "what would make a buyer say no" list.

**Pipeline — what the source says.** Nobody stores character spans; every system
records provenance at chunk granularity at best, and LightRAG *drops* source ids past
200 per entity. Resolution is a `groupby` on the surface name in GraphRAG, LightRAG and
Cognee; Graphiti (exact → cosine ≥0.6 → LLM) and RAGFlow (Levenshtein gate → batched LLM)
do it properly but destructively, with no retractable decision and no human-over-model
precedence anywhere. Cognee's "ontology resolver" is `difflib.get_close_matches(cutoff=0.8)`.
GraphRAG is in maintenance mode by its own README and resolves entities with
`groupby("title")`.

**Table stakes, not ours:** structure-aware chunking (RAGFlow is ahead of Stage 3 today),
contextual blurbs (RAGFlow `auto_keywords`/`auto_questions`/RAPTOR, LightRAG heading
breadcrumbs), ontology-constrained decoding *and* post-decode triple-legality validation
(LlamaIndex `SchemaLLMPathExtractor` + `_prune_invalid_triplets`), lazy community
summarisation (Microsoft's own LazyGraphRAG result), and the GLiNER prefilter — RAGFlow
ships a spaCy NER extractor and GraphRAG ships noun-phrase extractors. GLiNER-L is 47.8
average zero-shot F1, so as a *gate* it silently drops chunks: keep it as a cost lever,
tune for recall, alarm on skip rate, never pitch it as quality.

**Genuinely ours:** mandatory character spans (nobody has them), a retractable resolution
decision log with permanent human precedence, registry-anchored resolution (real, but
GLEIF covers ~2.5M entities — "unresolved" must be a supported state, not an error),
immutable versioned ontologies, engine-enforced isolation, and assertion-counted deletion.
Bi-temporality is *half* ours: Graphiti already ships `valid_at`/`invalid_at` with
contradiction-driven expiry, so the claim is contract semantics over documents, not a
category first. **Sell the record the pipeline produces, not the pipeline.**

**Acceptance test.** 200–500 stratified real documents, 150 partner-authored questions
(60 single-hop / 45 multi-hop / 25 temporal / 20 unanswerable), 60/40 with the holdout
sealed by the partner, six weeks, fixed scope and price. Thresholds: entity F1 ≥0.75,
triple F1 ≥0.60, ontology conformance ≥99.5%, span-grounding and provenance completeness
100% (enforced, not measured), resolution precision ≥0.95 / recall ≥0.80 with over-merge
<2%, citation precision ≥0.90 / recall ≥0.85, multi-hop recall@10 ≥0.80, abstention ≥0.90.
Budgets: ≤$0.09/doc, ≤$45 for the pilot corpus, `cache_read_input_tokens > 0` on every
call, retrieval P95 ≤350 ms, answer P95 ≤4 s. Week 5 is adversarial — deletion, human-
decision durability across a forced model upgrade, isolation, temporal supersession,
injection. A 12-item day-one pre-flight checklist probes text-layer/OCR, encoding and
offset-shifting normalisation, tables, document size, near-duplicates, acronyms,
language mix, entity density, cache-prefix integrity, span round-trip, erasure and
injection.

**Two things this surfaced for other stages.** The Batch API's ≤24h latency conflicts
with a "500 documents queryable in 4 hours" onboarding promise — a Stage 3 decision, not
yet made. And LEI/CIK coverage on a real contracts corpus is unmeasured; it decides how
strongly the resolution differentiator can be claimed and is cheap to measure against the
GLEIF golden-copy file before Stage 3 starts.
