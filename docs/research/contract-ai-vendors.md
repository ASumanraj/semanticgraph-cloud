# Contract-AI vendors: what they already do, from their own documentation

**Ticket** T-907 (vendor pass) · **Date** 2026-09-21 · **Status** complete

Companion to [`pipeline-comparison-and-acceptance.md`](pipeline-comparison-and-acceptance.md), which
compared GraphRAG *frameworks*. This compares the products a contracts buyer actually evaluates.
Same discipline, different market: capabilities come from vendor documentation, help centres, API
references, security pages and release notes. Press, analyst tiles and review aggregators are not
used as the source of a capability.

Every claim carries one label:

- **[VERIFIED]** — a first-party document states it, URL cited, page read.
- **[VENDOR CLAIM]** — first-party, but a marketing page with no technical detail behind it.
- **[NOT DOCUMENTED]** — I looked in the vendor's own docs/help/API and found nothing. This is an
  answer, not a gap in the research.
- **[NOT VERIFIED]** — the page exists but was blocked (403/503) or renders client-side and could
  not be read. Where a search engine returned indexed text *from* that first-party page, it is
  marked **[VERIFIED-INDEX]** — primary content, secondhand retrieval.

Several first-party doc sites actively block automated fetching: `help.linksquares.com` (403),
`support.ironcladapp.com` (403), `www.sirion.ai` (403), `support.litera.com` and
`developers.docusign.com` (JS-rendered, empty body). Those limits are flagged inline, not papered over.

---

# 1. Vendor selection

Eight products, chosen to span the four archetypes, weighted toward the ones that plausibly own the
*portfolio* question rather than the single-document one.

| # | Vendor / product | Archetype | Why this one | Status & ownership as of 2026-09 |
|---|---|---|---|---|
| 1 | **Ironclad** (CLM + Repository + Public API) | (a) CLM suite | The only CLM in the set with a fully public, unauthenticated developer reference covering Entities, Obligations and Record Amendments — so its data model can actually be read rather than inferred. | Independent, private. No acquisition found. ARR reported >$200M Feb 2026 (secondary). Deloitte alliance announced 2026-06 ([press](https://www.deloitte.com/us/en/about/press-room/deloitte-and-ironclad-form-strategic-alliance.html)). **[VERIFIED — site and dev portal live 2026-09-21]** |
| 2 | **Icertis** (ICI 8.2) | (a) CLM suite | The enterprise-procurement end of CLM, and it publishes a complete public product wiki (ICIHelp) including the amendment and AI-extraction models. | Independent, private. Acquired Dioptra 2025-11-19 (secondary, PitchBook). Public wiki at 8.2 live 2026-09-21. **[VERIFIED — wiki live]** |
| 3 | **LinkSquares** (Analyze + Agentic Platform) | (b) analytics / extraction-first | The purest "extract from executed contracts, then answer questions" product still independent, and it shipped Restated Agreements — the closest thing in the market to an "as amended" model. | Independent. Bill Hewitt named **interim** CEO 2026-03 (secondary, PR Newswire) — leadership instability worth noting. Agentic Platform launched Q2 2026. **[VERIFIED — release site live]** |
| 4 | **Workday Contract Intelligence, powered by Evisort AI** | (b) analytics, now platform-embedded | Evisort was the category-defining extraction-first tool; it is now an ERP module. Its datasheet is the clearest primary statement of what "Ask AI across all contracts" means. | **Acquired.** Workday acquired Evisort in 2024; rebranded to Workday Contract Intelligence / Workday CLM. Available through Workday from 2025-03-27 ([Workday newsroom](https://newsroom.workday.com/2025-03-27-Evisort-AI-Powered-Contract-Intelligence-Now-Available-Through-Workday)). Evisort no longer sells standalone. **[VERIFIED]** |
| 5 | **Harvey** (Assistant, Vault, Workflows) | (c) LLM-native legal AI | The best-capitalised legal AI, with a genuine public developer portal and the only detailed public security page in the set. | Independent. $200M round 2026-03 at ~$11B (secondary). Developer portal and security page live 2026-09-21. **[VERIFIED]** |
| 6 | **Luminance** | (c) LLM-native legal AI | The one LLM-native vendor whose *marketing* explicitly claims contract-family/amendment reasoning and portfolio query — i.e. it is selling the exact pitch. Also the only one documenting on-prem. | Independent, private. Site live 2026-09-21. **[VERIFIED]** |
| 7 | **Docusign Navigator / IAM (Agreement Manager)** | (d) platform-embedded | Owns the e-signature funnel, so it gets agreements at creation time; has a public Navigator/Agreement Manager REST API. | Docusign (NASDAQ: DOCU). **Lexion acquired 2024-05**, folded into IAM. Agentic Contract Workflows announced 2026 ([investor release](https://investor.docusign.com/news-and-events/press-releases/news-details/2026/Docusign-Announces-Agentic-Contract-Workflows-for-In-House-Legal-Teams/default.aspx)). Lexion is no longer a standalone product. **[VERIFIED]** |
| 8 | **Thomson Reuters CoCounsel Legal** | (d) platform-embedded | The incumbent-distribution play, and the only vendor publishing hard portfolio-scale numbers (10,000 docs × 100 questions). | Thomson Reuters (NYSE: TRI). CoCounsel Legal "next generation" launched 2026-08; UK expansion 2026-01. **[VERIFIED]** |

**Considered and excluded, with reason:**

- **Sirion** — majority investment by Haveli Investments announced 2026-01, closed 2026-02 (secondary,
  Wikipedia/CB Insights). Genuine contender in archetype (a), but `sirion.ai` returns 403 to automated
  fetch and publishes no open technical documentation, so every answer would be [NOT VERIFIED]. Excluded
  for unreadability, not irrelevance.
- **Agiloft** — active, independent, ships "Screens by Agiloft" contract review. Excluded to avoid a
  third CLM suite; its self-published accuracy evaluation is used in §4.
- **Litera Kira** — alive, not shut down; a module inside Litera since the 2021 acquisition. **Grid Chat**
  (natural-language query across review data) went GA in the **August 2026** release ([Litera support,
  Kira Aug 2026 release notes](https://support.litera.com/article/Kira-August-2026-Release-Notes-855385) —
  page returns a shell to automated fetch, **[NOT VERIFIED]**). Excluded: diligence-project scoped, not
  portfolio scoped.
- **Legora** — $600M Series D at $5.6B, 2026-03/04 (secondary, TechCrunch). Excluded as duplicative of
  Harvey's archetype with thinner public documentation.
- **Hebbia** — excluded: document-and-data engine for finance, no contract-portfolio model documented.

---

# 2. Capability matrix

Split into two tables of four so the cells stay readable. Sources in §2.3.

## 2.1 CLM suites and extraction-first

| | **Ironclad** | **Icertis (ICI 8.2)** | **LinkSquares** | **Workday Contract Intelligence** |
|---|---|---|---|---|
| **1. Portfolio question → computed answer?** | Partly. `conversational_search` on the MCP server runs natural-language search "using the same AI engine as Ironclad's Dashboard Conversational Search" and "understands complex semantic filters" — i.e. **NL → filters over extracted fields**, not a computed cross-contract answer. **[VERIFIED-INDEX]** Aggregation beyond filtering: **[NOT DOCUMENTED]** | Filtering and reporting over Masterdata/Agreement attributes via CRUD APIs and dashboards. A portfolio Q&A surface producing a computed answer: **[NOT DOCUMENTED]** | Yes, claimed: Contract Intelligence lets users "Ask questions in natural language and receive precise answers" across the repository (Q2 2026 release). Whether the answer is computed or retrieved is not stated. **[VERIFIED]** / mechanism **[NOT DOCUMENTED]** | Yes, and the strongest documented statement in the set: "Ask questions about your contracts in simple, natural language and get clear, reasoned answers—including **summaries, calculations, rankings**". Plus full Boolean + conceptual search. **[VERIFIED]** |
| **2. Amendments → "as amended" position** | **The best documented in the set.** An amendment record sets `parent.recordId` + `parent.parentLinkType: "amendment"` and `propertiesToAmend` with `"amendmentType": "replace"`. The parent then exposes an `amendments` array and each amended property carries **`originalValue` alongside the current `value`**. Deleting the amendment **reverts parent values to originals**. Conflicts are prevented, not resolved: no cycles, no self-parenting, **and an amendment may not itself be amended**. **[VERIFIED]** | `Is Amendment` + `Previous Agreement ID` smart link; `Is Inherit On Amendments` (default On) inherits attributes from parent contract type; **amendment chains are allowed** ("amend previously amended agreements"). Whether parent values are updated, whether a consolidated as-amended position is produced, and how conflicting amendments resolve: **[NOT DOCUMENTED]** | **Restated Agreements**: "Each time a new Restated Agreement is generated, LinkAI extracts SmartValues on the newly created text" — i.e. it **synthesises a restated document** and re-extracts from it. Q2 2026 added "Visibility into how agreements were linked" (manual / AI-assisted / automatic). Conflict rules between amendment and master: **[NOT DOCUMENTED]** **[VERIFIED-INDEX]** | Datasheet mentions "contracts and related documents" and obligation management. An amendment→master model or as-amended computation: **[NOT DOCUMENTED]** |
| **3. Counterparty / entity resolution** | Real entity object with `parentId` hierarchy for "organizational structures, subsidiaries, and other hierarchical business relationships", cycle-prevented; `entity_alternativeNames`, `entity_salesforceID`, `entity_category`, `entity_businessType`; `GET` all entity relationship types. **LEI / D-U-N-S / CIK: [NOT DOCUMENTED]. Automatic dedup/merge, merge review, merge reversal: [NOT DOCUMENTED]** (entities are CRUD objects). **[VERIFIED]** | Counterparties are Masterdata entities addressable by REST; `Multi-Party` agreements supported. Party-name normalisation, parent/subsidiary hierarchy semantics, legal-entity identifiers, merge/unmerge: **[NOT DOCUMENTED]** | "subsidiary-level tracking, allowing teams to group and manage agreements based on the specific entities conducting business" (Q2 2026). `Retrieve Parent Child Hierarchy API` returns "all related agreements within a given hierarchy" — note that is *agreement* hierarchy, not *entity* hierarchy. Identifiers, merge/unmerge: **[NOT DOCUMENTED]** **[VERIFIED-INDEX]** | Counterparty is an extracted data point and a dashboard dimension. Normalisation, hierarchy, identifiers, merge review: **[NOT DOCUMENTED]** |
| **4. Temporal / "in force on date X"** | Expiry and term are record properties; NL search example "expire in the next 12 months". `originalValue` vs `value` is a crude two-state history. **Point-in-time reconstruction ("as of date X"): [NOT DOCUMENTED]** | Effective dates as agreement attributes; renewal modelled through `Previous Agreement ID`; agreements can be executed/terminated/expired. Point-in-time query: **[NOT DOCUMENTED]** | Renewal/expiry tracking via SmartValues and alerts. Point-in-time query: **[NOT DOCUMENTED]** | "No more missed renewals"; renewal/expiry dashboards documented. Point-in-time query: **[NOT DOCUMENTED]** |
| **5. Evidence / citation granularity** | Smart Import returns **predictions** (`Retrieve Predictions`) reviewed as AI Suggestions in the Repository. Whether a prediction carries a page or character location: **[NOT DOCUMENTED]** | AI Discovery / AI Studio review surface with per-clause review and "Visual cues on AI confidence on extracted information in Excel". Clause-, page- or character-level source link back to the document: **[NOT DOCUMENTED]** | Agentic assistant gives "citation-backed answers grounded in trusted legal and government sources" — that is *legal research* citation, not source-contract citation. Contract-text citation granularity: **[NOT DOCUMENTED]** **[VERIFIED-INDEX]** | "'Ask AI' answers include **links to source documents**". The datasheet screenshot shows `Sources: 1 Master Service Agreement - Acme Corp` — **document-level**. Clause/page/character: **[NOT DOCUMENTED]** **[VERIFIED]** |
| **6. Deletion, derived data, audit** | `DELETE` for records, entities, obligations and attachments; Exports gated behind a "Security and Data Pro" add-on. **What happens to extracted predictions, embeddings, search indices or summaries on delete: [NOT DOCUMENTED]. Dedicated audit-log API: [NOT DOCUMENTED]** | History tab logs all changes; version upload reports "added, deleted or attribute/clause value changed"; deviation notes retained. Deletion cascade to derived AI data: **[NOT DOCUMENTED]** | **[NOT DOCUMENTED]** — no deletion or audit feature appears in the Q2 2026 release roundup or the indexed help articles reached. | "Advanced administration: Customize user roles, access controls". Deletion cascade, retention controls, audit log: **[NOT DOCUMENTED]** in the datasheet |
| **7. Public API** | **The strongest in the set.** Workflows, Records, Entities, Obligations, Exports, Webhooks, plus an MCP server. Per-bucket RPM published: records read 600 / write 200, entities 600/200, obligations 600/200, workflows 400/40, exports 20, records export 10, webhooks 600, MCP 80, catch-all 800, **company-wide cap 4,500 RPM**. `X-RateLimit-Limit/-Remaining/-Reset` headers; 429 + `Retry-After`. Webhooks retry up to **13.6 hours**; a 410 disables the webhook. SDKs: **[NOT DOCUMENTED]** **[VERIFIED]** | "rich REST API … endpoints to interact with a wide variety of entities such as Agreements, Masterdata, Users, Requests, Clauses, and Templates", CRUD + action triggers. **Sold as a separate SKU** requiring an APIM Dev Portal role; the reference itself is behind that portal. Rate limits, webhooks, SDKs: **[NOT DOCUMENTED]** publicly. **[VERIFIED]** | `Analyze Retrieve Metadata API` returns "Smart Values, Terms, Types, Tags, Parent Child Hierarchy" in bulk or individually as JSON with type/tag/date filters; `Retrieve Parent Child Hierarchy API`; Analyze Events. Rate limits, webhooks, SDKs: **[NOT DOCUMENTED]** **[VERIFIED-INDEX]** | "deliver structured contract data points directly to other enterprise systems … via API and productized integrations". No public API reference located. **[VENDOR CLAIM]** |
| **8. Deployment / residency / models / training** | **[NOT DOCUMENTED]** publicly — `ironcladapp.com/trust` renders client-side and returned no readable body. **[NOT VERIFIED]** | Multi-instance (US/APAC/EU wikis exist, implying regional instances). Model providers, training posture: **[NOT DOCUMENTED]** publicly | **[NOT DOCUMENTED]** at the pages reachable | SaaS inside Workday. "a proprietary LLM fine-tuned for contracts and an orchestration layer that can apply multiple LLMs"; **ISO/IEC 42001 certified**. Which third-party LLMs, residency, training posture: **[NOT DOCUMENTED]** **[VERIFIED]** |
| **9. Integrations** | Salesforce (AppExchange listing), `entity_salesforceID` as a first-class entity field, MCP server, Anthropic/Claude integration. **[VERIFIED]** | Masterdata/Users APIs imply ERP + IdP integration; specific named connectors: **[NOT DOCUMENTED]** at the pages read | "API Integrate with any third-party app" **[VENDOR CLAIM]** | Salesforce, Box, Google Drive, SharePoint, Dropbox, shared drives, "even other CLM platforms"; native to Workday HR/Finance. **[VERIFIED]** |
| **10. Pricing / portfolio size** | **[NOT DOCUMENTED]** — no public price. Largest portfolio size documented: **[NOT DOCUMENTED]**; the 4,500 RPM company cap is the only published scale number. | **[NOT DOCUMENTED]**; API is a paid SKU | **[NOT DOCUMENTED]** | **[NOT DOCUMENTED]** — "Be up and running in days, not months" is the only scale statement |
| **11. Stated limitations** | Explicit and useful: an amendment **cannot amend another amendment**; no cycles or self-parenting; `propertiesToAmend` must exist in the payload or `BAD_REQUEST`. **[VERIFIED]** | "existing validations or dependencies for an attribute's properties set for the agreement will not be inherited to amendments"; AI findings must be dispositioned (Ignore / Defer / Compare / Confirm with Deviation) — i.e. human review is assumed. **[VERIFIED]** | **[NOT DOCUMENTED]** | **[NOT DOCUMENTED]** — the datasheet states no limitation of any kind |

## 2.2 LLM-native and platform-embedded

| | **Harvey** | **Luminance** | **Docusign Navigator / IAM** | **CoCounsel Legal** |
|---|---|---|---|---|
| **1. Portfolio question → computed answer?** | Vault is "a collaborative workspace for large-scale document review, analysis, and synthesis" over "tens of thousands of documents"; Assistant API gives "legal reasoning over documents and data". Scope is a **project**, not a standing portfolio. **[VERIFIED]** | Claimed outright: "Query across complete contracts, contract families, amendments and obligations, asking questions you didn't anticipate needing to ask", "delivering cited answers from first review through portfolio insight". No technical documentation behind it. **[VENDOR CLAIM]** | Extracted provisions + agreement list are queryable; "Data Extraction: Pulls renewal dates, payment terms, and regulatory obligations into centralized dashboards". Computed cross-agreement answers: **[NOT DOCUMENTED]**; **[NOT VERIFIED]** for the API detail (docs render client-side) | Yes, with the only hard numbers in the market: Tabular Analysis reviews **up to 10,000 documents against up to 100 questions** per table, "run as many tables as needed", results in a filterable table. That is *per-document answers tabulated*, not a single computed portfolio answer. **[VERIFIED-INDEX]** |
| **2. Amendments → "as amended"** | **[NOT DOCUMENTED]** — Vault has projects, files and knowledge bases; no agreement-relationship model | "analyzes document families as a single, evolving relationship, interpreting amendments, side letters and related agreements together, **understanding prevailing terms**" — the exact claim, zero documentation of the mechanism or conflict rules. **[VENDOR CLAIM]** | Navigator surfaces renewal dates; agreement-to-agreement relationships: **[NOT VERIFIED]** (reference pages unreadable) | **[NOT DOCUMENTED]** |
| **3. Counterparty / entity resolution** | **[NOT DOCUMENTED]** | **[NOT DOCUMENTED]** | Partial and *manual*: "A party can include one or more other parties, which means that you can **manually create logical groups of parties** such as 'Microsoft' that may contain multiple Microsoft parties such as 'Legal' or 'Azure'". Automatic normalisation, identifiers, reversal: **[NOT DOCUMENTED]** **[VERIFIED-INDEX]** | **[NOT DOCUMENTED]** |
| **4. Temporal** | **[NOT DOCUMENTED]** | "track renewal dates, obligations and risks in real time" **[VENDOR CLAIM]** | Renewal Notice Date and Expiration Date notifications enabled by default; Renewals Management module. Point-in-time reconstruction: **[NOT DOCUMENTED]** **[VERIFIED-INDEX]** | **[NOT DOCUMENTED]** |
| **5. Evidence / citation** | Research answers carry "linked citations"; **the Assistant/Completion API reference does not document a citation object, offsets or quoted spans at all.** **[NOT DOCUMENTED]** for structure | "Every insight is supported by source-level citations … trace outputs directly back to the underlying clause" — **clause-level claimed**, unevidenced. **[VENDOR CLAIM]** | Provisions are extracted values on an agreement record. A source link, page or offset per provision: **[NOT VERIFIED]** | "Each answer links back to the **specific contract language** it's based on, and the system flags anything ambiguous for a second look." Citations delivered as hyperlinked endnotes in Word output. Passage-level; character offsets: **[NOT DOCUMENTED]** **[VERIFIED-INDEX]** |
| **6. Deletion, derived data, audit** | Best in set. API: `DELETE /vault/delete_file/{file_id}`, `DELETE /vault/delete_project/{project_id}` (async), and `GET /vault/workspace/recycle_bin` listing "deleted vaults pending permanent purge". Security page: customers "set retention policies, delete data anytime"; audit logs, SAML SSO, IP allow-listing, data lifecycle management. **What happens to derived indices/embeddings on delete: [NOT DOCUMENTED]** **[VERIFIED]** | Full backups every 24h; breach notice within 24h; ISO 27001. Deletion cascade, audit log: **[NOT DOCUMENTED]** | **[NOT DOCUMENTED]** | **[NOT DOCUMENTED]** |
| **7. Public API** | Real and public. Bearer auth, `https://api.harvey.ai/v2/…`, HTTPS-only. **Assistant API 20 req/min**, **Vault API 10 req/min**, **History Export API 60 req/min** returning "enriched event data with metadata for audits and billing". Vault endpoints: workspace projects, recycle_bin, upload_files, get_metadata, project files (cursor pagination), get_files (status polling), delete_file, delete_project. Webhooks, SDKs: **[NOT DOCUMENTED]** **[VERIFIED]** | **[NOT DOCUMENTED]** — no developer portal or API reference found on luminance.com | Navigator API `getAgreementsList` / `getAgreement`; Agreement Manager API with configurable agreement queries. Response schema, webhooks, rate limits: **[NOT VERIFIED]** (pages unreadable) | **No repository API.** The MCP connector exposes exactly four tools, all deep legal research: Start Deep Legal Research, Check Deep Research Status, Get Deep Research Report, Follow Up. "For tasks beyond research … users should access CoCounsel directly." Ingestion or repository query by API: **[NOT DOCUMENTED]** **[VERIFIED]** |
| **8. Deployment / residency / models / training** | **The most complete disclosure in the set.** Azure-hosted; residency in **EU & Switzerland, US, Australia**, extending to subprocessors; **"Zero Data Retention (ZDR) by model providers"** contractually required; does not train on customer data by default; opt-in bespoke per-customer model whose data "is never used to train models used by other customers"; SOC 2 Type II, ISO 27001 / 27701 / 42001, GDPR, CCPA, AIUC-1. Named model providers: **[NOT DOCUMENTED]** **[VERIFIED]** | **The only on-prem story in the set**: hosted VPC *or* "deployed within their own environment", with a mandatory "Call Home" connection to Luminance management servers for support and patching — i.e. **not air-gapped**. Customer chooses the AWS data centre, then residency is fixed to it plus a backup DC in-region. ISO 27001; Darktrace deployed internally. **[VERIFIED-INDEX]** | SaaS. "Iris is the AI engine behind Docusign IAM." Model providers, residency, training: **[NOT DOCUMENTED]** | SaaS, grounded in Westlaw + Practical Law. Model providers, residency, training: **[NOT DOCUMENTED]** at the help pages read |
| **9. Integrations** | DMS integration is the named driver for the Vault API; Docusign IAM partnership. Named connector list: **[NOT DOCUMENTED]** | **[NOT DOCUMENTED]** | Native e-signature; "Open Legal AI Ecosystem: Partnerships with **Harvey, Legora, and CoCounsel Legal**"; Smart Routing into sales/procurement/HR/finance. **[VERIFIED]** | Westlaw, Practical Law, Word (endnote citations), Claude Desktop via MCP, Docusign IAM. **[VERIFIED]** |
| **10. Pricing / portfolio size** | No public pricing; no self-serve. Documented scale: "tens of thousands of documents" per Vault project. **[VERIFIED]** for scale, **[NOT DOCUMENTED]** for price | **[NOT DOCUMENTED]** | **[NOT DOCUMENTED]** | No public price. **10,000 documents / 100 questions per table** is the documented ceiling. **[VERIFIED-INDEX]** |
| **11. Stated limitations** | Rate limits are stated as limits; nothing said about accuracy or failure modes. **[NOT DOCUMENTED]** | **[NOT DOCUMENTED]** — the marketing asserts "Legal-Grade™" accuracy with no stated failure mode | **[NOT DOCUMENTED]** | Two real ones: the 10,000×100 ceiling, and "flags anything ambiguous for a second look" — an explicit admission that some answers are not reliable unaided. Plus the MCP connector's stated scope limit. **[VERIFIED-INDEX]** |

## 2.3 Sources

**Ironclad** — [dev hub index (`llms.txt`)](https://developer.ironcladapp.com/llms.txt) ·
[rate limits](https://developer.ironcladapp.com/reference/clm-api-rate-limits) ·
[Entities CRUD guide](https://developer.ironcladapp.com/docs/entities-crud-api-guide.md) ·
[Record Amendments CRUD guide](https://developer.ironcladapp.com/docs/record-amendments-crud-api-guide.md) ·
[getting started](https://developer.ironcladapp.com/reference/getting-started-api) ·
[webhooks](https://developer.ironcladapp.com/reference/webhooks) ·
[MCP server help (403 to fetch)](https://support.ironcladapp.com/hc/en-us/articles/39887091143319-Ironclad-MCP-Server) ·
[Anthropic integration](https://ironcladapp.com/product/integrations/anthropic)

**Icertis** — [API Capabilities, ICIHelp 8.2](https://iciwikiapac.icertis.com/ICIHelp8.2/index.php?title=API_Capabilities) ·
[Working with Agreements](https://iciwikiapac.icertis.com/ICIHelp8.2/index.php?title=Working_with_Agreements) ·
[Amendments](https://iciwikiapac.icertis.com/ICIHelp8.2/index.php?title=Amendments) ·
[Contract Digitalization](https://iciwikiapac.icertis.com/ICIHelp8.2/index.php?title=Contract_Digitalization)

**LinkSquares** — [Q2 2026 release roundup](https://release.linksquares.com/q2-2026-release-roundup) ·
[release index](https://release.linksquares.com/) ·
[Restated Agreements help (403)](https://help.linksquares.com/hc/en-us/articles/36730204152471-Restated-Agreements) ·
[API overview (403)](https://help.linksquares.com/hc/en-us/articles/10575707057175-LinkSquares-API-Overview) ·
[Analyze API use cases (403)](https://help.linksquares.com/hc/en-us/articles/10849398433559-Analyze-API-Sample-Use-Cases)

**Workday Contract Intelligence** — [datasheet PDF, doc id 20250404](https://www.workday.com/content/dam/web/en-us/documents/datasheets/workday-contract-intelligence-powered-by-evisort-ai-datasheet-enus.pdf) ·
[product page](https://www.workday.com/en-us/products/contract-management/contract-intelligence.html) ·
[availability announcement 2025-03-27](https://newsroom.workday.com/2025-03-27-Evisort-AI-Powered-Contract-Intelligence-Now-Available-Through-Workday)

**Harvey** — [security](https://www.harvey.ai/security) ·
[developer introduction](https://developers.harvey.ai/guides/introduction) ·
[Vault guide](https://developers.harvey.ai/guides/vault) ·
[Assistant guide](https://developers.harvey.ai/guides/assistant) ·
[authentication](https://developers.harvey.ai/api-reference/authentication) ·
[history exports](https://developers.harvey.ai/guides/usage_history) ·
[Vault platform page](https://www.harvey.ai/platform/vault)

**Luminance** — [Contract Intelligence](https://www.luminance.com/contract-intelligence/) ·
[Analyze](https://www.luminance.com/analyze/) ·
[Security](https://www.luminance.com/security/) ·
[Support data sheet](https://www.luminance.com/files-support/) ·
[Privacy policy](https://www.luminance.com/privacy-policy/)

**Docusign** — [Navigator API reference](https://developers.docusign.com/docs/navigator-api/reference/navigator/agreements/) ·
[getAgreement](https://developers.docusign.com/docs/navigator-api/reference/navigator/agreements/getagreement/) ·
[Agreement Manager API overview](https://developers.docusign.com/docs/agreement-manager-api/) ·
[configure agreement queries](https://developers.docusign.com/docs/agreement-manager-api/concepts/configure-agreement-queries/) ·
[platform approach to contract AI](https://www.docusign.com/blog/a-platform-approach-to-contract-ai) ·
[renewal notifications](https://support.docusign.com/s/document-item?bundleId=pqz1702943441912&topicId=buj1712251122371.html)

**CoCounsel Legal** — [how it works](https://www.thomsonreuters.com/en-us/help/cocounsel/legal/get-started/how-it-works) ·
[Skill: Review documents](https://www.thomsonreuters.com/en-us/help/cocounsel/legal/skills/skills-prompts-workflows/review-documents) ·
[MCP connector guide](https://legal-mcp.thomsonreuters.com/docs/connector-guide) ·
[MCP connector help](https://www.thomsonreuters.com/en-us/help/cocounsel/legal/integrations/mcp-connector/cocounsel-legal-mcp-connector) ·
[product page](https://legal.thomsonreuters.com/en/products/cocounsel-legal)

---

# 3. Per-vendor notes

**Ironclad** is the surprise of this pass. Its Record Amendments API is not a link field — it is a
computed rollup with an `originalValue`/`value` pair per amended property and a *revert on amendment
delete*. That is a real, if shallow, non-destructive amendment model, published openly, and it
invalidates any pitch that says "nobody links amendments to masters". Its ceiling is equally clear:
one level only (an amendment cannot be amended), `replace` semantics only, and the rollup operates on
**structured properties the customer defined**, not on clause text. Its Entities object gives
parent/child subsidiary hierarchy with cycle prevention — again real, again CRUD: someone or something
upstream must decide two names are the same company, because no dedup, merge, review or unmerge appears
anywhere in the reference.

**Icertis** documents the enterprise reality: amendments chain, attributes inherit, humans disposition
every AI finding through Ignore / Defer / Compare / Confirm-with-Deviation. It is the most
*review-oriented* product in the set and the least *computational*. Its API being a separately licensed
SKU behind a dev portal is a commercial fact worth remembering — a buyer evaluating "can I get my
contract data out" gets a price quote, not a URL.

**LinkSquares** does the most conceptually interesting thing in the market: Restated Agreements
*generates new text* representing the consolidated agreement and then re-extracts Smart Values from that
generated text. This is the opposite architectural choice to a decision log — it materialises the
as-amended state as a new document rather than computing it as a projection. It means the restated text
is itself model output, and nothing in the reachable documentation says how a conflict between master
and amendment is resolved, or whether the restatement is re-derivable. The interim-CEO appointment in
March 2026 is a commercial risk signal for anyone considering them as a partner or an acquirer target.

**Workday Contract Intelligence** is the sharpest data point for the citation argument. It is the most
credible "ask anything across the portfolio" product — summaries, calculations, rankings, custom AI
models that backfill a new field across the whole repository — and its own datasheet shows the citation
as a **link to a document title**. A user who wants to know *why* the answer says $10,000 opens the MSA
and reads. That is the gap, stated by the vendor, in the vendor's own screenshot.

**Harvey** is not a contract-portfolio product and does not claim to be. Vault is matter-scoped. What it
does have that nobody else does is a genuinely enterprise-grade published posture: named residency
regions, contractual zero-data-retention from model providers, ISO 42001, a usage/history export API
explicitly for audits, and a recycle bin with a stated purge path. If the founder's buyer is an
enterprise security reviewer, Harvey's security page is the bar the product has to clear.

**Luminance** is the competitive warning. Its marketing already claims, in these words, contract-family
reasoning, amendment interpretation, "prevailing terms", portfolio query and clause-level citations —
the pitch almost verbatim. There is no technical documentation, no API reference and no benchmark behind
it. That is not a reason to dismiss it; it is a reason to expect every prospect to have heard the claim
already and to be sceptical of hearing it again. Luminance is also the only vendor documenting
customer-environment deployment, with the honest caveat that supported on-prem requires a Call Home
channel — so *not* air-gapped.

**Docusign Navigator / IAM** has the structural advantage nobody else has (it sees agreements at
execution) and the weakest publicly readable documentation, because the developer site renders
client-side. The one distinctive documented feature is **manual** party grouping — the user builds the
"Microsoft" umbrella by hand. That is the explicit admission that automated counterparty resolution is
not solved here. Its 2026 posture is to be the substrate under Harvey, Legora and CoCounsel rather than
to win the reasoning layer, which makes it a potential channel rather than only a competitor.

**CoCounsel Legal** publishes the numbers everyone else hides: 10,000 documents × 100 questions per
table, answers linked to the specific contract language, ambiguity flagged for human review. Its shape
is *tabulated per-document answers*, which is a genuinely different product from a computed portfolio
answer, and the distinction is worth making precisely rather than dismissively — for most legal-ops
questions a filterable 10,000-row table is a sufficient answer. Its MCP connector deliberately exposes
research only, so there is no programmatic path into or out of the contract repository.

---

# 4. Independent accuracy evidence

Read in full where linked. Each entry states what it measures **and what it does not**.

**Stanford RegLab / HAI, "Hallucination-Free? Assessing the Reliability of Leading AI Legal Research
Tools"** (published 2024-05-23, updated 2024-05-30)
[[HAI summary](https://hai.stanford.edu/news/ai-trial-legal-models-hallucinate-1-out-6-or-more-benchmarking-queries)].
Pre-registered dataset of **over 200 open-ended legal queries** in four categories (general research,
jurisdiction/time-specific, false-premise, factual recall). Results: **Lexis+ AI and Ask Practical Law AI
produced incorrect information more than 17% of the time; Westlaw AI-Assisted Research hallucinated more
than 34% of the time.** It distinguishes *incorrect* responses from *misgrounded* ones — correct legal
statement, unsupported citation — which is precisely the failure a span-level citation is designed to
make impossible.
**Does not measure:** contract analytics, extraction, portfolio querying, or any product in §2. It is a
legal-research study. Citing it as evidence about contract AI would be exactly the kind of
category-slippage this report exists to avoid. Its transferable finding is narrower and stronger: *a
citation that a human must open to verify is a citation the vendor is not verifying.*

**Vals Legal AI Report (VLAIR), 2025-02-27** [[report](https://www.vals.ai/industry-reports/vlair-2-27-25)].
The first vendor-neutral head-to-head. **Seven tasks** — Data Extraction, Document Q&A, Document
Summarization, Redlining, Transcript Analysis, Chronology Generation, EDGAR Research. Tools: **CoCounsel
(Thomson Reuters), Vincent AI (vLex), Harvey Assistant, Oliver (Vecflow)**; Lexis+ AI withdrew from most
sections. Over **500 samples**; per-task "checks" (204 Data Extraction, 77 Document Q&A, 223 EDGAR);
lawyer baseline sourced through Cognia Law. Headline figures: Harvey Document Q&A **94.8%**, Harvey
Chronology Generation **80.2%** (matching the lawyer baseline), CoCounsel Document Summarization **77.2%**
and a **79.5%** average across its four submitted tasks, Oliver EDGAR Research **55.2%**.
**Stated limitations, verbatim in substance:** scoring is **LLM-as-judge** and "cannot fully replace expert
human review"; tools were evaluated as "pure text-generating tools" rather than as applications with
interfaces; EDGAR questions lacked document-type filters and so misaligned with product design; larger
corpus tasks were constrained by confidentiality on firm datasets.
**Does not measure:** anything at portfolio scale, amendments, entity resolution, temporal correctness,
deletion, or citation *granularity* — only whether the answer passed a check.

**VLAIR Legal Research, 2025-10-14** [[report](https://www.vals.ai/industry-reports/vlair-10-14-25)].
**200 legal research questions** across ten types, blind-scored by lawyers and law librarians. AI products
(Alexi, Counsel Stack, midpage) scored **74–78%** against a **69%** lawyer baseline; legal-specific tools
beat ChatGPT by ~6 points on citation authoritativeness, ChatGPT won where current web information was
needed. **Limitations:** zero-shot only, "did not cater for follow-up prompting"; jurisdiction was given
in the prompt, so sourcing was not truly tested; workflow features not measured. Again: research, not
contracts. Its value here is directional — the 2024 Stanford picture has materially improved within 18
months, so *"legal AI hallucinates"* is no longer a safe premise to build a pitch on.

**CUAD (Contract Understanding Atticus Dataset)**, NeurIPS 2021 Datasets & Benchmarks
[[Atticus Project](https://www.atticusprojectai.org/cuad)]. **510 contracts, 41 clause types, 13,000+
expert annotations**, CC BY 4.0. Measures **clause identification and extraction from a single document**.
**Does not measure:** anything across documents, any temporal question, any resolution question, or the
correctness of an *answer* — only whether a span of a known clause type was found. It is nonetheless the
only public dataset in which the ground truth is a **span**, which makes it the natural fixture for a
span-grounding test.

**LegalBench** [[project site](https://hazyresearch.stanford.edu/legalbench/)]. **162 tasks from 40
contributors**, crowdsourced from lawyers and legal academics, incorporating CUAD-derived contract tasks
(licence grants, IP ownership, termination and renewal, liability caps, insurance, non-compete,
confidentiality). Measures **legal reasoning** across "complex jargon, longer contexts, sophisticated
multi-step reasoning, intricate structure, and minimal labeled data".
**Does not measure:** any system property — it evaluates models, not products, on short isolated tasks.

**CLAUSE** [[arXiv 2511.00340](https://arxiv.org/pdf/2511.00340)], 2025-11. **Over 7,500 perturbed
contract samples** generated from CUAD and ContractNLI across **10 anomaly categories**, validated by a
RAG pipeline against official statutes. Measures whether LLMs **detect fine-grained embedded legal flaws
and explain their significance**. Finding: models "often miss subtle errors and struggle even more to
justify them legally". This is the closest thing to a contract-specific adversarial benchmark and it is
a negative result. **Does not measure:** retrieval, portfolio scope, or product behaviour.

**Screens by Agiloft accuracy evaluation** [[Agiloft blog](https://www.agiloft.com/blog/screens-redlining-evaluation/),
[Screens](https://www.screens.ai/blog/screens-accuracy-evaluation-report)]. **97.6%** success at correcting
failed standards with suggested redlines, over **50 publicly available software terms-of-service
contracts** against a published community screen. **This is vendor-published, not independent** — but it is
the only evaluation in the set whose corpus, prompt and method are public enough that "the analysis can be
reproduced by anyone using the Screens platform". Treat the number as marketing and the *methodology
disclosure* as the genuine benchmark to beat.

**What does not exist, as far as I can find:** a vendor-neutral benchmark that measures cross-contract
portfolio question answering, amendment/as-amended correctness, counterparty resolution accuracy, or
citation granularity. Every published evaluation is single-document or single-question. That absence is
itself a finding: there is no scoreboard a buyer can use to check any of the six differentiators, which
cuts both ways — nothing proves incumbents are bad at it, and nothing stops them claiming they are good.

---

# 5. What none of them document

Across all eight, at first-party sources, I found **no documentation at all** of:

1. **Character- or offset-level provenance.** The best in the set is CoCounsel's "links back to the
   specific contract language" and Luminance's "trace outputs directly back to the underlying clause"
   (a claim). Nothing exposes a span, offset or verbatim quote as retrievable data, and no API returns a
   citation object with a location.
2. **What happens to derived data on deletion.** Every vendor with an API has a `DELETE`. Not one states
   whether extracted fields, embeddings, search indices, dashboards, cached summaries or restated
   documents are removed with the source. Harvey comes closest with a recycle bin and a "pending
   permanent purge" state — for files, not for derivations.
3. **Reversible entity merges.** Ironclad and Docusign both have entity/party grouping; both are manual
   CRUD. No vendor documents an automatic counterparty merge, therefore none documents reviewing or
   reversing one, therefore none documents a human decision outranking a model decision.
4. **Legal-entity identifiers.** No LEI, D-U-N-S, CIK or any external registry anchor in any entity model.
5. **Point-in-time queries.** Every vendor tracks effective and expiry dates. None documents "what was in
   force on date X" as a query, or a bi-temporal distinction between when a fact was true and when the
   system learned it.
6. **Extraction versioning.** No vendor states which model or which extraction schema version produced a
   given field, or what happens to previously extracted values when the model is upgraded. Icertis's
   deviation notes and Ironclad's `originalValue` are the only traces of prior state anywhere.
7. **Conflict rules between documents.** Ironclad *prevents* conflicts by construction. Everyone else is
   silent on what happens when an amendment and its master disagree.
8. **Tenant isolation mechanics.** Certifications yes (SOC 2, ISO 27001/42001); a statement of how
   isolation is enforced, no — anywhere.
9. **Public pricing.** Not one of the eight publishes a price.
10. **Stated failure modes.** Only Ironclad (structural constraints) and CoCounsel (scale ceiling,
    ambiguity flagging) say anything about what the product cannot do. Workday's datasheet and
    Luminance's site state no limitation of any kind.

---

# 6. Blunt assessment: the six differentiators

## (1) Character-span provenance on every fact — **still genuinely yours, and it is the only unambiguous one.**

No vendor documents a span. The strongest counter-evidence is CoCounsel — "each answer links back to the
specific contract language it's based on" — which is passage-level in the UI, and which the founder should
assume looks identical to a buyer in a demo. Workday, the most credible portfolio-Q&A product in the set,
cites at **document** level and shows it in its own datasheet screenshot.

But read §1.3(a) of the prior pass again, because the risk has moved. The gap is no longer "does anyone
highlight the source text" — several do, in the UI. The gap is that **nobody exposes the span as data**:
no API in this set returns a citation object with a location, so no customer can build a programmatic
verification, a coverage metric, or a hallucination check on top of a vendor. That is the defensible
claim, and it is a *developer-platform* claim, not an end-user one — which supports the ticket's second
hypothesis over its first. Selling "we highlight the sentence" to a legal-ops buyer is selling something
Luminance already claims and CoCounsel already ships.

## (2) Retractable resolution decision log with permanent human precedence — **yours, but the market has not asked for it.**

Nothing documented anywhere. Ironclad's Entities and Docusign's party groups are both **manual** — a human
creates the hierarchy or the umbrella group, so there is no model decision to outrank and no merge to
reverse. That is the honest reading: incumbents avoided the problem rather than solved it badly.

The uncomfortable consequence is that there is no incumbent over-merge scandal to point at, no benchmark
that scores resolution, and no buyer who has been burned by an automated merge — because nobody automates
it. "Human decisions permanently outrank model decisions across upgrades" answers an objection the market
has not yet raised. It is real, it is defensible in an adversarial demo (§2.5 step 17 of the prior pass),
and it is not a reason anyone will take the first meeting.

## (3) Assertion-counted deletion — **yours, and it is the most under-rated one.**

Nobody documents the cascade. Every vendor has `DELETE`; not one says what happens to the extracted field,
the dashboard number, the embedding or — in LinkSquares' case — the *generated restated agreement* that was
derived from the deleted document. LinkSquares is the sharpest example: delete the amendment that produced
a Restated Agreement and the documentation says nothing about the restatement or the SmartValues extracted
from it.

This is not a feature claim, it is a compliance claim, and it is checkable in one SQL query in front of a
buyer's privacy counsel. Its weakness is buyer sequencing: it is a week-five question, not a week-one one.

## (4) Immutable versioned ontologies — **yours, but the buyer-facing version of it is different from the plan's.**

No vendor records the extraction schema version a field was produced under. What every vendor *does* ship
is customer-defined extraction: Workday's "custom AI models" that "automatically analyze every contract in
your repository", Ironclad's Smart Import predictions, Icertis's AI Studio, LinkSquares' Smart Values.
The market has already solved "let me define my own fields" — and solved it self-service, with no prompt
engineering required (Workday's explicit claim).

So the differentiator is not *configurable ontology*; that is table stakes and Workday does it better than
a v1 will. The differentiator is **what happens on the second version**: every one of those products lets a
customer edit a field definition, and none of them documents whether previously extracted values are
recomputed, stale, or silently mixed. Pitch immutability as *"your Q3 number and your Q1 number were
computed by the same rules, and we can prove which"*, not as ontology hygiene.

## (5) Database-enforced tenant isolation — **yours technically, invisible commercially.**

No vendor documents isolation mechanics; all the large ones hold SOC 2 Type II and most hold ISO 27001,
and Harvey and Workday hold ISO 42001. A security reviewer's questionnaire is satisfied by the certificate,
not by the DDL. `FORCE ROW LEVEL SECURITY` will not win a deal against a company holding SOC 2, ISO 27001,
ISO 27701, ISO 42001 and AIUC-1 with published residency regions and contractual zero-data-retention from
its model providers — which is Harvey's documented position today.

Treat this as a cost-of-entry item and a defence against a single catastrophic incident, not a
differentiator. The commercial work here is the certificate, not the predicate.

## (6) Bi-temporal validity, amendments superseding clauses — **the weakest of the six. Partly taken.**

This is where this pass changes the picture most, and the founder should not be told otherwise.

- **Ironclad ships a documented, non-destructive, reverting amendment rollup.** `propertiesToAmend`,
  `originalValue` beside `value`, an `amendments` array on the parent, and **deleting the amendment reverts
  the parent's values**. That is a working "as amended" position with an undo, publicly documented, today.
  Its ceiling is real — one level, `replace` only, structured properties rather than clause text — but
  "nobody links an amendment to its master" is no longer a true sentence.
- **LinkSquares ships Restated Agreements**, which generates consolidated text and re-extracts from it, plus
  subsidiary-level grouping and visible link provenance (manual / AI-assisted / automatic).
- **Icertis allows amendment chains** with attribute inheritance, which Ironclad does not.
- **Luminance markets the full claim** — "document families as a single, evolving relationship … understanding
  prevailing terms" — with no documentation behind it, which means the *claim* is already commoditised even if
  the capability is not.

What is left that is genuinely yours: **the temporal query**. Not one vendor documents "what was in force on
date X". Ironclad gives two states (original, current). Icertis gives a history tab a human reads.
LinkSquares gives a regenerated document. None gives a point-in-time projection, and none distinguishes
valid time from transaction time. Combined with §1.3(c) of the prior pass — Graphiti already has bi-temporality
over chat episodes — the defensible statement narrows to: **bi-temporal validity over a contract corpus,
queryable as of an arbitrary date, with the superseding amendment and its span shown.** Claim that. Do not
claim amendment linking.

## What is genuinely still open

1. **Which hypothesis this supports.** The vendor evidence leans to the ticket's *second* hypothesis. The
   distinctive gap is not "legal ops cannot get answers" — Workday, CoCounsel and LinkSquares all ship a
   credible answer surface — it is that **none of them exposes the evidence, the decision or the deletion
   cascade as data an engineer can build on.** Every one of the six differentiators is a property of a
   *record*, and records are what platforms sell. The buyers pass (`contract-ai-buyers.md`) should test the
   builder segment hard, not treat it as the fallback.
2. **Whether a filterable 10,000-row table is already the answer.** CoCounsel's Tabular Analysis may satisfy
   most real legal-ops portfolio questions without any graph at all. This is the vector-RAG-baseline problem
   from the prior pass, in its contracts form, and it needs the same treatment: run it, measure it, show it
   before the buyer does.
3. **Whether the amendment claim survives contact.** Ironclad's rollup should be exercised on real data
   before any pitch repeats "nobody does this". The specific open questions: does it work on clause text or
   only on customer-defined properties, and what does a two-level amendment chain actually do.
4. **Docusign is unmeasured.** Its developer documentation could not be read (client-side rendering), and it
   has both the best ingest position in the market and an explicit strategy of being the substrate under
   Harvey, Legora and CoCounsel. It is the most likely channel partner and the most likely to close the gap
   by default. Someone should read those API docs in a browser.
5. **No scoreboard exists.** There is no vendor-neutral benchmark for portfolio QA, amendments, resolution
   or citation granularity. That means a design partner's sealed holdout (§2.2 of the prior pass) is not
   just good practice — it is the *only* available evidence, for us and for every competitor.
