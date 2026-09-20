# The developer product surface — console, onboarding, and the three screens that are the product

**Ticket** T-902 · **Date** 2026-09-20 · **Status** research complete

Scope: what screens a developer-first knowledge-graph API needs, in what order, and what the
shortest path from landing page to first API response looks like. Grounded in vendor primary
sources (docs, quickstarts, console guides) fetched 2026-09-20. Anything not confirmed from a
primary source is tagged **[UNVERIFIED]**.

Read against `docs/architecture/ENTERPRISE_PLAN.md` Part 0.1 (the four defensible differentiators),
Part 0.2 (the wedge), and Part 3 Stage 3/5 (pipeline and control plane).

---

## 1. The standard console surface for AI-infrastructure products

### 1.1 What was checked

| Vendor | Primary source |
|---|---|
| Pinecone | [quickstart](https://docs.pinecone.io/guides/get-started/quickstart), [manage API keys](https://docs.pinecone.io/guides/projects/manage-api-keys), [monitor usage](https://docs.pinecone.io/guides/organizations/manage-cost/monitor-your-usage), [llms.txt](https://docs.pinecone.io/llms.txt) |
| Weaviate Cloud | [Cloud quickstart](https://docs.weaviate.io/cloud/quickstart), [query tool](https://docs.weaviate.io/cloud/tools/query-tool), [cluster status](https://weaviate.io/developers/wcs/cluster-status) |
| Zep | [quickstart](https://help.getzep.com/v2/quickstart), [customizing graph structure](https://help.getzep.com/customizing-graph-structure), [set_ontology SDK ref](https://help.getzep.com/sdk-reference/graph/set-ontology), [changelog 2026-06-10](https://help.getzep.com/changelog/2026/6/10) |
| Supabase | [SQL editor](https://supabase.com/features/sql-editor), [tables and data](https://supabase.com/docs/guides/database/tables), [logs](https://supabase.com/docs/guides/telemetry/logs) |
| Neon | [tour the console](https://neon.com/docs/get-started-with-neon/signing-up), [manage API keys](https://neon.com/docs/manage/api-keys), [monitoring page](https://neon.com/docs/introduction/monitoring-page), [changelog 2026-01-09](https://neon.com/docs/changelog/2026-01-09) |
| Clerk | [Next.js quickstart](https://clerk.com/docs/quickstarts/nextjs) |
| Resend | [introduction](https://resend.com/docs/introduction) |
| Modal | [playground](https://modal.com/playground), [pricing](https://modal.com/pricing) |
| LangSmith | [observability in Studio](https://docs.langchain.com/langsmith/observability-studio), [annotation queues](https://docs.langchain.com/langsmith/annotation-queues) |
| Neo4j Aura | [visual tour of the console](https://neo4j.com/docs/aura/visual-tour/), [Explore](https://neo4j.com/docs/aura/explore/introduction/) |
| Cognee | only third-party/indirect sources found for a hosted console — **[UNVERIFIED]** |

### 1.2 The union of screens, and which are table stakes

**Table stakes** — absent any one of these, a developer concludes the product is not real:

| Screen | Purpose | Seen in |
|---|---|---|
| **API keys** | Create, name, scope, reveal-once, last-used timestamp, revoke. Pinecone scopes keys per *project*, not per org — the right granularity. | Pinecone, Neon, Resend, Clerk, Weaviate, Modal |
| **Usage / quota / cost** | Units consumed vs. plan, a time series, a downloadable report. Pinecone puts this at Settings > Usage; Neon has a per-branch/per-compute monitoring page. | all |
| **Request logs / run inspection** | One row per API call or job, filterable, drill-down to inputs/outputs/latency/error. Supabase's Logs Explorer exposes each stack component as a SQL-queryable table; LangSmith's traces are the richest version. | Supabase, LangSmith, Neon, Resend, Modal |
| **Data browser** | See the rows the API wrote without writing client code. Supabase Table Editor, Neon SQL Editor (with pre-filled placeholder SQL), Weaviate query app, Neo4j Explore. | Supabase, Neon, Weaviate, Neo4j, Zep |
| **Team / members / roles** | Invite, role assignment, org→project hierarchy. | all |
| **Billing / plan** | Plan, payment method, invoices. | all |
| **Project / environment switcher** | The org → project → environment hierarchy in the chrome, current scope always visible. | all |

**Differentiated** — present in the better consoles, not universal:

| Screen | Why it differentiates |
|---|---|
| **Playground / query tool in browser** | Weaviate ships a GraphQL IDE in-console; Neon ships a SQL editor with placeholder SQL pre-loaded and an AI "Generate SQL" button; LangSmith's Playground runs prompts and evaluations from the UI. The difference between "I read about it" and "I saw it work". |
| **Command palette (Cmd+K)** | Neon added a console-wide palette scoped to the current branch/project ([changelog 2026-01-09](https://neon.com/docs/changelog/2026-01-09)). An expectation in dense consoles now, not a flourish. |
| **Branch / environment isolation** | Neon's branch picker splits the sidebar into project-level items (Dashboard, Branches, Integrations, Settings) and branch-level items (Overview, Credentials, Monitoring). Directly analogous to what we need for ontology versions. |
| **Human-review queue** | LangSmith annotation queues — the closest console prior art for our resolution queue. |
| **Domain / connection verification** | Resend's Domains screen: a blocking prerequisite surfaced as its own first-class screen with its own status. Analogous to "is a controlled vocabulary connected?". |

**Notable absence worth copying:** none of these consoles has a *chat* screen. Zep, the closest
competitor, exposes its graph as an inspection view hung off a user (`Users > user123 > View Graph`),
not as a conversational product surface.

---

## 2. Time to first value

### 2.1 Traced paths (from the vendors' own quickstarts)

| Vendor | Steps, landing → first successful response | Key visible before signup completes? | curl with live key pre-filled? | In-browser playground before install? |
|---|---|---|---|---|
| **Neon** | ~3 in-console actions after signup: open SQL Editor → branch/db already selected → click Run on **placeholder SQL already in the editor**. | No, but a connection string is the first thing surfaced | n/a (SQL) | **Yes** — SQL Editor, plus AI-generated SQL |
| **Modal** | Sign up with GitHub/Google → `pip install modal` → `modal setup` → write `hello_world.py` → `modal run`. ~5. $5 credit on signup, $30/mo with a card. | No | No | **Yes** — hosted [playground](https://modal.com/playground), "run your first function" |
| **Weaviate Cloud** | 7 documented steps; cluster provisioning 1–3 min; free-forever sandbox tier. | No | No | Yes — console query app, but the quickstart routes you to a client library first |
| **Clerk** | `npx -y clerk@latest init` does framework detection, key provisioning and file edits in one command; docs state *"Setup is `npx -y clerk@latest init`, signed in or not"*. Effectively **1–2**. | Yes — the CLI provisions the app and writes the keys | n/a | No, but `clerk doctor` verifies |
| **Pinecone** | The *recommended* 2026 path is agent-assisted: `export PINECONE_API_KEY` → `claude plugin install pinecone` → `/pinecone:quickstart`. **3**, and the agent does the rest. Account and key are a prerequisite, not documented in-page. | No | No | Not in the quickstart |
| **Resend** | Blocked on a prerequisite: **your own verified domain** plus an API key, before the first send. Longest documented path in the set. | No | No | No |
| **Stripe** (reference standard, not an AI product) | Every code sample in the API reference carries a **working sample test key**, so any example is runnable by copy-paste with zero setup; signing in swaps in your own key. ([keys](https://docs.stripe.com/keys), [API reference](https://docs.stripe.com/api)) | **Yes — effectively a shared public test key** | **Yes** | The docs *are* the playground |

### 2.2 Findings

- **Median: ~4 steps.** Fastest are Clerk (a single `init` that provisions the app and writes keys)
  and Neon (placeholder SQL already in the editor, one click to run).
- **Nobody in this set hands you a live key before signup.** Stripe comes closest, by publishing a
  *shared sample test key* baked into every snippet — the cheapest, highest-leverage trick available,
  and it is a decade old.
- **The 2026 shift: the first step is now an agent step.** Pinecone's own recommended quickstart is a
  Claude Code plugin; Clerk's is a CLI that detects the framework. Docs are being written for an agent
  to execute, not a human to read. Pinecone publishes `docs.pinecone.io/llms.txt`.
- **The slowest paths are those with a blocking prerequisite** (Resend: verify a domain; Weaviate:
  provision a cluster). Any prerequisite we impose before the first response — pick an ontology,
  create a project, connect a vocabulary — costs us the wedge.

### 2.3 What this means for us

Our equivalent of "placeholder SQL already in the editor" is a **pre-seeded demo tenant**: on first
login the account already contains a small contracts corpus, ingested, resolved and queryable under
the shipped contracts ontology pack. The user's first action is *reading an answer with citations*,
not *uploading a PDF and waiting for a pipeline*. Upload is step two.

That is also the strategic demo. ENTERPRISE_PLAN Part 0.2: *"shipping a working pre-built ontology is
the proof that you are software, not consulting."* The onboarding screen is where that proof lands or
is lost.

---

## 3. The three screens that are the product

### 3.1 Ontology editor

**Prior art**

| Tool | Approach | Source |
|---|---|---|
| **Zep** (closest competitor) | **Code only.** `client.graph.set_ontology()` with Pydantic/TS/Go models; ≤10 fields per model; reserved attribute names (`uuid`, `name`, `summary`, …); `strict_ontology: true` drops non-conforming entities; type counts capped by plan. Console shows a read-only "View Customization" dialog (custom ontology / custom instructions / summary instructions tabs) on graph, user and project settings pages, added [2026-06-10](https://help.getzep.com/changelog/2026/6/10). **No versioning documented — `set_ontology` overwrites previous definitions.** | [customizing-graph-structure](https://help.getzep.com/customizing-graph-structure) |
| **Palantir Foundry Ontology Manager** | Form-based editor (Object types / Link types / Properties in a left sidebar, property editor panel on the right); top bar with search, create, and a **branch selector**. Changes are developed on a branch and an **"ontology proposal" is explicitly analogous to a pull request** — reviewed and approved before merging to main, with per-resource conflict resolution ("Use Main branch changes" / "Keep current branch changes"). | [Ontology Manager overview](https://www.palantir.com/docs/foundry/ontology-manager/overview), [review ontology proposals](https://www.palantir.com/docs/foundry/ontologies/review-ontology-proposals) |
| **Stardog Designer + Voicebox** | Dual **List view / Graph view** of the data model; List view has tabs for Classes, Relationships, Attributes. Voicebox is an LLM agent that generates ontology elements from a natural-language description of the use case. | [Designer](https://docs.stardog.com/stardog-applications/designer/), [guided ontology creation](https://docs.stardog.com/voicebox/guided-ontology-creation-and-mapping/) |
| **TopBraid EDG** | Form-based governance tool; EDG Diagram panel (7.2+) shows class boxes listing properties, value ranges and value counts. Strength is audit trails, permissions, validation — not authoring speed. | [visual exploration with EDG](https://www.topquadrant.com/resources/visual-exploration-of-ontologies-with-topbraid-edg/) |
| **Neo4j** | No first-class ontology editor; the data model is a by-product of the import tool and of Explore "Perspectives". | [Aura visual tour](https://neo4j.com/docs/aura/visual-tour/) |
| **WhyHow.AI** | Knowledge Graph Studio was **API-first with an SDK**, schema-constrained graphs, rule-based entity resolution, MongoDB-backed. The hosted studio UI could not be verified — `web.archive.org` is not fetchable from this environment. **[UNVERIFIED]** | [GitHub](https://github.com/whyhow-ai/knowledge-graph-studio) |

**What good looks like**

The market splits cleanly: either the ontology is a code artifact with a read-only viewer (Zep), or a
governed form-based editor with branch/proposal semantics (Palantir, TopBraid). Our rule 5 —
*ontologies are immutable; editing publishes a new version* — matches Palantir's model exactly, and
Palantir has already proven the metaphor that makes immutability legible: **a draft is a branch,
publishing is a merge, and the diff is the review artifact.**

Concrete mechanics:

1. **Three surfaces over one artifact.** A form editor (type name, description, properties with types
   and cardinality, allowed `(subject_type, predicate, object_type)` triples); a YAML/JSON view that
   round-trips; an import path (start from the contracts pack, or from an existing schema). The YAML
   view is what makes the ontology diffable and what the SDK writes.
2. **Version selector in the chrome, not on the page.** Like Neon's branch picker:
   `v3 (published)` / `v4 (draft)`. Every other screen — explorer, review queue, extraction runs —
   displays which ontology version it is reading.
3. **Publish is a reviewed diff.** "Publish v4" shows added/removed/changed against v3, warns which
   existing facts become non-conformant, and states plainly that v3 stays queryable forever.
   Immutability is a *feature to advertise in the UI*, not a constraint to hide.
4. **Validation at authoring time, not extraction time.** The pipeline validates triple legality
   after decoding (Stage 3); the editor should surface the same rules as authoring constraints, so
   illegal triples are unrepresentable.
5. **Strictness is a per-version setting.** Zep's `strict_ontology` flag is the right idea: a toggle
   deciding whether off-ontology entities are dropped or kept generic. Record it on the version.
6. **An LLM assist is now expected** (Stardog Voicebox, Neon's Generate SQL): "describe your domain →
   draft an ontology", which the user then edits. Haiku-tier and cheap, and it removes the blank-page
   problem that is the real reason ontology editors go unused.

### 3.2 Graph explorer

**Prior art**

- **Neo4j Bloom / Aura Explore** — the search bar is the primary control: **search phrases** are named
  aliases for pre-defined graph queries, saved inside a **Perspective**. Expansion happens from a
  node's right-click menu or from the **Inspector** panel. Hard limit: **10,000 records processed per
  visualization query** unless the query sets a lower one, explicitly to stop the app hanging.
  ([scene interactions](https://neo4j.com/docs/aura/explore/explore-visual-tour/scene-interactions/),
  [search bar](https://neo4j.com/docs/aura/explore/explore-visual-tour/search-bar/),
  [search phrases](https://neo4j.com/docs/aura/explore/explore-features/search-phrases-advanced/))
- **Linkurious Enterprise** — search → expand → filter, with filters in a right-hand **drawer** (moved
  out of the top bar to free vertical space and allow filtering side-by-side with the graph);
  multi-select shows a searchable/sortable property table that expands full-screen; saved and shared
  visualizations in team spaces; date/time filter conditions built in the UI; an **audit trail of all
  read and write operations**. ([user manual](https://doc.linkurious.com/user-manual/latest/search/),
  [4.2 release](https://linkurious.com/blog/linkurious-enterprise-4-2/))
- **Graphistry** — WebGL renders up to ~8M nodes+edges; *most client GPUs are smooth at 100K–2M*.
  Server-side GPU layout and filtering for iterative exploration.
  ([Graphistry GPU](https://www.graphistry.com/gpu), [pygraphistry](https://github.com/graphistry/pygraphistry))

**What good looks like**

The consistent answer across all three: **you never render the graph, you render a query result.**
Neo4j's 10k cap and Graphistry's 100K–2M practical ceiling bracket the honest numbers. reactflow —
already installed — is a DOM/SVG renderer and degrades far earlier than either; budget a **few hundred
nodes on screen**, and design the interaction so the user never notices that limit.

Concrete mechanics:

1. **Search-then-expand is the only entry.** Opening the explorer shows a search box and zero nodes.
   Seed by entity search or a saved view. Never "load the graph".
2. **Expand is explicit, incremental and capped.** Node click → Inspector panel listing neighbours
   grouped by edge type with counts → "expand 12 of 340". A node with 340 neighbours expands into a
   *collapsed group*, not 340 nodes.
3. **Filters in a right drawer** (Linkurious): entity type, edge type, confidence, and — ours
   specifically — **valid-time and transaction-time sliders**. Bi-temporal correctness is
   differentiator #2 and the explorer is the only place it is visible. "Show the graph as it was
   believed on 2026-03-01" is the screenshot that sells this product.
4. **Provenance on click is mandatory.** Rule 1 gives every fact a `chunk_id` and a character span.
   Selecting an edge must show the asserting documents, the verbatim chunk with the span highlighted,
   the ontology version, and the assertion count (rule 4: how many documents would have to be deleted
   for this fact to die). No competitor in this list can do this. Highest-value pixel on the screen.
5. **Saved views**, named and shareable, with the query serialized in the URL — Neo4j's Perspectives,
   Linkurious' team spaces.
6. **Golden Record vs. Raw Entity toggle** — show the projection or the underlying mentions. This is
   where the explorer hands off to the review queue.

### 3.3 Entity-resolution review queue

The rarest screen, and the clearest differentiator (Part 0.1 #1 and #3). Prior art is in data-quality
and MDM tooling, not developer consoles.

| Tool | Mechanics worth stealing |
|---|---|
| **Splink** ([cluster studio](https://moj-analytical-services.github.io/splink/charts/cluster_studio_dashboard.html), [waterfall chart](https://moj-analytical-services.github.io/splink/charts/waterfall_chart.html)) | The **waterfall chart** is the best explanation device in the field: each comparison feature contributes a bar of match weight summing to a total, with match probability on a log-scale right axis. Cluster Studio samples clusters for spot-checking and lets you interrogate links between member records; self-contained offline HTML. |
| **Senzing** ([explainability](https://senzing.com/explainability/)) | **Why / why-not / how.** Three distinct questions: why these records matched, why a candidate did *not* match, and how the entity evolved over time. The "why not" view is the one everyone omits and reviewers most need. |
| **Zingg** ([active learning](https://www.zingg.ai/post/entity-resolution-at-scale-part-4-thresholds-active-learning)) | Five phases: findTrainingData → label → train → match → link. The interactive labeller presents *pairs near the decision boundary* — "random sampling rarely surfaces these efficiently". Queue ordering is an active-learning problem, not a confidence sort. |
| **OpenRefine** ([cell editing / clustering](https://openrefine.org/docs/manual/cellediting)) | Cluster-level, not pair-level: a table of clusters, a "Merge?" checkbox per cluster, an editable **New Cell Value** field, and two commit actions — **Merge Selected & Re-Cluster** and **Merge Selected & Close**. Histograms on the right filter clusters by size/length; clusters exportable as JSON. |
| **Reltio** ([bulk match review](https://docs.reltio.com/en/applications/hub/bulk-match-review-at-a-glance), [review potential matches](https://docs.reltio.com/en/objectives/resolve-potential-matches/potential-matching-at-a-glance/potential-matching-operation/review-potential-matches-overview), [merge matched data](https://docs.reltio.com/en/objectives/resolve-potential-matches/potential-matching-at-a-glance/potential-matching-reference/merge-matched-data)) | **Up to 5 profiles side by side.** Bulk: filter potential matches, multi-select, mark merge / not-a-match in one action. Unique URIs are assigned *before* merging specifically so records can be **unmerged later**; automatic unmerge when rules or data change. |
| **LangSmith annotation queues** ([docs](https://docs.langchain.com/langsmith/annotation-queues)) | The developer-console form of this. One item at a time; left panel with **Needs Review / Needs Others' Review / Completed**; pairwise mode with hotkeys **A / B / E** and Enter to advance; configurable rubric feedback keys; multiple required reviewers who cannot see each other's feedback but share comments; **reservations** that lock an item for a duration and auto-release; **Requeue** moves the item to the end of *your* queue; reviewer notes. |
| **Label Studio** ([hotkeys](https://labelstud.io/guide/hotkeys)) | Every action is a remappable hotkey (`EDITOR_KEYMAP` env var, `keymap.json`). Serious review tooling assumes the hands never leave the keyboard. |

**What good looks like**

1. **Queue, one decision at a time, keyboard-driven.** `J`/`K` move, `M` merge, `N` not-a-match,
   `S` skip/requeue, `U` undo, `?` for the shortcut sheet. Copy LangSmith's three-state left panel.
2. **Side-by-side candidate cards, up to five** (Reltio), each showing Golden Record fields, source
   documents, and the differing attributes highlighted.
3. **Show the evidence, not the score.** A Splink-style waterfall of contributing signals — normalized
   name, phonetic, trigram, vector similarity, shared neighbours, Adamic-Adar — summing to a match
   weight, probability alongside. A bare "0.87" is not reviewable.
4. **The vocabulary match is the headline.** Our differentiator is resolution against LEI/CIK, not
   fuzzy dedup. The card's top line should read *"Both resolve to LEI 549300…"*, which converts most
   decisions from a judgement into a confirmation. Where there is no vocabulary hit, say so loudly —
   that is the band where human attention is worth paying for.
5. **Why-not, alongside why** (Senzing). When a reviewer asks "should these have merged?", the system
   must answer with the specific signal that blocked it.
6. **Bulk actions on a filtered slice** (Reltio, OpenRefine): filter to "same LEI, confidence > 0.9",
   select all, merge. Real reviewers process thousands of pairs; one-at-a-time alone is a toy.
7. **Undo is architecturally free here and must be visible.** Rule 3: merging inserts a decision,
   unmerging retracts one. Show the decision log as a first-class tab — who decided, when, on what
   evidence, under which model and ontology version — and a permanent "Unmerge" on every Golden
   Record. Reltio had to engineer pre-merge URIs to make unmerge possible; we get it from the schema.
   Advertise it.
8. **Queue ordering is active learning** (Zingg): surface pairs near the decision boundary, not the
   highest-confidence ones. Record every human decision as outranking the model permanently (rule 3),
   which turns the queue into a training signal rather than a chore.

---

## 4. Docs-as-product

| Artifact | Status in 2026 | Evidence |
|---|---|---|
| **OpenAPI spec, published and downloadable** | Table stakes | Neon publishes a full [API reference](https://neon.com/docs/reference/api-reference) |
| **Typed SDKs, ≥2 languages (Python + TS)** | Table stakes | Weaviate ships Python, JS/TS, Go, Java, C# |
| **CLI** | Table stakes | Neon's CLI gained an `api` command in 2026 so agents can call any route without being handed raw keys; Clerk's whole quickstart is `npx clerk@latest init`; Modal's is `modal setup` |
| **Copy-paste-runnable samples with a working key** | Table stakes, rarely done well | Stripe's sample test key in every snippet |
| **`llms.txt` / `llms-full.txt`** | **Table stakes as of 2026** | Pinecone publishes [docs.pinecone.io/llms.txt](https://docs.pinecone.io/llms.txt); Discord's May 2026 portal revamp shipped MCP server + llms.txt + copy-as-markdown together |
| **MCP server over the API and the docs** | **Table stakes as of 2026** | as above; MCP passed 1,000 community servers within six months of its late-2024 introduction |
| **A coding-agent plugin / skill** | Emerging — Pinecone made it the *default* path | Pinecone's quickstart recommends `claude plugin install pinecone` then `/pinecone:quickstart` |
| **Free tier or sandbox that does not expire** | Table stakes | Weaviate "free-forever" sandbox; Modal $5 on signup, $30/mo with a card |
| **Example apps in a public repo** | Table stakes | universal |
| **Dated changelog** | Table stakes | Neon and Zep both publish dated changelogs |

The 2026 headline: **documentation has two audiences and the second one is a coding agent.** Pinecone's
recommended quickstart is not prose, it is a plugin invocation. Docs an agent can read (`llms.txt`),
call (MCP) and execute (CLI with a scoped token) *are* the onboarding path; the human-readable page is
the fallback. For us this is a large, cheap advantage: an MCP server exposing `ingest`, `query`,
`get_provenance` and `review_merge` makes the product usable from inside the customer's own agent on
day one — which is exactly the buyer we are selling to.

---

## 5. Recommended information architecture

Priority key: **Now** = before the first external developer; **After first customer** = once someone is
paying or piloting; **Later** = when there is an enterprise buyer or a team larger than one.

| Screen | Purpose | Priority |
|---|---|---|
| **Landing page** | One sentence on the outcome, one runnable curl, one link to docs. No feature bento. | Now |
| **Onboarding / Get started** | Pre-seeded demo tenant, key visible, curl pre-filled with it, a first query returning an answer with citations. The single most important screen. | Now |
| **API keys** | Create / name / reveal-once / last-used / revoke, per project. | Now |
| **Documents** | Upload; per-document ingestion status (parse → chunk → contextualize → extract → resolve); failure reasons; delete, with the assertion-count cascade explained before confirming. | Now |
| **Graph explorer** | Search-then-expand, filters drawer, bi-temporal sliders, provenance-on-click. | Now |
| **Ontology** | Version list; form + YAML editor on a draft; publish-as-diff; version picker in the chrome. | Now |
| **Resolution review queue** | Keyboard-driven merge/unmerge with evidence, vocabulary match, decision log. | Now |
| **Usage** | Documents and tokens processed, cost to date, plan cap, per-tenant spend-cap status (Stage 2). | Now |
| **Query playground** | Run a retrieval query in-browser; show the assembled context and citations; "copy as curl" / "copy as Python". | Now |
| **Request log / run inspector** | One row per API call and per pipeline run; drill into the extraction for a chunk, with the ontology version and model ID it ran under. | After first customer |
| **Team / members / roles** | Invite; admin/member/viewer (Stage 5 RBAC). | After first customer |
| **Billing** | Plan, card, invoices (Stage 5, Stripe meters). | After first customer |
| **Controlled vocabularies** | Which vocabulary (LEI/CIK/MeSH) a tenant resolves against; coverage stats; unmatched entities. | After first customer |
| **Evaluations** | Gold set, graph-construction metrics, regression history (Stage 4). Internal tool first. | After first customer (internal) / Later (customer-facing) |
| **Audit log** | Append-only, exportable — required by the regulated buyer, not by the developer wedge. | Later |
| **Connectors** | S3 / GDrive / SharePoint sync. Only after the ingest API is proven and someone asks. | Later |
| **Chat** | See §8. | Later, or never as a product surface |
| **SSO / SCIM** | Buy WorkOS when the first ask arrives (plan Stage 5). | Later |

---

## 6. Recommended onboarding path

Target: **first successful API response in under 3 minutes, ≤4 steps, no prerequisites.**

1. **Landing page** shows a runnable curl against a public demo corpus using a **shared public demo
   key**, Stripe-style. Anonymous visitors get a real 200 with real citations before any account
   exists. Highest-leverage item in this document; costs a rate-limited endpoint and a fixture corpus.
2. **Sign up with GitHub/Google.** One click. No email-verification gate, no org-naming form.
3. **Land directly on Get Started**, in a tenant **already seeded** with the contracts demo corpus,
   ingested and resolved under the published contracts ontology pack — not an empty state. The screen
   shows:
   - the tenant's own API key, revealed once, already substituted into a curl block and a Python
     block, with a copy button;
   - a **Run it here** button that executes that exact request in-browser and renders the answer with
     its citations (Neon's "placeholder SQL, click Run" move);
   - three links, each one click to a live screen with real data in it: *see the graph this came from*
     → explorer; *see what was merged* → review queue; *see the rules* → ontology.
4. **Then, and only then, "upload your own document."** The empty-tenant path is step two of the
   product, because our pipeline's honest latency makes an upload-first onboarding a spinner-first
   onboarding.

Treated as part of onboarding rather than as docs work: `llms.txt`, an MCP server, a `semanticgraph`
CLI with `login` / `ingest` / `query`, and a coding-agent plugin whose install line sits at the top of
the quickstart.

**Deliberately excluded from onboarding:** choosing an ontology, creating a project, naming an
organization, connecting a vocabulary, inviting a team. Every one is a Resend-style
domain-verification prerequisite, and each costs measurable conversion.

---

## 7. Design system and accessibility baseline

**What modern dev consoles use** — Radix primitives for behaviour, shadcn/ui as the styling and
distribution layer on top, TanStack Table for dense data with row virtualization (~50k rows, ~30 in the
DOM) and column pinning, `cmdk` for the command palette, URL-serialized filter state for shareable
saved views ([shadcn data table](https://ui.shadcn.com/docs/components/base/data-table),
[openstatus reference build](https://data-table.openstatus.dev/),
[shadcn vs Radix](https://vercel.com/i/shadcn-vs-radix)). Radix supplies WAI-ARIA roles, keyboard
navigation and focus management by default; the shadcn default theme is stated to meet **WCAG 2.1 AA**
contrast — note that is 2.1, and **WCAG 2.2 AA** (target size, focus appearance, dragging alternatives)
is the current bar, which matters directly for the explorer's drag interactions and small node targets.

Three baseline commitments:

- **Every review-queue and explorer action needs a keyboard path and a visible focus ring.** WCAG 2.2
  2.4.11 (focus not obscured) is easy to violate with a sticky right drawer over a canvas.
- **The graph canvas needs a non-visual equivalent.** A node/edge *table* view of the same query
  result, with the same provenance, is both the accessibility answer and the answer for graphs too
  large to render. Build the table first; the canvas is the second view of it.
- **Dense tables, not cards.** Usage, documents, logs and the review queue are all tabular; the current
  dashboard's card-and-gradient treatment is the wrong form for all four.

**On `docs/design/dark-mode-guide.md`** — read in full. It is a generic, well-written CSS reference on
`color-scheme`, `light-dark()`, token pairs, `accent-color`, `scrollbar-color`, a toggle pattern
(system/light/dark, with an explicit recommendation *against* exposing all three states), fallbacks and
known browser issues. It is **technically consistent with what modern consoles do** — token pairs
redefined per scheme, `color-scheme` declared early to avoid FOUC, no hardcoded root scheme — and there
is nothing in it I would contradict.

But it is generic guidance, not this product's design system, and **the existing frontend follows none
of it.** The file is UTF-16-encoded, sits under `docs/design/` and is not cross-referenced from
`AGENTS.md`, which is most of the reason. Two gaps: it says nothing about (a) light mode in practice —
the app is dark-only with light-mode cards accidentally mixed in — and (b) data density, focus and
keyboard conventions, which are the parts that matter for a console. It should become the colour-token
chapter of a short design doc, not the whole of it.

---

## 8. Blunt assessment: what the current seven pages get wrong

I read `frontend/src/app/**` and `frontend/src/components/**`. The honest summary is that this is a
mockup produced by a code generator, not a product surface, and almost none of it should survive.

**1. It is two half-built apps wearing one name.** There are two separate navigation implementations.
`components/Sidebar.tsx` links to `/`, `/graph`, `/sources`, `/team`, `/settings` — **five routes, four
of which do not exist**. `app/dashboard/layout.tsx` defines a *second*, inline sidebar linking to
`/dashboard/projects` (**also nonexistent**), `/dashboard/explorer` and `/dashboard/connectors`.
Neither sidebar links to ontology, evaluations or chat — three of the seven pages. The board is not
wired to the game.

**2. Four of the seven pages are ten-line stubs.** `chat`, `evaluations`, `ontology` and `settings` are
each a heading and a sentence. The ontology page — one of the three screens that *is* the product —
reads in full: *"Define Nodes and Edges for the extraction pipeline."* Counting these as "seven pages
that already exist" overstates the position by roughly a factor of two.

**3. The dashboard is fabricated data in the wrong visual language.** Hardcoded `24,592` entities,
`1.2M` tokens, `450ms` latency, an invented `extractionData` series, and an activity feed naming
**"Gemini LLM"** — a provider this architecture does not use. It renders `bg-white` cards on a
`#0a0a0b` dark layout, i.e. white rectangles on black. The breadcrumb says **"Acme Corp"** and the
avatar **"JS"**, both hardcoded.

**4. The landing page sells a system that was explicitly superseded.** It advertises *"High-Speed
Celery Workers"* — Celery was replaced by Temporal in Part 1.3 — and *"Mathematically Verified LLM
pipelines"* with a fake JSON block reading `"verification": "100% Mathematically Proven"`. That is not
a defensible claim about an LLM extraction pipeline; it is the line that makes a technical buyer close
the tab. Meanwhile none of the four actual differentiators — controlled-vocabulary resolution,
bi-temporal correctness, human curation with provenance, multi-tenant isolation — appears anywhere.

**5. `AuthGuard` is a hardcoded lie.** `const currentUserRole = "Super Admin"; // Hardcoded for
mockup`. It renders an "Unauthorized" screen for roles it never receives. This is a component that
*looks* like a security control, in a codebase whose second irreversible rule is that tenant isolation
fails closed. Delete it rather than leave something auth-shaped that authorizes nothing.

**6. `GraphExplorer` hardcodes `http://localhost:8000/graph` and sends
`headers: { tenant_id: "tenant-123" }`.** Part 3 Stage 5 says explicitly: *"never the current unsigned
`X-Tenant-ID` header."* It fetches `/graph` with no query and no limit — load-the-whole-graph, the one
interaction every explorer in §3.2 exists to prevent — then applies `animated: true` and a neon cyan
`drop-shadow` to every edge, which will drop frames at a few hundred elements. There is no expand, no
search, no provenance panel. Its "Graph Controls" are two checkboxes wired to nothing.

**7. Nothing a developer needs on day one exists.** There is **no API keys screen, no usage screen, no
logs, no playground, no onboarding** — five of the seven table-stakes screens in §1.2 missing, in a
product whose chosen wedge is developers. The seven pages include two screens (`connectors`, `chat`)
that no console in the comparison set ships, and omit every screen all of them ship.

**On `chat` and `connectors` specifically.** They do not earn their place, and they cost more than they
look.

- **Chat** is the demo that makes this product indistinguishable from every RAG wrapper — and Part 0.3
  is explicit that a benchmark fight on generic RAG accuracy is lost. It also puts document text on a
  screen whose traffic ends up in logs and traces, against the telemetry convention. The legitimate
  need underneath it is *"show me an answer with citations"*, which is the **query playground**: one
  request, a visible assembled context, clickable provenance. Build the playground; delete chat.
- **Connectors** is integration surface area for a pipeline that has not yet processed a single
  document end to end on real infrastructure (Stage 1 is unticked). Every connector is an ongoing
  auth-and-rate-limit maintenance liability. It is a post-first-customer screen; until then the ingest
  API plus a CLI covers it.

**What I would do with the seven pages:** keep `explorer` and `ontology` as route names and rewrite
both against §3.1–3.2. Delete `chat`, `connectors`, `AuthGuard`, `components/Sidebar.tsx` and the
fabricated dashboard. Demote `evaluations` to an internal tool. Add onboarding, API keys, documents,
usage, playground, and the resolution review queue.

The review queue is the screen that does not exist anywhere in the current frontend, and is the one the
strategy says no hyperscaler will build. That — not the graph canvas — is the screen worth building
first.
