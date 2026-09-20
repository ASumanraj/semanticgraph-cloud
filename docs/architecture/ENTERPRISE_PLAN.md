# SemanticGraph Cloud — Enterprise Architecture & Execution Plan

> **Status:** Approved 2026-09-20. This is the authoritative architecture document.
> It supersedes `ARCHITECTURE.md`, which describes the pre-research design (Neo4j, Celery)
> and is retained only until the migration in Part 3 is complete.
>
> **Progress is tracked here.** Each stage in Part 3 has a checklist; tick items as they land
> so the remaining work is always visible in git history.
> Decisions are recorded individually in [`docs/adr/`](../adr/README.md).

---

## Context

`S:\semanticgraph-cloud` has a clean hexagonal core (~1,400 LOC in `src/semanticgraph/`) buried
under five dead scaffolds, two frontends, 661 MB of stray `node_modules` inside `src/`, four nested
git repos, and no repo at the root. The documented architecture (`ARCHITECTURE.md`) describes a
system that mostly does not exist: no auth, no RLS, no migrations, and the Neo4j and LLM adapters
are 0-byte files.

Three parallel research passes (market/competitive, enterprise-SaaS requirements, technical
architecture) changed the target materially. This plan reflects what the evidence says, not what
the original design assumed. **Three of the original premises did not survive research** and are
corrected in Part 0.

The goal: a base strong enough that features can be added one at a time without rework — which
means getting the handful of genuinely irreversible decisions (Part 2) right before writing more code.

---

# Progress tracker

Tick as each item lands. Detail for every item is in Part 3.

### Stage 0 — Repository foundation
- [x] Approved plan committed to `docs/architecture/ENTERPRISE_PLAN.md`
- [x] Root `.gitignore` (+ `.gitattributes`, `.dockerignore`)
- [x] `git init` at root + first commit
- [x] Root `pyproject.toml` (replaces unpinned `requirements.txt`) — `uv.lock` still to generate
- [x] Nested git histories resolved — scaffold `.git` dirs removed; `ECC/` pinned as a submodule at `dd6ee53`
- [x] Legacy scaffolds deleted (Part 1.4); frontend consolidated on the Next.js app at `frontend/`
- [x] `AGENTS.md` rewritten against this plan
- [x] CI repointed at the root project (`ci.yml`: ruff + pytest on 3.12, frontend lint + build)
- [x] Remote configured and pushed — github.com/ASumanraj/semanticgraph-cloud

**Stage 0 complete.**

### Stage 1 — Correctness of existing code
- [x] Package collapsed onto one structure (`models/`, `services/` and the loose root modules removed; upload and search moved into use cases)
- [x] Production→test import removed — fakes promoted to `adapters/outbound/inmemory/`
- [x] Global-variable composition root replaced with a config-built `Container` (no setters)
- [ ] Async/sync boundary fixed (`AsyncSession` throughout)
- [x] `docker-compose.yml` runs the real API and worker
- [ ] End-to-end proof on real infrastructure (AGENTS.md "Proving it works"):
  - [ ] Postgres-backed integration test — upload via HTTP, worker processes, assert rows with SQL
  - [ ] Playwright in `frontend/` — drive the real upload control against a running API
- [x] Architecture-fitness tests (no framework imports in `domain/`/`application/`; no `tests` import in `src/`)

### Stage 2 — The irreversible schema ← the foundation
- [ ] Alembic baseline
- [ ] `tenant_id` everywhere, leading every composite index
- [ ] FORCE RLS + non-owner app role + fail-closed tests
- [ ] Provenance chain with mandatory spans
- [ ] Bi-temporal facts with edge invalidation
- [ ] Versioned resolution decision log
- [ ] Immutable versioned ontologies
- [ ] Assertion-counted delete cascade
- [ ] Usage event ledger
- [ ] Append-only audit log
- [ ] OpenTelemetry with `tenant_id` attribution
- [ ] Per-tenant spend cap

### Stage 3 — Pipeline
- [ ] Parse · [ ] Chunk · [ ] Contextualize · [ ] Extract · [ ] Resolve · [ ] Retrieve
- [ ] Temporal migration
- [ ] Contracts ontology pack

### Stage 4 — Evaluation
- [ ] Gold set · [ ] Graph-construction metrics · [ ] CI regression gate

### Stage 5 — Control plane
- [ ] JWT auth with verified tenant claim · [ ] API keys · [ ] RBAC · [ ] Metering · [ ] Billing

### Stage 6 — Infrastructure
- [ ] Network/Database/Compute stack split · [ ] Per-environment config · [ ] Secrets · [ ] S3 tenant prefixes

### Stage 7 — Enterprise controls
- [ ] Encryption · [ ] Backups + rehearsed restore · [ ] DPA + subprocessor list · [ ] IR plan · [ ] Model pinning

---

# Part 0 — Strategic position

## 0.1 The premise has to change

The original pitch — "multi-tenant managed GraphRAG SaaS" — is a horizontal product in a category
where the evidence is against the horizontal claim:

- **Microsoft put GraphRAG in maintenance mode** (README: no new PRs, no new features), then
  published **LazyGraphRAG**, whose thesis is *don't build the LLM-extracted graph eagerly* —
  comparable quality at ~0.1% of indexing cost. The largest research org in the category built
  this exact pipeline, measured it, and walked away from the eager version.
- **The accuracy edge is ~3 F1 points.** arXiv 2502.11371: HotpotQA multi-hop 63.01 (GraphRAG)
  vs 60.04 (vector RAG), at a **41–57× construction-cost penalty** and 8.4× query latency. Only
  **13.6% of queries are GraphRAG-only**. arXiv 2506.06331 found published gains were biased
  upward and are "much more moderate than reported." Agentic retrieval is closing the rest.
- **WhyHow.AI — the purest instance of this exact thesis — appears to be gone.** Domain does not
  resolve, GitHub org 404s, no announcement found. **Kùzu** was acqui-hired by Apple and archived
  2025-10-10. These are the two most relevant recent outcomes in the space. *(Both need direct
  diligence before betting against them — see Open Questions.)*
- **Extraction is cheap, so extraction is not a moat.** ~$48–120 per 1,000 documents engineered.

**Where the ground is actually defensible** — all three reports independently converge here:

1. **Entity resolution grounded in an external controlled vocabulary.** The universally-reported
   #1 broken thing. Everyone does LLM fuzzy-dedup; nobody resolves to LEI/CIK, MeSH/UMLS, or a
   party registry. Domain work — which is exactly why AWS and Neo4j won't do it.
2. **Bi-temporal correctness at document scale.** Only Zep/Graphiti has a mature implementation,
   and only for chat episodes, not document corpora.
3. **Human-in-the-loop curation with provenance and approval gates.** What turns a demo into an
   auditable record. No hyperscaler will build it.
4. **Multi-tenant graph isolation as a product.** Structurally hostile to every incumbent's
   pricing: Neo4j at $65–146/GB/month makes 500 small tenant graphs economically absurd.

## 0.2 The chosen position

Per your direction — developer-platform/API first, then mid-market, then regulated enterprise:

> **A multi-tenant knowledge-graph substrate, sold as an API to companies building AI products,
> with one pre-built vertical ontology pack (commercial contracts) shipped as proof that a
> customer never needs a forward-deployed engineer to get value.**

This is the wedge the market research independently identified as unserved, and it matches your
sequencing instinct. The contracts ontology pack matters strategically: both Cognee and Vectara
sell human engineers alongside their software, which means their gross margin is partly services.
**Shipping a working pre-built ontology is the proof that you are software, not consulting.** That
is the single most important thing to demonstrate in the first release.

**The $10k–60k/yr price band is empty** — above Zep's $125/mo developer pricing, below Vectara's
$100k floor. That is the band this product should occupy as it moves from wedge to mid-market.

## 0.3 Trade-offs being accepted, stated plainly

| Accepted | Consequence |
|---|---|
| Not competing on generic RAG accuracy | Any benchmark fight is lost; sell relational/temporal/aggregate/auditable query classes only |
| No Cypher, no Neo4j GDS | Recursive CTEs and in-process igraph; deep (6+ hop) traversal needs the Part 1.4 escape hatch |
| Developer-platform ACVs are small | Slower revenue than enterprise sales — but no 6–12 month security review to survive first |
| Enterprise *controls* built now, *certificates* deferred | Per your instruction. Costs ~3 weeks now, saves a 10× retrofit |
| GraphRAG is an implementation detail, never the pitch | Sell the outcome ("portfolio-level obligation questions with a defensible audit trail") |

---

# Part 1 — Target architecture

## 1.1 Correction: drop Neo4j entirely

I recommended Neo4j database-per-tenant earlier in this session. **That recommendation was wrong,
and the hard limits are why:**

- Neo4j Aura: **max 5 databases per GB RAM, hard ceiling of 100 databases** regardless of instance
  size; **Business Critical tier or above only**; still a **Preview feature** under Experimental
  Service Terms.
- The smallest instance reaching that cap is ~$4,672/month → a **$47/tenant/month floor at perfect
  packing**. At 1,000 tenants you need 10 instances ≈ **$46,720/month**.
- Self-managed is nominally unbounded but shares one JVM heap and one page cache; the only concrete
  public data point is an operator hitting `Too many open files` at ~250 databases.
- For calibration: GitLab bulk-imported **8M nodes / 11M edges / 21 GB** into Neo4j on a
  **~$105/month** GCP instance. A 19M-element graph costs about $105/month of compute. The Aura
  multi-tenant pricing is two orders of magnitude off that.

The isolation and GDPR arguments I made for database-per-tenant were right about the *requirements*
and wrong about the *mechanism*. Postgres satisfies both requirements better.

## 1.2 Canonical store: Postgres + pgvector + RLS

**Postgres is the system of record for documents, chunks, mentions, facts, entities, edges,
ontologies, decisions, usage, and audit.** Edges live in an indexed table with `tenant_id` as the
leading column of every composite index. Graph algorithms (Leiden, personalized PageRank) run
offline in-process via `igraph`/`graspologic` over a per-tenant subgraph loaded into memory.

Why this is right for this product specifically:

1. **The retrieval shape is bounded neighborhood expansion, not deep traversal.** Vector-search
   seeds → 1–3 hop expansion → rank → assemble. Indexed relational joins are competitive in exactly
   that regime; index-free adjacency only dominates at 6+ hops.
2. **RLS is the only isolation mechanism in the entire comparison that fails closed.** Neo4j has no
   row-level-security equivalent. Every graph-store alternative — Neo4j `tenant_id`, Neptune pool,
   Graphiti `group_id` — is a predicate your code must remember. **Graphiti issue #1676 is what that
   costs in practice: 19 episodes leaked across 5 tenants in production**, because a driver mutated
   shared state between database selection and write. Measured RLS overhead is ~3.6 ms vs 3.2 ms
   for 100k rows across 1,000 tenants — *provided* `tenant_id` leads every composite index.
3. **One transactional store makes GDPR deletion tractable.** The delete cascade (Part 2.3) must be
   atomic. Across Postgres-as-truth plus Neo4j-as-truth it is a dual-write consistency problem on
   the one operation you cannot afford to get wrong.
4. **Nothing is foreclosed.** You own the canonical edges, so a per-tenant graph read-model later
   is a projection job, not a migration.

**Ruled out, with reasons worth recording:**

| Option | Disqualifier |
|---|---|
| Neptune Analytics | **One vector index per graph, dimension fixed at creation, vector writes "non-atomic and not isolated"** |
| FalkorDB | **SSPLv1** — its own docs say offering it as a service requires releasing your whole service's source. Needs a signed commercial license *before* any code is written against it |
| ArangoDB | BUSL 1.1, 100 GiB community cap |
| Memgraph | BSL 1.1 |
| Kùzu | **Archived 2025-10-10** (Apple acquisition); GitLab had to migrate off it mid-project |
| Dgraph | Apache 2.0 now, but twice-acquired since 2023; DQL not Cypher |
| Apache AGE | Credible fallback if Cypher is genuinely wanted — same Postgres, same RLS. Cost: weak variable-length paths, trails Postgres major versions |

## 1.3 Orchestration: Temporal, not Celery

Celery is a fine task queue and a poor workflow engine. Your pipeline is a workflow, and the
specific failures are not theoretical:

- **At-least-once + visibility timeout = duplicate paid LLM calls.** A 5-minute extraction under a
  3-minute visibility timeout runs twice on two workers. Your longest task is *unbounded* (a
  500-page document with gleaning), so there is no correct timeout value.
- **No durable workflow state.** Worker dies at step 7 of 9 → re-run the pipeline, re-pay every LLM
  call already bought. At $0.12–1.40 per document that is a P&L line, not an inconvenience.
- **Human-in-the-loop is a product requirement here**, and the entity-resolution review queue needs
  a workflow that pauses indefinitely and resumes on a human decision. Temporal Signals do this
  natively. In Celery you would build a state machine in Postgres and a polling loop — i.e. a worse
  Temporal.
- Redis is single-threaded; every push/pop/ack/timeout-check is on one core.

**Also ruled out: AWS Step Functions** — the **256 KiB payload limit** is disqualifying for a
document pipeline (every chunk list and candidate-pair batch exceeds it), and the **25,000-event
execution-history cap** bites on per-chunk fan-out. Express workflows dodge the history cap but
**stop at 5 minutes**. Prefect/Dagster are batch-DAG tools, wrong shape for per-document,
long-running, human-interruptible work. Ray is a compute framework — correct *inside* an activity
for GPU fan-out, not as the orchestrator.

Temporal Cloud: $50/M actions falling to $25/M at volume, no minimums. Self-hosting only pays at
~30–50M actions/month with an existing Kubernetes+Cassandra team.

**Migration shape:** your existing Celery task bodies are already the right activity granularity
(parse, chunk, contextualize, extract, resolve, materialize). Wrap each as a Temporal activity, then
write the workflow that sequences them. **Cost: ~2 weeks of ramp** on workflow determinism (no
`datetime.now()`, no random, no direct I/O in workflow code) and versioning discipline.

## 1.4 Target repository structure

```text
semanticgraph-cloud/                    # ONE git repo at the root
├── pyproject.toml                      # uv workspace, root project
├── uv.lock
├── src/semanticgraph/
│   ├── domain/                         # zero framework imports (already correct — keep)
│   │   ├── models/                     # Document, Chunk, Mention, Fact, GoldenRecord, Ontology
│   │   ├── provenance/                 # FactAssertion, SourceSpan  ← new, load-bearing
│   │   ├── temporal/                   # ValidInterval, TransactionInterval  ← new
│   │   └── value_objects/
│   ├── application/
│   │   ├── ports/outbound/             # + OntologyRegistry, ResolutionJudge, VocabularyResolver
│   │   └── use_cases/
│   ├── adapters/
│   │   ├── inbound/
│   │   │   ├── api/v1/                 # FastAPI
│   │   │   └── workflows/              # Temporal workflows + activities  ← replaces workers/
│   │   └── outbound/
│   │       ├── postgres/               # canonical store: graph, vectors, RLS
│   │       ├── llm/                    # provider abstraction (BYO-model seam)
│   │       ├── extraction/             # GLiNER prefilter + structured extraction
│   │       ├── resolution/             # Splink + clustering + LLM adjudication
│   │       ├── vocabulary/             # LEI/CIK/MeSH adapters  ← the differentiator
│   │       └── graphprojection/        # no-op today; the Neo4j/FalkorDB escape hatch
│   ├── composition/                    # Container built at startup, on app.state
│   └── control/                        # tenants, quotas, usage ledger, audit log
├── ontologies/contracts/               # the pre-built vertical pack
├── evals/                              # gold sets + graph-construction metrics
├── tests/{unit,integration,e2e,evaluation}/
├── infra/                              # CDK: Network / Database / Compute stacks
├── frontend/                           # ONE frontend
└── docs/{adr,architecture}/
```

**Deleted:** `backend/`, `src/api/`, `src/pipeline/`, `src/models/sql.py`, `src/frontend/`,
`infrastructure/`, `models/` (port billing/compliance intent first), `graphify-out/`,
`test_worker.py`, `verify_models.py`, `run_pytest.py`, `screenshot.png`, and the nested `.git`
directories in `backend/`, `infra/`, `src/frontend/`. `ECC/` moves out of the deployable tree.

---

# Part 2 — The decisions that are irreversible

Everything else in this plan can be changed later. **These five cannot**, and every one of them is
a schema decision that has no backfill path. If nothing else in this plan gets built, build these.

## 2.1 Mandatory provenance spans — the most expensive thing to get wrong

Every extracted fact carries the chunk and the character span it came from, and the field is
**non-nullable from the first document ingested**.

```
document → chunk → mention(span) → fact_assertion(fact_id, chunk_id, span, extraction_run_id)
fact  ← many fact_assertion        -- a fact is alive iff ≥1 live assertion
```

Without complete spans, **GDPR deletion, citation, hallucination detection, and incremental update
are all retroactively impossible** — facts already in the graph have no traceable origin, and the
only fix is re-extracting the entire corpus at full cost. Make the span mandatory *in the extraction
schema* too; if it is optional the model will omit it.

Free bonus: programmatically verifying the claimed span actually exists in the chunk is a
deterministic, zero-cost hallucination detector that catches a large class of fabrication.

## 2.2 Non-destructive entity resolution

A golden record is a **projection of a versioned decision log**, never a row you rewrite.

```
mention (immutable)
  → cluster_membership(decision_id, source: human|model|rule, confidence, decided_at)
    → golden_record (materialized view)
```

A merge is an insert. **An unmerge is a retraction of a decision, not a delete of data.** If you
store merges destructively, unmerge is unimplementable and you ship "contact support to undo."

**Human decisions outrank model decisions permanently.** Without this, every model upgrade silently
re-merges entities a customer already separated — the single most trust-destroying bug this product
can have.

Expect **~80–90 F1** as the realistic ceiling on hard entity matching (WDC Products hard variants:
72.18–79.99 F1 for top fine-tuned systems) and **design the product to survive being wrong**. The
review queue is a first-class product surface, not an admin page.

## 2.3 Assertion-counted deletion

Deleting document D removes exactly D's contribution: delete D → cascade chunks → cascade
`fact_assertion` rows → garbage-collect facts and cluster memberships with **zero remaining
assertions** → re-materialize affected golden records → invalidate affected community summaries.
One Postgres transaction.

Routinely forgotten and in scope for erasure: **embeddings, reranker caches, LLM prompt-cache
entries, community summaries quoting deleted text, and eval fixtures built from customer data.**
A summary generated from a deleted document still contains the deleted personal data. Note also the
Hamburg DPA position that high-dimensional embeddings may remain re-identifiable — "we deleted the
text but kept the vectors" is not defensible.

The EDPB made right-to-erasure its 2025 coordinated enforcement action. This is being actively probed.

## 2.4 Immutable versioned ontologies

Ontologies are versioned objects; editing creates a new version. Every extraction run records
`ontology_version`. Editing in place makes every fact extracted under the old version unattributable
and makes "why does this entity have this type?" unanswerable.

## 2.5 Engine-enforced tenant isolation

`tenant_id` on **every** table, including where it looks redundant, as the **leading column of every
composite index** (missing that is the single biggest RLS performance killer). `ALTER TABLE … FORCE
ROW LEVEL SECURITY` plus an application role that does **not** own the tables — `ENABLE` alone is
silently bypassed by the owner, which is the most common production pitfall.

Tenant context via `SET LOCAL` / `set_config(..., true)` **inside the transaction**. Session-level
`SET` under transaction-mode PgBouncer persists on the pooled connection and hands the next client
the previous tenant's context — that is a data breach, not a bug.

Fail closed: unset tenant yields `NULL`, `tenant_id = NULL` is never true, zero rows. **Test that
every table returns zero rows with no tenant context.**

---

# Part 3 — Execution stages

Each stage is independently shippable. Sized for a small team; parallelizable if there are more hands.

## Stage 0 — Repository foundation (3–5 days)

1. `git init` at root; `.gitignore` for `.venv/`, `__pycache__/`, `node_modules/`, `cdk.out/`,
   `graphify-out/`, `.uv_cache/`, `*.pyc`, `.env`.
2. Root `pyproject.toml` + `uv.lock`, replacing the 8-unpinned-name `requirements.txt`.
3. Execute the Part 1.4 deletions. **Confirm which of the `backend/` / `infra/` / `ECC/` /
   `src/frontend/` histories matter before removing any `.git`.**
4. First commit.
5. CI repointed at the root project and `tests/` — it currently runs `cd backend && pytest`, testing
   the deprecated scaffold on Python 3.10 against a `requirements.txt` that doesn't exist.

## Stage 1 — Correctness of what already exists (3–5 days)

1. **Remove the production→test import.** `adapters/inbound/api/app.py:33` imports
   `FakeGraphRepository` from `tests.unit.use_cases.test_ingest_document` in the FastAPI lifespan —
   the running API imports the test suite. Move fakes to
   `adapters/outbound/inmemory/` as first-class dev adapters, selected by config.
2. **Replace the global-variable composition root.** `composition/container.py` uses module globals
   guarded by `assert` — stripped under `python -O`, and `None` in forked workers. Build a
   `Container` at startup, store on `app.state`.
3. **Fix the async/sync boundary.** `PostgresDocumentRepository` declares `async def` over blocking
   SQLModel `Session` I/O, blocking the event loop. Move to `AsyncSession` throughout.
4. **Make `docker-compose.yml` real** — api and worker currently run
   `python -c 'import time; sleep(3600)'`.
5. **Architecture-fitness test**: fail the build if `domain/` or `application/` imports `fastapi`,
   `sqlmodel`, `temporalio`, or any driver. This one rule keeps the hexagon honest as the code grows.

## Stage 2 — The irreversible schema (2–3 weeks) ← the real foundation

Implement Part 2 in full: Alembic baseline; `tenant_id` everywhere with leading-column indexes;
FORCE RLS + non-owner app role + fail-closed tests; the
`document → chunk → mention → fact_assertion → fact` provenance chain with mandatory spans;
bi-temporal `valid_from/valid_to` + `created_at/expired_at` with edge invalidation rather than
deletion; the versioned resolution decision log; immutable ontology versions; and the
assertion-counted delete cascade with a test that proves deleting one of two supporting documents
leaves the fact alive and deleting both removes it.

Also in this stage, because they are equally hard to retrofit:

- **Usage event ledger** — one immutable row per cost-driving event, client-generated `event_id`
  with a unique constraint for idempotency, `occurred_at` separate from `recorded_at`, actual token
  counts read from the provider response (not estimated), price version stamped. **Usage you didn't
  record is revenue you cannot bill, and there is no backfill.** Emit server-side, at the call site
  that incurs the cost — not at the API boundary, where a retrying activity three layers down will
  escape you.
- **Append-only audit log** — auth, authz failures, admin changes, data access, export, deletion,
  API key lifecycle, and **every LLM invocation** (tenant, user, model, version, token counts,
  scope). No UPDATE/DELETE grant to the app role. Retain 15 months (SOC 2 Type II window + buffer).
- **OpenTelemetry with `tenant_id` on every span, metric, and log line**, propagated explicitly
  through Temporal activity headers. Instrument the stable `gen_ai.*` core now (operation, provider,
  model, input/output tokens) — it is also your billing and cost-attribution substrate.
  **Never put document content in telemetry** — log IDs and hashes only, or your observability
  retention window becomes a disclosed GDPR exposure. Enforce with a review rule before there are
  200 log statements.
- **Per-tenant spend cap.** With token-priced inference, an unbounded tenant is an unbounded AWS
  bill. Enforce entitlements *before* the expensive call.

## Stage 3 — The pipeline (4–6 weeks)

**Parse** → Docling default tier, Reducto or Azure Document Intelligence as a premium tier for
table-heavy corpora (Reducto reports 90.2% on complex tables vs Azure DI 82.7%, AWS Textract 80.9%,
Google Document AI 64.6% — *on Reducto's own benchmark*).

**Chunk** → structure-aware, never splitting a table or list, targeting **~600 tokens**. This is
not arbitrary: Microsoft's data shows a 600-token chunk yields **nearly 2× the entity references**
of a 2400-token chunk. Smaller chunks → higher recall → more calls → more cost → more duplicates to
resolve. Tune it as one dial, not three.

**Contextualize** → Anthropic Contextual Retrieval blurbs with Haiku 4.5 + prompt caching + Batch
API. Measured: **failed retrievals down 49%**, or **67%** with reranking added. ~$15–35 per 1,000
documents.

**Extract** → two-stage cascade:
- Stage 1: **GLiNER** over every chunk for type detection (CPU-viable, ~130× the throughput of
  comparable models with cached label embeddings). Cuts LLM calls 50–70%.
- Stage 2: **`claude-sonnet-5`** on flagged chunks, with **ontology snippets** (the relevant subset
  of types per chunk, not the whole ontology), prompt-cached, batched, **reasoning field first and
  structured fields after** — this ordering recovers most of the documented 10–30% reasoning
  degradation under strict output constraints — and **mandatory source spans**.
- Escalate to **`claude-opus-5`** only on low confidence or ontology-validation failure.
- Validate `(subject_type, predicate, object_type)` legality against the ontology graph *after*
  decoding. JSON schema enforces shape, not legality.
- Gleaning count is a per-tenant tier setting, **default 1** — it is reportedly two-thirds of
  ingestion prompt tokens and nobody has measured what it adds. Measure it on your own eval set.

**Resolve** → multi-strategy blocking union (normalized exact, phonetic, `pg_trgm`, pgvector ANN)
→ **Splink** probabilistic scoring plus graph-structural signals (shared neighbors, co-occurrence,
Adamic-Adar) → correlation/Leiden clustering on the match graph, **not connected components** (one
bad edge merges two companies) → Haiku 4.5 adjudication on the ambiguous band only, batched →
decision log. **Then the differentiator: resolve against an external controlled vocabulary**
(LEI/CIK for the contracts pack) instead of generic fuzzy dedup, which converts the hardest problem
in the category into a lookup.

**Retrieve** → cheap query router (a classifier, not an LLM call, on the hot path) → local search by
default (pgvector seeds → 2-hop expansion → PPR → cross-encoder rerank) → **lazy global search**:
Leiden communities computed on a schedule, summaries generated **on demand and cached**. Eager
summarization of every community for every tenant is the largest avoidable line item in a
multi-tenant deployment, and most tenants never issue a global query.

P95 retrieval budget ~350 ms (40 embed/classify + 60 vector + 80 expansion + 60 scoring + 80 rerank
+ 20 assembly), then 600–1200 ms to first generated token. Budget on P95 — retrieval P95 is reported
at ~64× median.

Context construction: **don't serialize triples.** Emit golden records with canonical descriptions,
relationship paths as short natural-language statements, and **verbatim source chunks with
citations**. The graph selects which chunks to include; the LLM still answers from text.

## Stage 4 — Evaluation (1–2 weeks, then continuous)

**DeepEval** for the CI gate (pytest integration decides it for a small team), Ragas metrics
alongside, **Phoenix or Langfuse** for production tracing and mining new eval cases from real traffic.

**Hand-roll the graph-construction metrics — no framework has them:** entity extraction P/R/F1
against a per-ontology gold set; **ontology conformance rate** (should be ~100% under constrained
decoding; deviation is a regression signal); **span-grounding rate**; resolution precision/recall
with **over-merge rate tracked separately** (very different product consequences); entity coverage;
**provenance completeness** (must be 100% — anything else is a deletion-correctness bug).

Regression design for a nondeterministic pipeline: **freeze LLM outputs as replay fixtures** — that
makes graph assembly, resolution, deletion cascade, and retrieval deterministically testable;
100–300 gold cases; run each 3–5× and gate on consistency (4/5), not exact match; gate on
**statistical significance** against a rolling baseline (Welch's t-test, Wilson intervals), not point
estimates; version prompt, model ID, ontology version, and chunker config on every run or you cannot
attribute a regression.

**Tag every eval case with its source tenant and document** — GDPR erasure covers your fixtures, and
you do not want to choose between compliance and your regression suite.

## Stage 5 — Control plane and commercial surface (2–3 weeks)

Auth (Stage 5 is where it lands *for the API wedge*; move it earlier if selling to an enterprise
first): OIDC/JWT with `tenant_id` as a **verified claim**, never the current unsigned `X-Tenant-ID`
header. Hashed, per-tenant, individually revocable API keys with last-used timestamps — for a
developer-platform wedge these matter more than SSO. RBAC (admin/member/viewer) with a `permissions`
seam so ABAC can slot in later without a rewrite.

**Buy WorkOS when the first SSO ask arrives**: $125/connection/month for SSO, $125 for SCIM
(**billed separately** — $250/mo for a customer wanting both) against **6–12 engineer-weeks** to
build SAML+SCIM credibly plus an ongoing support load that lands on your most senior engineer. Buy it.

Metering on the Stage 2 ledger; Stripe Billing with meters; **three-way reconciliation** (your
ledger vs billing provider vs the upstream Anthropic/Bedrock invoice) — that third leg is what
catches margin erosion and is the one everyone skips.

Pricing: **ingest-metered**, per document or per 1M tokens processed, storage and retrieval near-free
— it aligns price with your dominant cost and avoids Neo4j's per-GB trap. Benchmarks: Cognee $1.00/1M
tokens; Zep $125/mo for 50k credits (1 credit per 350 bytes ingested); Vectara $100k/yr floor.
**Meter tokens internally even while billing per document**, or a 400-page manual costing 50× a
2-page memo erodes margin invisibly.

## Stage 6 — Infrastructure (2–3 weeks)

Split `infra/` into **NetworkStack / DatabaseStack / ComputeStack** as `tickets/ticket-infra-design.md`
already specified. Rename off the default `InfraStack` **before anything is deployed for real** —
construct-id changes are replacements. Set `env=` explicitly; environment-agnostic stacks break AZ
and AMI lookups.

Per-environment parameterization: `RemovalPolicy.RETAIN` and `deletion_protection=True` outside dev
(currently `DESTROY`/`False`), Multi-AZ, PITR. Add Secrets Manager, ECS Fargate for API and Temporal
workers, S3 with **per-tenant key prefixes and scoped STS credential vending**, ALB + WAF, CloudWatch
alarms.

**Keep the CDK app deployable as a whole unit into a fresh AWS account from day one, and never
introduce a hard dependency on a resource in your account.** That discipline is nearly free now and
is the difference between six months and eighteen when a regulated buyer demands BYOC. Doing BYOC
*later* with a stateful store in the customer's account is the single hardest item in this plan.

## Stage 7 — Enterprise controls (ongoing, certificates deferred)

Per your instruction: build every technical control, defer only the audits.

**Build now:** encryption at rest/transit, secrets management, MFA on admin, the Stage 2 audit log
and ledger, retention and deletion paths, per-tenant rate limits and spend caps, model version
pinning surfaced per tenant, the LLM provider abstraction (the BYO-model seam), backups **with one
rehearsed restore**, a two-page incident response plan, a `security@` address, a DPA template, and a
**published subprocessor list** naming your model providers — 63.6% of AI vendors disclose no AI
subprocessor anywhere, so doing it is a cheap differentiator.

**Prompt-injection containment is a design property, not a filter.** You ingest untrusted
third-party documents — that is the product, and prompt injection is OWASP LLM01. The architectural
answer: **the model must never hold a tool capable of crossing a tenant boundary**, so a successful
injection is bounded by the tenant.

**Defer:** SOC 2 Type II ($30–90k, **~6 months of calendar that no amount of money compresses** —
start the clock earlier than feels necessary), ISO 27001, ISO 42001 (write the one-page AI governance
policy now, certify later), HIPAA, pen test (until asked; then $10–25k).

**EU AI Act:** you are almost certainly not high-risk under Annex III and not a GPAI provider. Real
obligations are Article 50 transparency and Art. 4 AI literacy. The Digital Omnibus (in force
2026-07-27) **deferred Annex III high-risk to 2027-12-02** — most advice online is stale. Your actual
exposure is contractual: customers deploying you in a high-risk context push their obligations down
to you. **Address it in the acceptable-use policy.**

---

# Part 4 — Buy, don't build

| Need | Decision | Why |
|---|---|---|
| SSO / SCIM | **Buy — WorkOS** | $250/mo/customer vs 6–12 engineer-weeks + permanent support load |
| Billing | **Buy — Stripe Billing**, own the ledger | The ledger is the durable asset; the vendor is swappable |
| Compliance automation | **Buy — Vanta/Drata/Secureframe** | Functionally interchangeable; negotiate a 2-year rate, they all raise at year-2 renewal |
| Orchestration | **Buy — Temporal Cloud** | Self-hosting pays only at 30–50M actions/mo with a K8s+Cassandra team |
| Entity resolution core | **Build on Splink** (open, fast, explainable) | Evaluate **Senzing** (~$0.0059/record/yr) if ER becomes *the* product |
| Controlled vocabularies | **Build** | This is the differentiator — the one thing not to outsource |
| Graph store | **Build on Postgres** | See Part 1.2 |
| Document parsing | **Buy per tier** — Docling free / Reducto or Azure DI premium | Quality gap is real and measured |
| Eval metrics for graph construction | **Build (~500 LOC)** | No framework measures extraction F1, ontology conformance, or over-merge |

---

# Part 5 — Unit economics

Per document = 10 pages ≈ 5,000 tokens ≈ 30 chunks.

| Stage | Naive | Engineered |
|---|---|---|
| Parse | $0.015 | $0.002 |
| Contextual blurbs | $0.033 | $0.017 |
| Extraction | $1.40 (Opus 5, 2 gleanings, no cache/batch) | $0.048 (GLiNER prefilter → Sonnet 5, cached, batched, 1 gleaning) |
| Entity resolution | $0.020 | $0.004 |
| Community summaries | $0.026 (eager) | ~$0.002 (lazy, amortized) |
| Embeddings | $0.0001 | $0.0001 |
| Graph storage | ~$0.0001 | ~$0.0001 |
| **Per document** | **~$1.49** | **~$0.073** |
| **Per 1,000 documents** | **~$1,494** | **~$73** |

**~20× between a working implementation and an engineered one**, before any distillation. Price
against the engineered number and build toward it, or the ingest tier runs at negative gross margin.

Levers in order of savings per unit of effort: **prompt caching** (0.1× reads — the ontology prefix
is identical across every chunk) → **Batch API** (another 50%, and it *stacks* with caching; nothing
in ingest needs sub-24h latency) → **model routing** → **GLiNER prefilter** → **lazy summaries** →
**chunk content-hash dedupe** (enterprise corpora are full of repeated boilerplate) → distillation
in phase 3 (machine-labeled training sets land within 1.78 F1 of human-labeled).

**Stop optimizing embeddings** — at $0.02/M tokens, embedding 1,000 documents costs $0.12. It is noise.

**Add an integration-test assertion that `usage.cache_read_input_tokens > 0`.** A timestamp, a UUID,
or an unsorted `json.dumps()` anywhere in the cached prefix silently drops cache hits to zero with no
error and a ~10× cost increase on your largest line item.

Realistic blended gross margin: **70–80%**. Not 85%+, if you re-extract on schema changes or run
frontier models. **The thing that destroys the model is forward-deployed engineering** — which is
why the pre-built contracts ontology (Part 0.2) is a business-model decision, not a feature.

---

# Part 6 — Verification

- `uv run pytest tests/ -v` passes from the root project with no import of `backend/`, `src/api/`,
  or `src/pipeline/`.
- `uv run ruff check . && uv run pyright` clean.
- **Architecture-fitness test** passes: no framework imports in `domain/` or `application/`.
- **Isolation:** every table returns zero rows with no tenant context set; tenant A's token gets 404
  for tenant B's document; a deliberately unfiltered query returns nothing under FORCE RLS.
- **Provenance:** 100% of facts have ≥1 live assertion; every claimed span verifiably exists in its
  chunk.
- **Deletion:** a fact supported by documents D and E survives deleting D and disappears on deleting
  E; affected summaries are invalidated; the whole cascade is one transaction.
- **Resolution:** a human "these are different" decision survives a full model-upgrade re-run.
- **Cost:** a 100-document ingest reports per-document cost within 20% of the engineered model, with
  `cache_read_input_tokens > 0` on every extraction call.
- **Pipeline:** `docker compose up` → `POST /v1/documents` → Temporal UI shows the workflow →
  entities land in Postgres → a multi-hop query returns cited paths.
- `cd infra && cdk synth` produces three named stacks.
- CI green including the coverage gate and the eval regression gate.

---

# Part 7 — Suggested order

**Stage 0 → 1** (repo + correctness, ~2 weeks) → **Stage 2** (irreversible schema, 2–3 weeks —
*this is the "super strong base" you asked for*) → **Stage 3** (pipeline, 4–6 weeks) →
**Stage 4** (eval, 1–2 weeks) → **Stage 5** (control plane, 2–3 weeks) → **Stage 6** (infra, 2–3
weeks) → **Stage 7** (continuous).

Roughly **14–20 weeks** to a defensible v1 at small-team pace. Stages 0–2 are ~5 weeks and are the
part where deferral is genuinely expensive — everything after is money or calendar; that part is
neither.

---

# Part 8 — Open questions

Answerable in parallel with Stage 0–1; none block starting.

1. **Verify WhyHow.AI's fate** (Crunchbase, LinkedIn, founders). If they were acquired rather than
   shut down, the read on the category changes.
2. **Which controlled vocabulary ships first?** LEI/CIK (contracts/finance) is the recommendation —
   free, authoritative, and the contracts ontology is reusable across every customer.
3. **Confirm the Temporal Cloud bill** at your projected volume before committing.
4. **`ECC/` disposition** — submodule, external path, or delete. It is 257 MB / 11,747 files of
   vendored skills inside the deployable tree.
5. **Which nested git histories matter** (`backend/`, `infra/`, `ECC/`, `src/frontend/`) before any
   `.git` is removed.
6. Re-verify the EU AI Act dates against the OJ text before they go in any customer-facing document.

---

## Appendix — what changed from the first plan, and why

| First plan | Now | Cause |
|---|---|---|
| Implement `Neo4jGraphRepository` | **Drop Neo4j; Postgres + pgvector + RLS** | Aura caps at 100 DBs / 5 per GB RAM, Business Critical only, still Preview; ~$47/tenant/mo floor vs ~$105/mo for a 19M-element graph on plain compute |
| Neo4j database-per-tenant for isolation | **FORCE RLS in Postgres** | RLS fails closed; every graph-store option is an app-layer predicate. Graphiti #1676 leaked 19 episodes across 5 tenants in production |
| Fix Celery's async boundary | **Migrate to Temporal** | At-least-once + unbounded task duration = duplicate paid LLM calls; no durable state; HITL review queue needs Signals |
| RLS + migrations as "Stage 3 blockers" | **Stage 2, alongside provenance and the decision log** | Provenance spans have no backfill path — the most expensive item to get wrong |
| Horizontal managed GraphRAG SaaS | **Developer-platform wedge + one pre-built vertical ontology** | Microsoft's own maintenance-mode + LazyGraphRAG result; ~3 F1 points at 41–57× build cost; WhyHow.AI gone |
| — | **Usage ledger + audit log + OTel tenant attribution in Stage 2** | Unrecorded usage is unbillable, and none of the three backfills |
