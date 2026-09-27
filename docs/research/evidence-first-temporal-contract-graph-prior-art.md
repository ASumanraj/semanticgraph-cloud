# Evidence-first temporal contract graph: prior art, history and use-case ranking

Research date: 2026-09-25. Written from two research passes (fact-check and prior art; history, events and use cases) plus reviewer spot-checks. Read `contract-ai-market-and-customer-one.md` first; this note extends it and corrects it in one place (section 9).

## Question

Is the combination of our four guarantees a new product category, and which graph-centred use case should a launch lead with?

1. Every extracted fact links to exact supporting text (chunk and character span).
2. Facts are queryable as of a past date (valid time and transaction time).
3. Entity merges are reversible logged decisions; a human decision outranks a model decision permanently.
4. Deleting a source removes only knowledge supported solely by it.

Two unverified market summaries, produced by another agent, prompted this. Their claims are checked in section 1.

## Labels

- **verified** — a primary source was opened and says it.
- **reviewer-verified** — additionally re-checked by the reviewer (listed in section 10).
- **fetch-summary** — primary source read through a fetch tool's summary; re-check a quote before publishing it.
- **index-only** — search-result text only, page not opened.
- **vendor claim** — the vendor's own page, not independently checked.
- **practitioner** — law-firm or consultant material.
- **hypothesis** — inference, not evidence.

"Not publicly documented" is the only permitted negative. It never means "does not exist".

## Summary

- Each guarantee has published prior art on its own. Bi-temporal validity, provenance, temporal graph updates, expiry radars, propose-then-approve with a decision log, and reference-counted deletion of derived artifacts are all documented.
- Within the searches in section 7, no publicly documented system combines all four over a contract corpus. That is an opportunity signal, not proof.
- Category history does not favour first movers. The first AI clause-extraction firms were acquired at modest prices; the largest outcomes came later (hypothesis, small sample).
- "Find every affected contract" events are real, but regulators often solved the largest ones by protocol or legislation. Current dated regimes (EU Data Act, DORA) still create per-contract work.
- The use cases where all four guarantees are load-bearing are regulatory-change remediation, the sub-processor/DPA graph, and amended credit agreements. None has proven buyer pull yet.
- Graphiti's `remove_episode` deletes an edge when its first asserting episode is removed, even if a later episode still asserts it. Reproduced on a pinned commit (section 1, row 1). It is one deletion path, not the whole product guarantee, so it is one case in a benchmark, not the benchmark.
- DORA Art. 30 clause-gap checking, including verbatim-verified quotes and human sign-off, is already sold (Vendorica; section 8). It cannot be a "first" claim or a standalone differentiator.

## 1. Fact-check of the pasted claims

| # | Claim | Verdict | Source and what it says |
|---|---|---|---|
| 1 | Graphiti (Zep): temporal facts, provenance, historical queries | **Partly confirmed** (code read, commit 47f6482, v0.30.2) | `EntityEdge` has `valid_at`/`invalid_at` (valid time), `created_at`/`expired_at` (transaction time) and `episodes: list[str]`. `SearchFilters` accepts date filters on all four timestamps; there is no dedicated as-of API. Provenance is episode-level; no span, offset or quote field exists in `graphiti_core`. No unmerge code (`add_episode` discards the duplicates list). `remove_episode` deletes an edge when `edge.episodes[0] == episode.uuid` (first asserter), and deletes a node only if `count(MENTIONS) == 1`. The MCP docstring says facts supported by other episodes are preserved, which the edge logic does not match. **Reviewer-verified** by reading (`graphiti.py:1824-1852`) **and reproduced** on the pinned commit with embedded Kuzu and no LLM calls (`artifacts/graphiti-remove-episode-repro.py`): with `edge.episodes = [doc1, doc2]`, removing doc1 deleted the fact (1 to 0) although doc2 still asserts it; removing doc2 kept the fact and left the deleted doc2's uuid in `edge.episodes`. Limits: the graph was built through Graphiti's own save methods, not through `add_episode` (which needs an LLM), so this shows what `remove_episode` does to such an edge, not how often real ingestion produces one. A public Graphiti issue reportedly describes a two-episode reproduction (reported by another reviewer, not checked here). One deletion path is not the whole product guarantee. The Zep paper (arXiv 2501.13956) itself calls its bi-temporal model "a novel advancement in LLM-based knowledge graph construction" and says new edges invalidate old ones through an LLM comparison that prioritises new information. |
| 2 | MDPI "Automated GDPR Contract Compliance Verification Using Knowledge Graphs" | **Confirmed** (doi 10.3390/info13100447; mdpi.com 403, read from the mdpi-res PDF) | Models expiry dates, clause states Invalid/Fulfilled/Pending/Violated derived from the current date, contract status, and automatic notifications. States are overwritten in place ("updated in the KGs"): no history, no provenance, no as-of query. |
| 3 | Violation Situation Pattern | **Confirmed** (arXiv 2606.03326, KM4LAW 2026, DiliTrust authors) | Persistent violation node with validity interval, five-state lifecycle, immutable transition nodes. Authors state immutability is application-layer only; evidence links are entity-level, not spans; no transaction time, reversal or deletion; evaluation on planted violations in a fixture graph. |
| 4 | SAGE and EvoGraph-R1 | **Confirmed**, with a name collision | SAGE arXiv 2605.12061 (agent memory graph, writer trained with GRPO); a different paper, arXiv 2605.30711, is also titled "SAGE". EvoGraph-R1 arXiv 2607.12764 (CVPR 2026): `GraphEdit` Insert/Update/Delete on a hypergraph; "Delete" lowers confidence. Both are silent agent rewrites with no human gate, audit or deletion semantics. |
| 5 | fida lab and OpenCLM | Both exist; **marketing-only** | fida lab (fidalab.io): features page states a knowledge graph, an Expiration Radar and obligations; use-cases page mentions MCP; no docs or API pages; home page no longer says "knowledge graph". OpenCLM (openclm.ai, AGPL per site): reminders, audit trail, version history; no graph, MCP or AI extraction in its docs; linked repo `nxglabs/openclm` returns 404. |
| 6 | Standards | **Confirmed as prior art**; none defines unmerge or deletion-by-support | PROV-O has `prov:Invalidation`, derivation and quotation, but no term for deletion, retraction or spans. OWL-Time (Candidate Recommendation Draft, 2022) covers intervals and durations, not valid time or recurrence. LegalRuleML 1.0 gives norms validity times and identifier-based links to text fragments down to word level; it covers norms, not extracted facts. |
| 7 | Bitemporal SQL | **Confirmed as standard, so not novel** | Kulkarni and Michels, SIGMOD Record 2012: SQL:2011 application-time and system-versioned tables, `AS OF`, a bitemporal example. In SQL:2011 a DELETE only closes the period, which conflicts with erasure. PostgreSQL 18 adds `WITHOUT OVERLAPS` and `PERIOD` but no system-versioned tables. |
| 8 | Luminance "context graphs" | **Confirmed** (vendor claim) | luminance.com/platform/technology: "Pre-computed legal knowledge and Context Graphs connect contracts, amendments and related documents, enabling users and AI agents to retrieve the right evidence faster and analyze transactions in context." No mechanism, API or benchmark. **Reviewer-verified.** |
| 9 | Icertis: obligations, relationships, performance, agents | **Confirmed** except "relationships" | icertis.com/products: "track every obligation, and prove outcomes"; "Agents execute + humans govern". No standalone relationships feature on that page. |
| 10 | Tamr and Quantexa: human decisions, reversal, provenance | **Partly** (Tamr); **not found** (Quantexa) | Tamr: uncertain cases go to human review; logs every match decision; with "Enable suggestions" a verified record may move if the model disagrees, only "Disable suggestions" locks it. No unmerge found. Quantexa: models "open and transparent… explainable"; nothing on overrides, unlinking, audit history; community docs returned 403. |
| 11 | FinregE | **Partly** (index-only) | finreg-e.com returned 403. Index text: knowledge graphs linking regulations, versions, policies and controls; "source-linked to the exact paragraph and versioned through every amendment". Read before quoting. |
| 12 | RAINavigator | **Contradicted** as stated | An open knowledge graph for regulated AI: use case → law → obligation → control → component → evidence. Control objectives and architecture components, not a firm's own internal controls. |
| 13 | "Proactive Context Graphs" | Exists; narrower than it sounds | arXiv 2607.07721, 2026-07-04: live graph plus delta detection and an LLM surfacing layer, on NetworkX; synthetic case studies, one of them contract lifecycle management. |
| 14 | "Policy-to-Knowledge" | A **repo, not a paper** | github.com/rrahimi-uci/policy-to-knowledge, MIT, 15-agent OpenAI pipeline; each rule keeps a `source_reference` chunk path; no evaluation, nothing on contracts or timestamps. |
| 15 | EvoKG | **Two unrelated works** | Park et al., WSDM 2022 (arXiv 2202.07648), temporal link prediction; Lin et al., arXiv 2509.15464, noise-tolerant KG evolution with validity intervals. Neither about contracts. |
| 16 | Neo4j contract GraphRAG | **Confirmed, no amendments** | Bratanič, 2025-05-05, on CUAD (~500 contracts): single-contract and cross-portfolio aggregate questions; 22-question benchmark, GPT-4o 0.82 answer satisfaction. Amendments, versions and temporal tracking not covered. |
| 17 | Google KG 2012; W3C PROV 2013 | **Confirmed** | Google blog 2012-05-16 (more than 500M objects); PROV-DM "W3C Recommendation 30 April 2013". |

## 2. Nearest neighbours against the four guarantees

Each row lists what the system documents and what is absent in what was read.

| System | Documents | Absent in what was read |
|---|---|---|
| Graphiti | Bi-temporal edges, episode provenance | Character spans, reversible merges, exact support counting on edges |
| post-graph-rag (arXiv 2608.24921, author Chandan Rajah, Sep 2026) | PostgreSQL-native; bi-temporal layer that supersedes earlier assertions (abstract, **reviewer-verified**); per-edge chunk provenance and "dormant entity" when the last mentioning document disappears (agent-reported, not confirmed in the abstract) | Character spans, reversible merges, human precedence, RLS (abstract does not mention them) |
| Agentic Unlearning (arXiv 2602.17692) | Dependency-closure unlearning that prunes isolated entities and logically invalidates shared artifacts (**reviewer-verified**); reference counting and tamper-evident audit log per the agent | Transactions, RLS, bitemporal semantics, human precedence; evaluated on medical QA agent memory |
| Quipu (arXiv 2608.16813) | Append-only bitemporal log; retract vs tombstone; approval gate bound to an evidence hash (fetch-summary) | Spans, merges, tenancy; SQLite backend |
| Talamus | `--as-of` queries, cited provenance, review-gated corrections (fetch-summary) | Deletion semantics, merges, tenancy |
| RE-call | Postgres, supersession, "source erasure", provenance (fetch-summary) | Spans, valid-time queries, merges; PolyForm Noncommercial licence |
| Violation Situation Pattern | See section 1, row 3 | Same |
| Vendorica (DORA Art. 30 product page, raw HTML read 2026-09-27, **reviewer-verified**) | AI clause analysis that "only keeps quotes it can verify verbatim against the text", each finding with "the quoted excerpt and its location"; "Reviewers confirm or override, sign-off locks the position of record"; an org-wide gap register "where remediation is tracked to closure". Contract text is "never stored, only its SHA-256 fingerprint" | Character-offset spans, as-of queries and historical assessments (none on the pages read; a reviewer reports "historical assessments", not found by me), amendments, entity resolution, deletion semantics (it does not retain the text) |
| Tamr / Senzing / Palantir | Human review, curation, action proposals and reverts | Documented human-over-model precedence that survives reprocessing (Tamr's is a setting) |

## 3. Propose-then-approve, erasure, regulatory pull, moats

**Propose-then-approve** is documented, mostly outside contract graphs (fetch-summary unless noted). Palantir AIP Logic: agent proposals "require a review", an agent decision log, "when you accept a proposal, the Action will be automatically executed". Palantir action reverts undo object edits but not side effects, and are blocked once a later edit exists. Senzing: human forcing via `TRUSTED_ID` attributes; the built-in feature does not persist across reprocessing; deleting a record makes the system "unlearn" its consequences (vendor claim). Neo4j Agent Memory: `SAME_AS` links with pending/confirmed/rejected status; merge reversal not documented. Not publicly documented in what was read: a human decision that outranks the model permanently across model upgrades, with reversible merges, over a contract corpus.

**Erasure of derived data.** GDPR Art. 17 (verified, Publications Office text): 17(1) erasure "without undue delay"; 17(2) reasonable steps to inform controllers of "any links to, or copy or replication of" the data; 17(3)(b) and (e) exempt processing needed for a legal obligation or legal claims, which matters because contracts are often legally retained. Art. 19 (verified): communicate erasure to recipients "unless this proves impossible or involves disproportionate effort". Recital 26 (verified): "means reasonably likely to be used, such as singling out". EDPB Opinion 28/2024 (verified, PDF): models trained on personal data "cannot, in all cases, be considered anonymous"; the word "embedding" does not appear; nothing on knowledge graphs or summaries. Assertion-counted deletion as a technique has prior art (truth maintenance, view maintenance by counting derivations, Agentic Unlearning); as a product guarantee over a contract corpus it is not publicly documented.

**Regulatory pull is weaker than earlier notes implied.** AI Act (verified, EUR-Lex): Art. 12 logging and Art. 13 transparency bind high-risk systems; Annex III items 1-7 do not list commercial contract analytics (nearest: 4(b), employment terminations). Applicability dates were not checked against any delay. DORA (verified, EUR-Lex): Art. 28(3) register of "all contractual arrangements"; Art. 30(2)(a)-(i) mandatory clauses, including (h) "termination rights and related minimum notice periods". `dora-register-field-source.md` already classifies the register fields. EDPB Opinion 22/2024 (verified): controllers "should have the information on the identity of all processors, sub-processors etc. readily available at all times".

**Moats.** Only two items have primary evidence, neither about contract graphs: Tamr's persistent cluster IDs and per-publish snapshots, and Palantir's recommended writeback of human-verified decisions. Accumulated human decisions, per-ontology gold sets, ontology packs, PROV-O exports and switching cost are hypotheses. Two are testable in interviews: whether decisions are exportable, and whether a buyer would re-adjudicate them after switching.

## 4. History

Rows without "verified" rest on search summaries or secondary sources.

| Date | Event | Label |
|---|---|---|
| 1969 | Fellegi-Sunter probabilistic record linkage | listing only |
| ~1999 | Emptoris founded; CLM emerges late 1990s. First obligation management: not established | secondary |
| 2001 | Berners-Lee, Hendler, Lassila, "The Semantic Web" | listing verified |
| 2011 | Kira founded (as DiligenceEngine); eBrevia founded | verified (LawSites 2018, ebrevia.com) |
| 2012-05-16 | Google Knowledge Graph | verified |
| 2013 | LexPredict and Tamr founded; W3C PROV Recommendations 2013-04-30 | PROV verified |
| 2015-2016 | Luminance (2015) and Quantexa (2016) founded | secondary |
| 2018 | Kira $50M Series A; Elevate buys LexPredict; DFIN buys eBrevia (about $19.5M) | Kira verified; rest secondary |
| 2020-02 | DocuSign agrees to buy Seal Software for $188M | index-only |
| 2020-10 to 2021-01 | ISDA IBOR Fallbacks Protocol: more than 12,000 entities in nearly 80 jurisdictions by 2021-01-25 | verified (isda.org) |
| 2021-08 | Litera acquires Kira; Zuva spun out | prior notes |
| 2024-02 / 2024-04 | Microsoft GraphRAG blog, then arXiv 2404.16130 | verified |
| 2025-01-20 | Zep paper: bi-temporal model | verified |
| 2025-02-18 | Luminance $75M Series C, $165M total | verified (TechCrunch) |
| 2025-12-08 | Agiloft AI obligation management | verified |
| 2026 | "Context graph" wave: Luminance page, arXiv 2607.07721, a Foundation Capital essay (date uncertain) | mixed |

**Pattern (hypothesis; small n, survivorship bias).** The first AI clause-extraction firms exited by acquisition at modest prices; the largest reported outcomes (Harvey, Icertis) came later. Consistent with "technology shift plus distribution", not with first-mover advantage. It does not show that execution alone wins.

## 5. "Find every affected contract" events

| Event | Documented scale | Approach | Graph, span or as-of? |
|---|---|---|---|
| LIBOR | ARRC closing report: about $200T of contracts, "hundreds of thousands" affected; ~95% of surveyed lenders had identified all exposure by Oct 2022, ~14% expected to be largely done by year-end. Per-firm counts and cost: not publicly documented | ISDA protocol, then US legislation and a Fed rule for tough legacy contracts. Extraction: ING with Eigen, about 150 loan agreements (vendor-adjacent) | None documented; the decisive move was legal |
| EU SCCs | Old SCCs valid until 27 Dec 2022 for contracts concluded before 27 Sep 2021 (Commission Q&A). No contract count | Contract-by-contract | "Concluded before X, replace if modified" is an as-of-plus-amendment test |
| Brexit | About £26T later £29T of uncleared derivatives at risk (index-only) | Legislation and regulator coordination | None found |
| DORA (17 Jan 2025) | No regulator aggregate. 3rdRisk case study: 220 contracts, critical ones amended in five months (vendor claim) | Vendorica, Regulativ.ai, Luxgap, 3rdRisk sell clause-gap checks | Luxgap claims timestamped reports; amendment handling not stated |
| EU Data Act (12 Sep 2025) | Chapter IV applies to contracts concluded after 12 Sep 2025, and from 12 Sep 2027 to earlier indefinite contracts or those expiring at least 10 years after 11 Jan 2024 (regulation text). No counts | Commission model terms; vendor checklists (index-only) | Whether an amendment counts as a new conclusion: hypothesis, not researched |
| COVID force majeure | 171 public contracts, 18% with pandemic language (DFIN, vendor-published) | eBrevia and others | None |
| GDPR 2018, Russia sanctions | Scale not publicly documented | n/a | n/a |

The event class is real and recurring, but per-event scale is mostly unpublished, and regulators often solved the largest events by protocol or statute. That weakens the argument that the market would have bought per-contract impact tooling for those events.

## 6. Use-case landscape

Use cases 1-9 were assigned; 10-11 were added and not researched. "Guarantees" lists which of span / as-of / reversible merge / delete-by-assertion are load-bearing.

| # | Use case | Already served (own pages) | Guarantees | Copy risk | Launchable |
|---|---|---|---|---|---|
| 1 | Amendment change-impact | Ironclad rollup; LinkSquares Restated Agreements; Luminance and Pramata families (Pramata index-only) | span, as-of | High | Medium |
| 2 | Regulatory-change remediation | Four DORA gap tools; Fabasoft | span, as-of | Medium | High for a pilot |
| 3 | Vendor/sub-processor graph (Art. 28) | OneTrust (vendor claim) | All four | Medium-high | Medium (small budgets) |
| 4 | M&A diligence | Kira/Litera, Luminance, eBrevia, Harvey, Zuva | Mostly nice-to-have | High | Low |
| 5 | Loan covenant tracking | Aloan, CovenAce, nCino, Abrigo (index-only) | span, as-of, amendments | Medium | Low-medium |
| 6 | ISDA/CSA | ISDA CDM, ISDA Create | All | Standard-setter is the incumbent | Low |
| 7 | Reinsurance treaties | Nomad Data, V7, others (index-only) | Unknown | Unknown | Low |
| 8 | Lease abstraction | Visual Lease, LeaseQuery, Nakisa (index-only) | as-of | High | Low |
| 9 | Obligation and renewal operations | Icertis, Agiloft, Sirion, Pramata | Nice-to-have | Very high | Low |
| 10 | Counterparty-event impact (rename, acquisition, sanctions ownership) | Screening vendors; not researched | merge, as-of | Unknown | Unknown |
| 11 | As-of audit evidence for disputes and revenue-contract modifications | Not researched | span, as-of | Unknown | Unknown |

**Ranking** (all buyer pull is unproven; ranked by load-bearing guarantees, event-driven budget and launchability without a customer): 2 (with 1 as its engine), 3, 5, 10, 11, 4, 8, 6, 7, 9.

## 7. Negative-search log

All queries 2026-09-25 by web search; no direct GitHub code search or Google Patents search was run.

Prior-art pass: "bitemporal + KG + char span + reversible merge + decision log + deletion cascade + github"; "patents.google.com + assertion + source document + remaining assertions + valid/transaction time"; "arXiv contract KG + provenance + offsets + temporal validity + ER + audit + deletion"; "human decision outranks model decision + unmerge + golden record"; "github KG memory + span + bitemporal + retract + postgres RLS"; "patent unmerge + human override + provenance + deletion"; vendor-doc queries for Senzing, Tamr and Palantir; GDPR, EDPB and unlearning queries.

Use-case pass: "contract amendments knowledge graph temporal as of date … change impact arXiv"; "amendment contracts LLM extraction amended and restated … temporal contract graph benchmark"; "legislation.gov.uk point in time versions"; "contract change impact analysis amendment … master agreement order forms"; "Pramata contract hierarchy effective terms"; "Sirion OR Agiloft OR Evisort amendment consolidated / as amended"; "DORA contract remediation AI … Article 30 gap analysis"; "Data Act … repapering existing contracts 2027".

Nearest matches for an amendment change-impact system with spans and as-of history: SAT-Graph API (arXiv 2510.06002, legislation, a specification not a benchmark); a contract-amendment link classifier (arXiv 2106.14619, 1,124 pairs, F1 91%); Temporal Dependency Graphs (arXiv 2608.15270, deadlines over judgments); ContraVis (arXiv 2609.27014, single-contract contradiction review); legislation.gov.uk point-in-time versions (index-only). Google Patents pages for resolver-tree unmerge (US 11960470 and 12210510) appeared as snippets and were not opened.

**Verdict:** not publicly documented, as of 2026-09-25, as a complete combination. Not searched: proprietary bank tooling, Palantir-style deployments, non-English sources, Bing or Scholar directly.

## 8. Do not claim as first

| Claim | Prior art |
|---|---|
| Knowledge graphs | Google 2012; Semantic Web 2001 |
| Provenance standard | W3C PROV 2013 |
| Bi-temporal validity in an LLM-built graph | Zep/Graphiti (2025); post-graph-rag, Quipu, Talamus (2026) |
| Temporal KG evolution | EvoKG (arXiv 2509.15464) |
| GraphRAG over contracts | Neo4j, May 2025 |
| Source-linked rules in a graph | Policy-to-Knowledge repo; FinregE (index-only) |
| Amendment rollup with revert | Ironclad |
| Amendment linking, contract families | LinkSquares; Pramata (index-only) |
| Context graphs | Luminance; arXiv 2607.07721 |
| Propose-then-approve with a decision log | Palantir; Quipu; Talamus |
| Reference-counted deletion of derived artifacts | Agentic Unlearning; truth maintenance; view maintenance |
| Persistent violation and lifecycle nodes | Violation Situation Pattern |
| Recurrence rules | RFC 5545; ODRL |
| Rule-to-text linking | LegalRuleML |
| Point-in-time consolidated law | legislation.gov.uk |
| Human-in-the-loop entity resolution with audit history | Tamr |
| DORA Art. 30 clause-gap reporting, including verbatim-verified quotes, human sign-off and a remediation register | Vendorica (**reviewer-verified** on raw HTML: "maps the Article 30 provisions to each ICT arrangement and shows which contracts are missing which clause"; verbatim-verified quotes with location; reviewer sign-off; remediation register), Luxgap, Regulativ.ai, 3rdRisk. A second reviewer also names Governys, Leah, ComplyOne and Venvera; **not confirmed here** (Governys not found by search; ComplyOne surfaced only guide pages; Leah and Venvera not checked) |
| "We verify the quote" or "we track contract gaps" as a differentiator on their own | Vendorica, above |
| First or fastest AI contract review | Kira 2011, eBrevia 2011, LexPredict 2013 |

## 9. Corrections to earlier notes

`dora-register-field-source.md` says no register tool reports which Article 30 clauses are missing from a contract. At least one vendor now does so on its own product page (Vendorica, reviewer-verified from raw HTML), with verbatim-verified quotes, reviewer sign-off and a remediation register; three more (Luxgap, Regulativ.ai, 3rdRisk) claim clause-gap checks, and a second reviewer names four others that I could not confirm. These are vendor claims: live products, accuracy and customers were not checked. The "clause-gap report" and "verified quote" candidates are contested prior art, not open space, and DORA clause-gap analysis must not be presented as a first or unique claim. It remains a workflow worth testing, most plausibly as one part of a broader vendor-and-contract evidence lifecycle.

`docs/architecture/ENTERPRISE_PLAN.md` Part 0.2 calls the developer-platform wedge "chosen" and "unserved". T-907 and this note say the wedge and the contract workflow are unresolved hypotheses (T-907: the builder segment has the weakest business evidence). Treat both as hypotheses under test. (The plan's cost figure and GLiNER wording were already corrected on 2026-09-21; only the wedge wording is stale.)

## 10. Reviewer spot-checks and evidence gaps

**Reviewer-verified:** Graphiti `remove_episode` (`edge.episodes[0]`); the abstracts of arXiv 2602.17692 and 2608.24921; the Luminance and Vendorica quotes above. Everything else carries the source labels given, and rests on the research passes.

**Gaps.** mdpi.com, finreg-e.com, pramata.com, Quantexa community, the Eigen case study, BusinessWire, CNBC, the Federal Register and some Luminance URLs returned 403 or 404; EUR-Lex challenged some fetches and texts came from alternate hosts. The Zenodo artifact for the Violation Situation Pattern, FOLIO, LKIF, ContraxSuite, OpenContracts and RE-call's provenance document were not opened. The Snodgrass PDF was unreadable. EDPB guidance beyond Opinion 28/2024 and SEC/PCAOB expectations were not read. Several vendor and event rows are index-only. A Skadden "12% more risks" figure and a "9,164 contracts" COVID figure could not be traced and were discarded. Not researched: sanctions scale, reinsurance, ISDA/CSA depth, revenue-contract modifications, Quantexa's technical docs. The Foundation Capital essay's date is uncertain. arXiv identifiers in the 2606-2609 range were taken from the research passes; two were re-fetched, the rest were not.

## 11. What to do with this

**Not publicly documented, therefore open:** all four guarantees together; span-level evidence as queryable data; a permanent human-over-model rule across model upgrades; a deletion cascade reaching eval fixtures in one transaction under FORCE RLS; this combination applied to contract portfolios.

**Product hypothesis (to test, not settled).** The distinction worth testing is the end-to-end guarantee across evidence, history, identity decisions, deletion and impact: when a record changes, show the new supported state, what downstream items may be affected, and who approved what. No single piece of it (clause gaps, quote verification, temporal facts) is defensible alone. It needs a buyer and a benchmark to show it matters. T-907's conclusion is limited to the competitors and public interfaces it examined.

**Cheapest experiments** (buyer pull, one per candidate; pass criteria are proposals). In every interview ask about an actual recent workflow: what source changed, how it was handled today, which decisions it affected, who owns the budget, and whether they would pilot. Do not ask whether they like the graph idea.

1. *Regulatory remediation:* offer three EU data-practice law firms a one-week Data Act Chapter IV test on 30 redacted contracts with span-cited results. Pass: at least three send real contracts and one names a budget owner within 30 days.
2. *Sub-processor graph:* ask 10 DPOs for their sub-processor lists and three DPAs and answer "who changed since last quarter". Pass: at least three supply data and one asks for a recurring feed.
3. *Covenants:* ask eight credit-ops people for one anonymised amended-and-restated credit agreement and its compliance-certificate history. Pass: our tool reproduces the covenant level as of the test date with the superseding span, and the reviewer agrees.
4. *Builders (from T-907):* give a builder team the span and decision-log API on 20 contracts. Pass: they rewire in 30 days.

**Public benchmark.** A neutral, event-level benchmark on public contracts, comparing implementations fairly and publishing the harness. Event types: point-in-time queries; amendments and supersession; a fact supported by two sources and deleting one; entity-resolution corrections (merge, unmerge, model upgrade); downstream impact of a change. The Graphiti `remove_episode` behaviour is one case among these, not the benchmark; a benchmark built around one known edge case would not be credible. Hypothesis to check before relying on it: amended credit agreements filed publicly on SEC EDGAR may serve as the corpus.

**Defensible narrow claim,** valid only while the searches in section 7 still hold and only after the benchmark exists:

> As of 2026-09-25, we found no publicly documented product that, for a portfolio of contracts, lists each affected agreement for a given amendment, cites the superseding text by character span, re-runs the answer as of a past date, and lets a human reverse an entity merge.

**Positioning (claims the evidence supports):** SemanticGraph Cloud is a Postgres-based contract knowledge substrate. Each extracted fact carries the chunk and character span it came from. Facts are queryable as of a past date. Entity merges are recorded, reversible decisions in which human decisions outrank model decisions. Deleting a source document removes only what that document alone supported. Other systems document parts of this. We are not aware of a publicly documented system that combines all four over a contract corpus.

**Architecture note worth keeping (no code implied).** Keep three layers apart: the authoritative evidence record (immutable assertions, sources, decisions), an operational projection (deadlines, due dates, impacts, lifecycle events), and an agent working state (plans, proposals). An agent may propose merges, supersessions or actions; only a deterministic rule or an authenticated human changes authoritative state. A date passing closes a fact's `valid_to` and appends a lifecycle event; it never rewrites the fact. Recurring obligations store a recurrence rule and derive occurrences rather than materialising future nodes. This matches the existing decision log (Rule 3) and bi-temporal schema, and it stays a design note until an experiment shows buyer pull.
