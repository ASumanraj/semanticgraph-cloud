# Pipeline mechanics vs. competitors, and the design-partner acceptance test

**Ticket** T-903 · **Date** 2026-09-20 · **Status** complete

Sources are primary where possible: competitor source code read at `main` on 2026-09-20,
their papers on arXiv, and their own issue trackers. Marketing pages are not cited.
Anything I could not verify from a primary source is marked **[UNVERIFIED]**.

Read alongside [`ENTERPRISE_PLAN.md`](../architecture/ENTERPRISE_PLAN.md) Part 0, Part 2,
Stage 3, Stage 4 and Part 5. Nothing here re-litigates Postgres
([ADR-0002](../adr/0002-postgres-as-the-graph-store.md)) or Temporal
([ADR-0003](../adr/0003-temporal-for-the-document-pipeline.md)).

---

# Part 1 — Pipeline mechanics, stage by stage

## 1.0 What was read

| System | What I read | Commit state |
|---|---|---|
| Microsoft GraphRAG | `packages/graphrag/graphrag/index/operations/extract_graph/graph_extractor.py`, `config/defaults.py`, `index/update/entities.py`, `packages/graphrag-input/`, `packages/graphrag-chunking/`, `README.md` | `main`, 2026-09-20 |
| LightRAG | `lightrag/constants.py`, `lightrag/operate.py` | `main`, 2026-09-20 |
| Graphiti / Zep | `graphiti_core/utils/maintenance/node_operations.py`, `edge_operations.py`, `edges.py`, `utils/content_chunking.py`, `driver/`, [arXiv 2501.13956](https://arxiv.org/abs/2501.13956) | `main`, 2026-09-20 |
| Cognee | `cognee/modules/chunking/TextChunker.py`, `tasks/chunks/chunk_by_paragraph.py`, `modules/ontology/matching_strategies.py`, `tasks/graph/extract_graph_from_data.py`, `tasks/graph/detect_contradictions.py`, `eval_framework/` | `main`, 2026-09-20 |
| LlamaIndex PropertyGraphIndex | `llama-index-core/.../property_graph/transformations/{schema_llm,simple_llm}.py`, `node_parser/interface.py` | `main`, 2026-09-20 |
| RAGFlow | `rag/graphrag/{entity_resolution,utils}.py`, `rag/graphrag/{general,light,ner}/`, `deepdoc/parser/`, `rag/svr/task_executor.py`, `rag/app/naive.py` | `main`, 2026-09-20 |

## 1.1 The comparison table

| | **Parse** | **Chunk** | **Contextualize** | **Extract** | **Resolve** | **Store / isolation / incremental** | **Retrieve** |
|---|---|---|---|---|---|---|---|
| **MS GraphRAG** ([repo](https://github.com/microsoft/graphrag)) | Not its job historically; now a `graphrag-input` package wrapping **MarkItDown** plus csv/json/jsonl/parquet readers. No layout model, no table structure, no OCR of its own. | Token chunker, **`size=1200`, `overlap=100`**, `o200k_base` (`config/defaults.py`). Sentence chunker available. Boundaries ignore document structure. | **None.** Chunk text is embedded and extracted from as-is. | `gpt-4.1` default. **Delimited-tuple text**, not structured output: `TUPLE_DELIMITER="<|>"`, `RECORD_DELIMITER="##"`, `COMPLETION_DELIMITER="<|COMPLETE|>"`, parsed with a regex *after* decode. Default entity types `["organization","person","geo","event"]`. Gleaning: `max_gleanings=1`, a `CONTINUE_PROMPT` loop with a `LOOP_PROMPT` asking the model to answer `Y`/`N`. **On any exception the extractor logs and returns two empty dataframes** — the chunk silently contributes nothing. | **Exact string match on `title`.** `_group_and_resolve_entities` does `merged.groupby("title")`, descriptions concatenated into a list and later LLM-summarised. Not reversible, no decision record. Known defect: same title + different type collapses to one node, [issue #1718](https://github.com/microsoft/graphrag/issues/1718) (opened 2025-02-18, **closed as not planned**). A reconciliation step has been requested since [issue #401](https://github.com/microsoft/graphrag/issues/401). | Parquet files on disk / blob + a vector store (LanceDB default). **No tenancy concept at all.** Incremental index exists (`index/update/`) but leaves [dangling ids after community update](https://github.com/microsoft/graphrag/issues/2540). | Local (entity-seeded), Global (map-reduce over **eagerly generated** Leiden community reports at every level), DRIFT, and Basic. Dynamic community selection added later to cut global cost. |
| **LightRAG** ([repo](https://github.com/HKUDS/LightRAG)) | Server-side parsers for docx/pdf/text; `DEFAULT_DOCX_*` guards against zip bombs. No layout model in core. | Token chunking, **`CHUNK_SIZE=1200`, `overlap=100`**; a paragraph mode (`DEFAULT_CHUNK_P_SIZE=2000`) with sentence regex and a references-dropping heuristic. | **Yes, cheaply and deterministically**: heading breadcrumbs are prepended as section context, capped at `DEFAULT_MAX_SECTION_CONTEXT_TOKENS=256`. No LLM call. | Delimiter mode (`tuple_delimiter="<|#|>"`) or JSON mode. `DEFAULT_MAX_GLEANING=1`. Caps: `MAX_EXTRACTION_RECORDS=100`, `MAX_EXTRACTION_ENTITIES=40`, input `MAX_EXTRACT_INPUT_TOKENS=20480`. | **Normalized exact name match.** `normalize_entity_name()` then dict merge; descriptions merged by `_combine_descriptions_dedup()` and LLM-summarised only when `force_llm_summary_on_merge=8` fragments accumulate. No embeddings, no LLM judgement, no reversibility. | Pluggable KV/vector/graph backends (NetworkX, Neo4j, Postgres+AGE, Milvus…). Workspace field, application-level. **Provenance is capped**: `DEFAULT_MAX_SOURCE_IDS_PER_ENTITY = 200` and `PER_RELATION = 200`, with a `KEEP`/`FIFO` limit method — beyond 200 supporting chunks, source ids are *dropped*. | naive / local / global / hybrid / mix. `TOP_K=40`, `CHUNK_TOP_K=20`, `COSINE_THRESHOLD=0.2`, `MAX_TOTAL_TOKENS=30000`, optional rerank (`RERANK_BINDING="null"` by default). |
| **Graphiti / Zep** ([repo](https://github.com/getzep/graphiti), [paper](https://arxiv.org/abs/2501.13956)) | None. Input is an *episode* (text/JSON/message) supplied by the caller. | `utils/content_chunking.py` — chunks only when content is big **and** estimated entity-dense; `CHARS_PER_TOKEN=4` heuristic, `CHUNK_MIN_TOKENS` gate, density estimated from capitalised-token ratio / JSON key count. | No blurb generation; instead an **episode context window** (previous episodes) is passed to extraction, and node summaries are generated and refreshed. | LLM structured output with typed entity classes; entity type descriptions built from docstrings and truncated at sentence boundaries. Edges carry an LLM-extracted `fact` sentence plus `valid_at` / `invalid_at` dates parsed from text. | **The best in this set.** Three tiers: exact-duplicate collapse → cosine candidate search with `NODE_DEDUP_COSINE_MIN_SCORE = 0.6` → LLM adjudication, recorded in a `uuid_map`. Still destructive: the losing uuid is remapped, not retained as a retractable decision. | Neo4j, FalkorDB, Kùzu, Neptune drivers. Tenancy is `group_id`, an **application-level predicate** — and it failed in production: [issue #1676](https://github.com/getzep/graphiti/issues/1676) (opened 2026-07-23, since closed) reports **19 episodes misplaced across 5 group graphs** because `self.driver = self.driver.clone(database=group_id)` mutated shared state under concurrency; "*this fails silently. No exception, no log line*". | Hybrid: BM25 + cosine + BFS graph expansion, with RRF / MMR / cross-encoder rerankers. Communities optional and built on demand. Zep reports **P95 300 ms** retrieval in the paper; the engineering blog claims **150 ms P95** after optimisation and ~92% episode-latency reduction from ~4 s [[blog](https://blog.getzep.com/scaling-agent-memory-zep-30x/)]. |
| **Cognee** ([repo](https://github.com/topoteretes/cognee)) | `Document` subclasses per type (pdf/docx/audio/image); no layout model of its own. | `chunk_by_paragraph` → `chunk_by_sentence`, batched up to `max_chunk_size`. **Chunk ids are content-hash derived** (`chunk_content_hash` + occurrence counter) — free boilerplate dedupe, and exact text reconstruction is a stated invariant. | No contextual blurb. Optional summarisation tasks exist downstream. | Pydantic `KnowledgeGraph` via structured output; also a 3-pass **cascade extractor** (nodes → relationship names → edge triplets) with separate prompts. Duplicate node ids within one chunk are dropped with a `logger.warning` and a code comment calling it "a lossy strategy". | **Exact, deterministic ids**: `Entity:<name>`. Optional ontology grounding is **`difflib.get_close_matches(..., cutoff=0.8)`** (`modules/ontology/matching_strategies.py`) against an RDF/OWL file's node names. Contradictions: an **opt-in, off-by-default** LLM task that adds a `contradicts` edge and never rewrites anything. | Pluggable graph + vector + relational stores. Multi-tenant via dataset/user scoping at app level. Provenance = `source_pipeline` / `source_task` stamps plus chunk linkage. | Graph completion / insights / chunk search, plus its own `eval_framework` with HotpotQA and synthetic-corpus adapters. |
| **LlamaIndex PropertyGraphIndex** ([repo](https://github.com/run-llama/llama_index)) | Whatever reader you plug in (`LlamaParse` sold separately). Not part of the index. | `SentenceSplitter`, **`DEFAULT_CHUNK_SIZE=1024`, `DEFAULT_CHUNK_OVERLAP=20`**. | **None** in the index path. | `SchemaLLMPathExtractor`: builds a Pydantic model whose fields are `Literal[...]` unions of the allowed entity and relation types and calls `llm.astructured_predict` — **schema enforced at decode time** where the provider supports it, `strict=True` by default. Then `_prune_invalid_triplets` validates each `(subject_type, relation, object_type)` against `kg_validation_schema` **after** decoding. `max_triplets_per_chunk=10`, `num_workers=4`. On `ValueError/TypeError/AttributeError` it logs and yields `triplets = []` unless `raise_on_error`. | **Nothing.** Nodes are upserted by id/name; there is no dedupe, no similarity pass, no merge record. | Any of ~20 graph stores; Neo4j/Memgraph/Nebula/`SimplePropertyGraphStore`. No tenancy primitive. | Retriever composition: `VectorContextRetriever`, `LLMSynonymRetriever`, `CypherTemplateRetriever`, `TextToCypherRetriever`. No community layer. |
| **RAGFlow** ([repo](https://github.com/infiniflow/ragflow)) | **The strongest parse tier in the set.** `deepdoc/` ships its own layout + OCR + TSR stack, plus adapters for Docling, MinerU, PaddleOCR, Mistral OCR, MonkeyOCR, OpenDataLoader, TCADP. Figures go through a vision model (`figure_parser`, `vision_figure_parser_pdf_wrapper`); tables are tokenised separately (`tokenize_table`), Excel merged by `chunk_token_num`. Per-corpus templates (`rag/app/{laws,manual,paper,book,resume,presentation}.py`). | Template-driven and structure-aware; `chunk_token_num` per knowledge base, delimiters configurable. | **Yes, LLM-based and optional**: `auto_keywords` and `auto_questions` per chunk (`rag/svr/task_executor.py`), plus corpus tagging (`tag_kb_ids`) and RAPTOR hierarchical summaries. Closest thing in the set to Anthropic-style contextual retrieval. | Three extractors: `general/` (GraphRAG-style delimited tuples), `light/` (LightRAG-style), and **`ner/` — a spaCy pipeline (tokenize → POS → dep-parse → NER → typed relations) across 7 languages, one forward pass, no LLM**. Confidence tiers by spaCy label. Checkpoints (`checkpoints.py`) make extraction resumable. | **Explicit ER step** (`entity_resolution.py`): within-type pairwise `itertools.combinations` filtered by `is_similarity` — a digit-2gram guard, then `Levenshtein.distance(a,b) <= min(len(a),len(b))//2` for English, or ≥0.8 character-set overlap otherwise — then **batched LLM adjudication** (`resolution_batch_size=100`, with timeouts that silently skip a batch), then `graph_merge`. Destructive; no decision log. | Elasticsearch/Infinity + MySQL + MinIO. `tenant_id` threaded through the application. Incremental via doc-scoped tasks and checkpoints. | Fused keyword + vector + graph, with Leiden communities and reports, a query-analysis prompt, and rerankers. |

## 1.2 What that table actually says

Three patterns, and they matter more than any individual cell.

**Nobody stores character spans.** Every system in the set records provenance at *chunk
granularity* at best: GraphRAG's `text_unit_ids`, LightRAG's capped `source_ids`, Graphiti's
`episodes: list[str]`, Cognee's `source_task` stamps, RAGFlow's `source_id`. Not one records
where inside the chunk the fact came from. LightRAG goes further in the wrong direction and
**drops source ids past 200 per entity**.

**Resolution is a `groupby` in four of six.** GraphRAG, LightRAG and Cognee all key entities on
the normalised surface name. Graphiti and RAGFlow do real candidate generation and LLM
adjudication — and both are destructive. No system in the set keeps a retractable decision log,
and none gives a human decision permanent precedence over a later model run.

**The category is converging on "spend less on the graph".** GraphRAG is in maintenance mode by
its own README ("*largely in maintenance mode, and won't be accepting new PRs or implementing new
features*", read 2026-09-20). Microsoft's own LazyGraphRAG defers all summarisation to query time
at **0.1% of GraphRAG's indexing cost and >700× lower global-query cost**
[[MSR](https://www.microsoft.com/en-us/research/blog/lazygraphrag-setting-a-new-standard-for-quality-and-cost/)].
RAGFlow shipped a spaCy-only extractor. [arXiv 2603.29875](https://arxiv.org/abs/2603.29875)
(2026-02-06) concludes that "*VectorRAG performs better than standard GraphRAG and almost as good
as current SOTA graph-based solutions, for a fraction of the cost*."

Supporting numbers, from [arXiv 2502.11371](https://arxiv.org/html/2502.11371v3) (HotpotQA,
Llama-3.1-8B): vector RAG 60.04 F1; community-GraphRAG local 61.66; HippoRAG2 63.01;
community-GraphRAG **global 45.16 — worse than plain vector RAG**. Indexing on MultiHop-RAG:
135 s for RAG vs 5,560 s (41×) and 7,702 s (57×). Retrieval: 1,724 s vs 14,434 s (8.4×) for
KG-GraphRAG. 13.6% of queries were GraphRAG-only wins; **11.6% were RAG-only wins**.
[arXiv 2503.04338](https://arxiv.org/html/2503.04338v2) adds per-query costs: RAPTOR 3.18 s /
3,210 tokens, LGraphRAG 2.98 s / 6,154 tokens, ToG 69.74 s / 16,859 tokens, KGP 105.09 s /
9,326 tokens; rich KGs cost "*up to 40× more tokens than trees*" to build; and — the line worth
pinning to a wall — **human-expert chunking consistently beat token-length chunking across
datasets**.

## 1.3 Verdict on each claimed differentiator

### (a) Mandatory provenance spans on every fact — **REAL. The strongest one.**

No competitor does it. Not one of the six records a character offset; all six record a chunk
reference and stop. The plan's four consequences (Part 2.1) all follow from spans and none of
them follow from chunk ids: a chunk-level citation cannot be verified programmatically, cannot
highlight, and cannot support the "does this claimed span literally exist in the chunk text"
hallucination check that costs nothing to run.

Caveats to be honest about:

- The *span* is differentiating; the *word "provenance"* is not. Every competitor will say they
  have provenance and will be telling the truth at chunk granularity. The demo has to show the
  span highlighted in the source PDF, or the claim reads as marketing.
- Making the span non-nullable **in the extraction schema** is where this gets hard, not in the
  DDL. Models are demonstrably worse at emitting exact offsets than at emitting text. The
  defensible implementation is: ask for the verbatim quote, then locate it in the chunk
  deterministically, and fail the fact when the quote is not found. That is also the free
  hallucination detector.
- Budget for the recall cost. Facts synthesised across two sentences have no single span. Decide
  now whether those are rejected or carry a multi-span list; retrofitting a multi-span
  representation is a schema change on the one table the plan says has no backfill path.

### (b) Resolution grounded in an external controlled vocabulary (LEI/CIK) — **REAL, but narrower than the plan implies.**

Nobody in the set does it. Cognee is the only one that even ships an "ontology resolver", and it
is `difflib.get_close_matches(name, candidates, cutoff=0.8)` against the labels in an RDF file —
string similarity with a different import. Graphiti and RAGFlow do LLM fuzzy-dedup, well. Nobody
resolves to an authoritative registry.

But grounding is not the lookup that "converts the hardest problem in the category into a lookup":

- **Coverage is the binding constraint.** GLEIF covers ~2.5 M legal entities
  [[GLEIF](https://www.gleif.org/en/lei-data/access-and-use-lei-data)]. Most counterparties in a
  mid-market contracts corpus — LLCs, subsidiaries, trading names, a landlord — have no LEI. The
  honest framing is *a high-precision anchor for the entities that have one*, not universal
  resolution. Design for the miss: "unresolved, cluster-local id" must be a first-class state,
  not an error.
- **The registry does not remove the matching problem.** GLEIF's own search is a full-text match
  on the registered legal name; broad names return many candidates. You still need blocking +
  scoring + adjudication to pick among them. You have moved the problem from "are these two
  strings the same company" to "which of these 40 registry rows is this string", which is
  genuinely easier and genuinely still hard.
- **LEIs outlive the entity.** A dissolved or merged entity keeps its code, so registry state is
  itself temporal and interacts with (c).

Verdict: real, defensible, and the right bet — provided it is sold as *precision and
auditability on the entities that matter*, with a measured coverage number, and never as a
solved-problem claim. Splink + clustering remains load-bearing for everything without a code.

### (c) Bi-temporal facts with validity-window invalidation — **HALF REAL.**

Graphiti has it and ships it: `valid_at` / `invalid_at` (valid time) plus `created_at` /
`expired_at` (transaction time), with `resolve_edge_contradictions` expiring edges whose windows
conflict. That is a genuine bi-temporal implementation in a competitor, and the plan's Part 0.1
already concedes it. Cognee's contradiction detection is off by default, additive-only, and has
no validity windows. GraphRAG, LightRAG and LlamaIndex have no temporal model whatsoever.

What is genuinely ours is narrower and still worth having: **bi-temporality over document
corpora rather than chat episodes**, where validity dates come from contract effective/termination
clauses and amendments rather than from "when the user said it". That is a different extraction
problem (dates in legal prose, relative references, conditional effectiveness) and a different
invalidation trigger (an amendment document supersedes a clause) than Graphiti's episode stream.

Do not claim bi-temporality as a category-first. Claim the contracts semantics on top of it, and
expect a technical buyer who has read the Zep paper to test exactly that.

### (d) GLiNER prefilter before the LLM extraction call — **NOT A DIFFERENTIATOR. It is a cost lever with a measurable recall risk.**

RAGFlow already ships a non-LLM NER extractor (`rag/graphrag/ner/`, spaCy, 7 languages,
dependency-parsed typed relations). GraphRAG ships `build_noun_graph/` with regex, CFG and
syntactic-parsing noun-phrase extractors and an `extract_graph_nlp` config. The idea that cheap
NER should gate or replace expensive LLM extraction is, in 2026, the mainstream position.

And the recall arithmetic deserves stating plainly. GLiNER-L reports **average zero-shot F1 47.8
across 20 NER datasets** [[NAACL 2024](https://aclanthology.org/2024.naacl-long.300.pdf)];
GLiNER2 reports 0.590 on CrossNER against GPT-4o's 0.599
[[arXiv 2507.18546](https://arxiv.org/html/2507.18546v1)]. Used as a *gate* — "skip the LLM on
chunks where GLiNER finds nothing" — every miss is a chunk that silently contributes no facts,
which is exactly the failure mode that is invisible until a buyer's gold set finds it.

Keep it, for the ~50–70% call reduction the plan claims in Part 5. But:
- Tune it for **recall, not F1**; a low threshold and a generous label set.
- Gate on *presence of any candidate*, never on the candidate types.
- Make skip rate a first-class metric with an alarm, and run a periodic sampled shadow where
  skipped chunks go to the LLM anyway to measure what the gate is losing.
- Never describe it externally as a quality feature. It is a cost feature.

### (e) Lazy community summarisation instead of eager — **NOT OURS. It is Microsoft's published result, and it is table stakes.**

LazyGraphRAG is the named prior art, with the 0.1%-indexing-cost and >700×-query-cost numbers
above. GraphRAG itself added dynamic community selection. Graphiti builds communities on demand.
For a multi-tenant deployment it is simply the correct engineering choice — Part 5 already prices
it at ~$0.002/doc amortised vs $0.026 eager — but a buyer who knows the space will not credit it
as innovation. Ship it, do not pitch it.

### Summary

| Claim | Table stakes | Genuinely ours | Notes |
|---|---|---|---|
| Mandatory character spans on every fact | — | **Yes** | The one nobody else has. Must be demoed visually. |
| Controlled-vocabulary resolution (LEI/CIK) | — | **Yes, with caveats** | Coverage is the constraint; "unresolved" must be a supported state. |
| Bi-temporal with validity windows | Partly (Graphiti) | Contract semantics only | Do not claim category-first. |
| Non-destructive, retractable decision log | — | **Yes** (untested claim in the ticket, but true of the set) | No competitor keeps a retractable merge decision or human-over-model precedence. |
| Engine-enforced tenant isolation (FORCE RLS) | — | **Yes** | Every competitor's tenancy is an app-level predicate; Graphiti #1676 is the proof of what that costs. |
| Assertion-counted deletion | — | **Yes** | No competitor implements per-document contribution removal. Related: GraphRAG #2540 leaves dangling ids on update. |
| GLiNER / NER prefilter | **Yes** | — | RAGFlow and GraphRAG already ship non-LLM extractors. |
| Lazy community summaries | **Yes** | — | Microsoft's published result. |
| Structure-aware ~600-token chunking | **Yes** | — | RAGFlow does this better today. Note MS's own default is 1200/100. |
| Contextual blurbs before embedding | **Yes** | — | RAGFlow (`auto_keywords`/`auto_questions`/RAPTOR), LightRAG (heading breadcrumbs). |
| Post-decode ontology legality validation | **Yes** | — | LlamaIndex's `_prune_invalid_triplets` is exactly this. |
| Ontology-constrained decoding | **Yes** | — | LlamaIndex `SchemaLLMPathExtractor` with `Literal` unions and `strict=True`. |
| Immutable versioned ontologies | — | **Yes** | Nobody versions the ontology an extraction ran under. |

**The honest one-line read:** the *pipeline* is table stakes and in two places (parse, contextualize)
RAGFlow is ahead of where Stage 3 plans to be. What is ours is the **record** the pipeline
produces — spans, retractable decisions, registry anchors, versioned ontologies, engine-enforced
isolation, and a deletion path that actually removes one document's contribution. Sell the record,
not the pipeline. That is consistent with Part 0.3's "GraphRAG is an implementation detail, never
the pitch" and should be reflected in how the acceptance test below is framed to a partner.

---

# Part 2 — The design-partner acceptance test

## 2.1 What the evidence says about pilots

The base rate is bad and the reasons are not technical. MIT NANDA's *The GenAI Divide: State of
AI in Business 2025* found **~95% of enterprise GenAI pilots produced no measurable P&L impact**,
from a review of 300+ disclosed initiatives, 52 structured interviews and 153 survey responses,
and attributed the gap to learning and workflow integration rather than model quality
[[report PDF](https://mlq.ai/media/quarterly_decks/v0.1_State_of_AI_in_Business_2025_Report.pdf)].
WalkMe's 2025 figure is the same shape: 78% of enterprises running agent pilots, **fewer than 15%
reaching production at meaningful scale**, with the handoff failing on operational infrastructure,
not performance [UNVERIFIED — reported secondhand, I did not find the primary WalkMe report].

a16z's design-partner framework ([2022-09-14](https://a16z.com/a-framework-for-finding-a-design-partner/))
gives the selection criteria — **representativeness, urgency, capacity** (specifically: "do they
have an employee who can be the internal champion of this project?") — recommends a **written
engagement of one, three or six months with biweekly check-ins**, and **5–10 partners** at a time.
Its named anti-patterns are founder-centric capture (the partner values your engineering time more
than the product, which hides every missing feature) and taking feedback only from the executive
buyer rather than the actual user.

Practitioner guidance converges on **fixed scope and fixed price** — an open-budget pilot is a
science project procurement cannot approve — and on the distinction between a PoC (does the
technology work, offline) and a pilot (does it change the numbers, on real data). "Sample data
proves nothing about your environment."

Two things follow for us specifically.

1. **The corpus must be theirs and must be messy.** A pilot on a clean sample set tests nothing
   this product is differentiated on.
2. **Day one is a data-readiness gate, not a demo.** The pre-flight checklist in §2.7 exists
   because the failures below are all discoverable in hours and all fatal in week six.

## 2.2 Golden corpus construction

**Size.** Practitioner consensus starts at **30–50 real queries** for a first golden set
[[Statsig](https://www.statsig.com/perspectives/golden-datasets-evaluation-standards)], and
research practice treats **~200 per slice** as the floor where confidence intervals stop being
embarrassing. ENTERPRISE_PLAN Stage 4 already specifies 100–300 gold cases, which sits correctly
between those. For a design partner:

- **Documents: 200–500**, drawn by stratified sample from the partner's real corpus, not curated.
  Strata: document type, era (at least one pre-2015 scan), language, size (include the largest
  document they have), and known-duplicate families. 200 is enough to hit every parse pathology;
  500 is enough that per-document cost is measured rather than extrapolated.
- **Questions: 150**, split **60 single-hop factual / 45 multi-hop relational / 25 temporal
  ("what was true as of…") / 20 unanswerable**. The unanswerable slice is not optional — it is
  the only way to measure whether the system fabricates, and buyers reliably include it.
- **Ground truth is written by the partner's domain expert, not by us, and not by an LLM.** Two
  experts on a 30-question overlap, with inter-annotator agreement reported; if agreement is below
  ~0.7, the questions are ambiguous and get rewritten. This is the single most common way a
  pilot's numbers become unfalsifiable.
- **Every gold answer carries its source document + page + quote.** Without that the
  citation-accuracy metric cannot be computed at all, and citation accuracy is our differentiator.

**Avoiding overfit.**

- **Split 60/40 into a visible dev set and a sealed holdout the partner keeps.** We never see the
  holdout until the final run. This is the term that makes the result credible to their procurement.
- **Freeze the corpus.** Any document added after the gold set is written goes into a separate
  "drift" run.
- **Rotate 20% of questions at the midpoint**, authored by the partner, so late gains have to
  generalise.
- **Tag every gold case with tenant and document id** (Stage 4 already requires this) — erasure
  covers fixtures, and a partner exercising deletion should not break the eval.

## 2.3 Metrics and thresholds

Ragas/DeepEval defaults measure the answer. A knowledge-graph buyer will measure the graph. Stage
4 already says to hand-roll these; here are the numbers to put next to them.

**Graph construction**

| Metric | Threshold | Basis |
|---|---|---|
| Entity extraction F1 vs gold, per ontology type | **≥ 0.75 micro-F1**, no single type < 0.60 | LLM KG-construction work reports ~63% F1 for a strong model on general extraction and 65.8% macro-F1 on REBEL / 75.7% micro-F1 on WebNLG2 for a tuned pipeline [[arXiv 2509.17289](https://arxiv.org/html/2509.17289v1)]. A constrained, ontology-specific extractor on contracts should clear that; promising 0.90 is how you lose. |
| Relation/triple F1 vs gold | **≥ 0.60** | Relation extraction sits 10–20 points below entity extraction everywhere. |
| Ontology conformance rate | **≥ 99.5%** | Should be near-100% under constrained decoding + post-decode legality validation; any drift is a regression signal, per Stage 4. |
| **Span-grounding rate** (claimed span exists verbatim in its chunk) | **100%, enforced, not measured** | A fact that fails this is rejected at write time. Reporting it as a percentage means it is not enforced. |
| **Provenance completeness** (facts with ≥1 live assertion) | **100%** | Anything else is a deletion-correctness bug (Part 2.1). |
| Extraction-failure / silent-drop rate | **< 1% of chunks**, alarmed | GraphRAG returns empty dataframes on exception; LightRAG had [#3352](https://github.com/HKUDS/LightRAG/issues/3352), where extraction ran, cost money, and was never merged into the graph. Measure it or inherit it. |
| GLiNER prefilter skip rate + shadow-sampled recall loss | skip ≤ 60%, measured recall loss **< 2%** | See §1.3(d). |

**Resolution** — report precision and recall separately, and **over-merge separately from
under-merge**, because the product consequences differ completely.

| Metric | Threshold | Basis |
|---|---|---|
| Pairwise resolution precision | **≥ 0.95** | Over-merging two counterparties is the trust-destroying error. |
| Pairwise resolution recall | **≥ 0.80** | ENTERPRISE_PLAN 2.2 already sets 80–90 F1 as the realistic ceiling (WDC Products hard variants: 72.18–79.99 F1 for top fine-tuned systems). Do not promise more. |
| **Over-merge rate** (clusters containing ≥2 true entities) | **< 2%**, reported as a raw count too | RAGFlow's `is_similarity` admits pairs within `min(len)/2` edit distance; GraphRAG collapses same-title-different-type ([#1718](https://github.com/microsoft/graphrag/issues/1718)). A count the partner can eyeball beats a rate they cannot. |
| LEI/CIK coverage on the partner's corpus | **measured and reported, no threshold** | Report it honestly in week one; it is the number that tells them whether the differentiator applies to their data. |
| Human-decision durability | **100% across a forced model upgrade** | Re-run extraction with a different model; every human "these are different" must survive. This is the test no competitor can pass. |

**Retrieval and answer**

| Metric | Threshold | Basis |
|---|---|---|
| Multi-hop recall@10 (gold supporting docs retrieved) | **≥ 0.80** | The class we sell. |
| **Citation precision / recall** (ALCE-style: each statement supported by its cited span; the answer fully supported by cited spans) | **precision ≥ 0.90, recall ≥ 0.85** | [ALCE](https://arxiv.org/abs/2305.14627) is the standard formulation; human/automatic agreement is κ=0.698 recall, κ=0.525 precision, so the precision judgement needs human spot-checks. Our spans should beat published chunk-level systems, and this is the metric to stake the pilot on. |
| Answer faithfulness (Ragas/DeepEval) | **≥ 0.90** | Standard buyer default; we should not be the bottleneck here. |
| Abstention on the unanswerable slice | **≥ 0.90 correctly abstains** | The fabrication test. |
| Answer correctness vs a vector-RAG baseline on the same corpus | **≥ baseline on single-hop; ≥ +10 points on the multi-hop and temporal slices** | Per arXiv 2502.11371, generic multi-hop gains are ~3 F1 points; +10 is only achievable because the slices are chosen to be relational/temporal. **Run the vector-RAG baseline ourselves and show it** — the buyer will otherwise run it, and 13.6% vs 11.6% (§1.2) is a losing surprise. |

## 2.4 Cost and latency budgets

| Budget | Target | Hard fail | Basis |
|---|---|---|---|
| Ingest cost per 10-page document | **≤ $0.09** | > $0.15 | Part 5's engineered $0.073 + 20%, matching Part 6's verification clause. |
| Ingest cost, 500-document pilot corpus | **≤ $45** | > $75 | Same. State it as an absolute number in the pilot agreement; fixed price is what makes it approvable. |
| `usage.cache_read_input_tokens > 0` on every extraction call | **100%** | any zero | Part 5. A silent cache miss is a ~10× cost event with no error. |
| Ingest throughput | **≥ 500 docs/hour** sustained per tenant | < 100/hr | Enough that 500 docs land inside an hour and a partner's 50k-doc corpus is a 4-day story, not a quarter. |
| First-corpus turnaround | **500 documents queryable within 4 hours of upload** | > 24h | Batch API is ≤24h, so the ingest path must either not use it for the onboarding run or be honest that onboarding is overnight. **Decide this before the pilot**; it is the most likely schedule surprise. |
| Retrieval P95 (seeds → expansion → rerank → assembly) | **≤ 350 ms** | > 1 s | Stage 3's budget. For context: Zep publishes P95 300 ms (paper) / 150 ms (blog); arXiv 2503.04338 measures 1.5–3.5 s per query end-to-end for RAPTOR/HippoRAG/LGraphRAG, and 70–105 s for ToG/KGP. |
| End-to-end answer P95 (to last token) | **≤ 4 s** | > 10 s | Retrieval + 600–1200 ms to first token + generation. |
| Cost per query | **≤ $0.01** | > $0.05 | LGraphRAG ~6,154 tokens/query at 2503.04338; ours should be smaller because global search is lazy. |

For the buyer's own frame of reference, the numbers to quote for what they are avoiding:
GraphRAG indexing measured at **$51.37–$389.12 per benchmark corpus** on GPT-4o
[[arXiv 2503.02922](https://arxiv.org/pdf/2503.02922)], and practitioner reports of **$200
estimated / $800 actual** first indexing runs because of retry loops and per-level summarisation
[UNVERIFIED — secondary practitioner accounts, not a primary measurement].

## 2.5 The protocol

**Week 0 — agreement (before any data moves)**

1. **Fixed scope, fixed price, written.** One named business question the pilot answers
   ("portfolio-level obligation questions with a defensible audit trail"), 6 weeks, a named
   internal champion with allocated time, biweekly check-ins. Per a16z: no champion, no pilot.
2. **DPA, subprocessor list (naming the model providers), and the acceptable-use clause on
   high-risk deployment** signed before the corpus arrives — Stage 7 makes these cheap to produce
   and they are otherwise a two-week stall at the worst moment.
3. **Write the go/no-go table into the agreement**: the metrics in §2.3–2.4, with thresholds, and
   an explicit statement that the sealed holdout decides. Agree what a *fail* obliges us to do.

**Week 1 — pre-flight and corpus intake**

4. Partner delivers **200–500 stratified documents** plus **the single largest document they have**
   and **one known-duplicate family**.
5. Run the **§2.7 pre-flight checklist**. Produce a one-page data-readiness report within 48 hours:
   what parsed, what did not, what will cost more than budget, what we cannot support. **This
   report is the most valuable artefact of week one** and it is the thing that stops a six-week
   failure.
6. Report **LEI/CIK coverage** on their actual counterparty names. If coverage is under ~40%,
   say so immediately and reframe what the resolution claim means for them.

**Week 2 — gold set**

7. Partner's domain expert authors **150 questions** to the §2.2 mix, each with document + page +
   quote. We supply the template and the multi-hop/temporal question patterns; we do not author
   the answers.
8. **Second annotator on a 30-question overlap**; report agreement. Below ~0.7, rewrite.
9. **Split 60/40. The partner seals the 40% holdout.**
10. Build the ontology mapping: their contract types onto the contracts pack, published as an
    immutable ontology version. Any gap is a new version, never an edit.

**Weeks 3–4 — ingest and iterate on the dev set only**

11. Full ingest with per-document cost, token counts and cache-hit rate recorded from the provider
    responses. Report the running spend against the §2.4 budget **weekly**, not at the end.
12. Score the dev set on every metric in §2.3. Fix, re-run, iterate.
13. **Run the vector-RAG baseline on the same corpus and the same questions.** Show it to the
    partner before they ask.
14. Run the **resolution review queue** with their expert, for at least 50 adjudications. This is
    a product surface, not an admin page (Part 2.2), and a design partner using it is the strongest
    signal a16z's framework lists — a technical integration painful to unwind.
15. Midpoint: partner rotates 20% of the dev questions.

**Week 5 — the adversarial week**

16. **Deletion.** Partner picks 10 documents; delete them. Assert with SQL: assertions gone, facts
    with other support alive, facts without support gone, embeddings and community summaries
    invalidated, all in one transaction. Then re-run the gold set and show which answers changed
    and why.
17. **Human-decision durability.** Force a model change and re-run extraction and resolution.
    Every human decision must survive. Show the decision log.
18. **Isolation.** In front of them: a second tenant, the same corpus, a query with no tenant
    context returning zero rows, and tenant A's token 404ing on tenant B's document.
19. **Temporal.** Ingest an amendment that supersedes a clause. Query "what was true as of
    <date>". Show the validity window and the invalidated edge.
20. **Injection.** A document in their corpus with an embedded instruction. Show it does not cross
    the tenant boundary (Stage 7: the model never holds a boundary-crossing tool).

**Week 6 — the holdout run and the decision**

21. **One run** against the sealed holdout, no tuning between the unsealing and the run, scored by
    the partner where they are willing.
22. Report every metric against its threshold, plus total spend against budget and P95 latency
    against budget, plus the vector-RAG baseline side by side.
23. Go/no-go against the week-0 table. A metric that fails gets a named cause and a date, or an
    admission that it is out of scope.

## 2.6 What we watch on their side, not ours

a16z's real signal is behavioural, and it is cheaper to instrument than to ask about:
documents uploaded *outside* the agreed corpus; queries issued by people who are not the champion;
review-queue adjudications per week; whether they build against the API. A partner who ingests
their own corpus unprompted in week 3 has told you more than the holdout will.

## 2.7 Pre-flight checklist — the failure modes to probe on day one

Every one of these is discoverable in an afternoon and fatal at week six. Run them as a script
against the intake corpus and put the output in the readiness report.

| # | Probe | What it catches | Why it matters here |
|---|---|---|---|
| 1 | **Text-layer detection per PDF.** Count pages with an embedded text layer vs image-only. | Scanned documents, and the opposite mistake — OCR'ing a PDF that already has text, which injects recognition errors and burns time. | [OHRBench](https://arxiv.org/abs/2412.02592) (8,561 document images, 8,498 Q&A pairs) finds "*none*" of the current OCR solutions "*is competent for constructing high-quality knowledge bases for RAG*", and that OCR noise (semantic and formatting) propagates through the whole pipeline. OCR errors corrupt the *span offsets* our whole differentiator rests on. Decide per document: premium parse tier, or reject. |
| 2 | **Encoding and control characters.** Detect non-UTF-8, mojibake, embedded control chars, mixed line endings, PDF ligatures (`ﬁ`, `ﬂ`) and soft hyphens. | Silent corruption that makes span offsets meaningless and exact-quote verification fail. | Ligature and soft-hyphen normalisation **changes character offsets**. Normalise once, before spans are computed, and store the normalised text as the chunk of record. Getting this wrong after ingest means re-extraction. |
| 3 | **Table census.** Count tables, max columns, multi-row headers, tables spanning pages. | The parse-tier decision, and the chunker's "never split a table" rule. | Multi-row headers hide meaning across rows; an 800-row table embedded as text floods the index with near-duplicates. A table-heavy corpus is the case for the Reducto/Azure DI premium tier (Stage 3). |
| 4 | **Document size distribution.** Largest document in pages and tokens; count over 200 pages. | Unbounded extraction time, per-document cost blowouts, activity timeouts. | ADR-0003's whole argument. A 500-page document with gleaning is the unbounded task. Confirm the Temporal activity heartbeat and the per-document spend cap fire before the partner's biggest document does. |
| 5 | **Near-duplicate families.** Content-hash and shingle the corpus; report exact duplicates and near-duplicates. | "Seven versions of the same product manual" — the reported norm in enterprise corpora. | Drives three things: chunk content-hash dedupe (a named cost lever in Part 5), whether assertion-counted deletion behaves sanely across versions, and whether resolution over-merges across versions of the same contract. Cognee's content-hash chunk ids are the pattern to copy. |
| 6 | **Acronym and identifier inventory.** Extract high-frequency capitalised tokens, internal codes, contract numbers, party short-forms. | Vector search blurs exact identifiers; the ontology may have no type for them. | Buyers search for invoice numbers, SKU codes, policy IDs and internal acronyms. Needs a lexical path (`pg_trgm` / BM25), not just pgvector. Also: an acronym and its expansion are a resolution test case — put 10 of them in the gold set. |
| 7 | **Language detection per document and per chunk.** | Mixed-language corpora, and mid-document language switches. | The contracts pack ontology and every prompt are English-first. GLiNER and spaCy models are per-language. Report the non-English share in week one; if it is over ~10%, it is a scope decision, not a bug to fix in week five. |
| 8 | **Entity-density dry run.** Extract on a 20-document sample; project entities/document, facts/document and cost/document onto the full corpus. | Entity explosion and cost overrun, before they happen at scale. | A dense corpus multiplies extraction cost, resolution candidate pairs (RAGFlow's ER is `itertools.combinations` within type — quadratic) and community count. GraphRAG's HotpotQA index needed reports for **>57,000 communities** ([arXiv 2503.04338](https://arxiv.org/html/2503.04338v2)). Project it, then check it against the §2.4 budget, then tell the partner the number. |
| 9 | **Cache-prefix integrity check.** Two identical extraction calls; assert `cache_read_input_tokens > 0` on the second. | A timestamp, UUID or unsorted `json.dumps()` in the cached prefix. | Part 5: silent, no error, ~10× on the largest cost line. Check on the partner's actual ontology, since their ontology is the prefix. |
| 10 | **Span round-trip on 100 sampled facts.** Take the stored span, slice the stored chunk, compare to the stored quote. | The differentiator not actually working. | If this is below 100% the pilot has no citation story. Run it on day one of ingest, not week five. |
| 11 | **PII and erasure rehearsal.** Find the personal data; run the delete cascade on one document containing it; confirm embeddings, caches, summaries and eval fixtures are gone. | The GDPR conversation arriving in week six. | Part 2.3, and the EDPB's 2025 coordinated action on erasure. "We deleted the text but kept the vectors" is not defensible (Hamburg DPA position on embedding re-identifiability). |
| 12 | **Injection sweep.** Grep the corpus for imperative-to-model patterns. | OWASP LLM01, on a corpus that is by definition untrusted third-party text. | Containment is architectural (Stage 7). Finding one in their corpus in week one and showing it bounded is a selling moment. |

---

# What would make a buyer say no

Ordered by how likely each is to be the actual reason, not by how uncomfortable it is.

1. **"Your resolution merged two of our counterparties."** One visible over-merge in a demo costs
   more than ten points of F1. It is the error their lawyers will find first and the one they
   cannot unsee. Mitigation: precision-biased thresholds, over-merge reported as a raw count, and
   the unmerge demonstrated live — unmerge is the answer no competitor in §1.1 can give.
2. **"We ran vector RAG on the same corpus and it was close."** They will run it. Published
   evidence says the generic gap is ~3 F1 points, that community-global search can be *worse* than
   vector RAG (45.16 vs 60.04 on HotpotQA), and that 11.6% of queries are vector-RAG-only wins.
   Mitigation: run the baseline first, show it, and confine the comparison to the relational,
   temporal, aggregate and auditable query classes Part 0.3 already says are the only ones to
   fight on. Losing a generic benchmark we chose to enter is a self-inflicted no.
3. **"The parse was wrong, so everything downstream was wrong."** Scanned pages, multi-row tables,
   two-column layouts. This is where week one actually goes, and RAGFlow's parse tier is better
   than Stage 3's default. Mitigation: probe 1 and 3, an explicit premium parse tier, and a
   documented reject path instead of silently producing garbage facts.
4. **"It cost more than you said."** Practitioner reports of 1.5–2× overruns on first indexing runs
   are common; a fixed-price pilot with a silent cache miss is a margin event and a credibility
   event. Mitigation: probe 9, per-tenant spend cap (Stage 2), weekly spend reporting, and the
   500-document number stated as an absolute in the agreement.
5. **"Nobody used it."** The MIT result: the failure is workflow integration, not accuracy. A
   pilot where only the champion ever queried is a no regardless of the metrics. Mitigation: §2.6,
   and the review queue as a real weekly surface.
6. **"Onboarding took longer than the pilot."** If the Batch API's ≤24h latency is in the
   first-corpus path, "500 documents in 4 hours" is not true. Decide before the pilot, not during.
7. **"You had no answer on security review."** Not SOC 2 — a design partner will usually accept a
   roadmap — but a missing DPA, an undisclosed subprocessor list, or no answer on erasure stalls
   weeks. Stage 7 makes all three cheap; produce them in week 0.
8. **"Your ontology didn't fit our contracts."** The contracts pack is the proof we are software
   and not consulting (Part 0.2). Every gap closed by us writing custom extraction logic during
   the pilot is a data point *against* the business model, even when it makes the partner happy.
   Track the number of partner-specific code changes; it should be zero, and if it is not, that is
   the finding.

---

## Open items

- **[UNVERIFIED]** The WalkMe 2025 "<15% reach production" figure is secondhand; find the primary
  report before it appears in anything customer-facing.
- **[UNVERIFIED]** GraphRAG "$200 estimated / $800 actual" indexing overruns are practitioner blog
  claims, not measurements. Our own 100-document cost run (Part 6) replaces them.
- The Batch API vs. first-corpus-turnaround tension (§2.4) is a real product decision that this
  research surfaced and did not resolve. It belongs in Stage 3.
- LEI/CIK coverage on a real contracts corpus is unmeasured. It is the single number that decides
  how strongly differentiator (b) can be claimed, and it can be measured cheaply against the GLEIF
  golden-copy file before any partner signs. Worth doing before Stage 3 starts.
