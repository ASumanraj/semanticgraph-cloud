# Contract AI: who is customer one? (buyer pass, T-907)

**Date** 2026-09-21 · **Scope** demand side only; the vendor pass is a separate document.
**Labels** used on every claim: **[VERIFIED]** a primary source states it and I opened it ·
**[VENDOR CLAIM]** a supplier or supplier-sponsored survey states it · **[PRACTITIONER REPORT]**
anecdotal / professional commentary · **[HYPOTHESIS]** my inference, not evidenced ·
**[NOT VERIFIED]** asserted by a secondary source I could not trace to a primary.

Nothing here is called a market gap. Where I found nothing, it says "no evidence found".

---

## The three segments

| # | Segment | Why chosen |
|---|---|---|
| **S1** | **Corporate legal-operations / procurement teams with large agreement portfolios** | Required by the ticket (H1) |
| **S2** | **Teams building contract or legal-AI products** — CLM vendors, legal-tech startups, ALSPs with product ambitions | Required by the ticket (H2) |
| **S3** | **EU financial entities compiling the DORA Article 28(3) register of information** | Chosen over the other four founder guesses — see §"Why S3 and not the others" |

### Why S3 and not the others

- **Lease / revenue-contract abstraction for accounting standards** — the forcing events (IFRS 16, ASC 842) had transition dates of 2019 for public filers and 2022 for private US filers. The *abstraction wave* is historic; what remains is steady-state modification accounting. I found one primary procurement record for outsourced lease abstraction (US DOJ, $2.76m, 2021 — see S1 §5) but **no evidence found** of a live, recurring, cross-contract question at 2026. Rejected as a wedge on recency, not on size.
- **M&A / PE diligence and law firms** — real and recurring, but the incumbent (Kira Systems, now Litera) has a decade of trained field models, and the one company that tried to sell exactly our shape of product into it — Zuva, the Kira spin-out — has moved *up* into an end-user sell-side product (S2 §3). That is evidence against us, not for us, and it is more useful as a warning than as a target.
- **Regulated pharma / life-sciences contract compliance** — **no evidence found** of a published survey, procurement record or regulator instrument creating a recurring cross-contract query. I searched; I did not find one I could open. Do not assume it is absent — assume I did not look hard enough.
- **Insurers reading policy wording** — **no evidence found** at the quality bar here. It is also a *document-interpretation* problem more than a *portfolio-resolution* problem, which is the opposite of our differentiator.
- **DORA** wins because it is the only candidate where a regulator names the artefact, names the fields, names the deadline, and has **published measured failure rates** on the industry's first attempt (S3 §1). That is the rarest thing in this whole document: an external party quantifying the pain.

---

## Comparison table

| | **S1 — Legal ops / procurement** | **S2 — Builders of contract/legal AI** | **S3 — DORA register (EU finserv)** |
|---|---|---|---|
| **1. Strongest recurring trigger** | Tariff/price-increase waves and sanctions changes forcing "which of our supplier contracts let them pass this through?"; renewal cliffs; audits. Episodic, unscheduled, 1–3×/yr. **[PRACTITIONER REPORT]** | A customer or a court finding a fabricated or unsupported citation in their product's output. 2,046 judicial findings of AI hallucination logged, from Q2 2023 to 2026-09-21. **[VERIFIED]** | Annual submission of the register of information to the national competent authority, then to the ESAs, by 30 April. Statutory, dated, every year. **[VERIFIED]** |
| **2. Current workaround** | Contract repository + metadata fields + spreadsheets + outside counsel + ALSPs. 90% report difficulty locating contracts; 49% have no defined process for storing executed contracts. **[VERIFIED]** | Build it: parsing, chunking, vector store, eval set, monitoring. Or buy narrow field-extraction APIs (Zuva: $1.25/doc + $0.0015/field/page). **[VERIFIED]** for pricing; build cost **[VENDOR CLAIM]** | Spreadsheets assembled by hand from procurement systems and contract PDFs, then CSV/XBRL conversion. 46% of institutions call the register their biggest DORA hurdle. **[NOT VERIFIED]** (secondary) |
| **3. Why tools fall short** | 78% do not systematically track contractual obligations; 71% do not monitor for deviation from standard terms — *despite* CLM being widely deployed. **[VERIFIED]** | RAG does not fix it: leading legal research tools hallucinated 17–33% of the time against vendor "hallucination-free" claims. **[VERIFIED]** | 6.5% of dry-run registers passed all 116 data-quality checks; 86% of errors were missing mandatory information; identifier (LEI) errors were the next most frequent. **[VERIFIED]** |
| **4. Buyer vs user** | Buyer: GC/CLO or CPO. User: contract manager, category manager, paralegal. Path: legal-ops-led, IT security review, procurement. **6–12 months [HYPOTHESIS]** | Buyer: CTO/founder. User: their own engineers. Path: free tier → credit card → annual. **Days to weeks [HYPOTHESIS]** | Buyer: Head of ICT third-party risk / CISO / COO, inside a funded DORA programme. User: TPRM analyst + legal. Path: regulatory-change budget line. **3–9 months [HYPOTHESIS]** |
| **5. Budget evidence** | Icertis platform licences, DHS, **$1.33m** (2026); Agiloft, US DOT, **$618k** (2018). ALSP market **$28.5bn**, 57% of law departments use one. **[VERIFIED]** | Legal tech raised **$4.28–5.99bn in 2025** depending on tracker; Workday paid **$311m** for Evisort, DocuSign **$165m** for Lexion. **[VERIFIED]** | 47% of UK / 38% of EU finserv CISOs spent **over €1m** on DORA compliance. **[VENDOR CLAIM]** (Rubrik/Wakefield, n=350) |
| **6. Portfolio size** | Large orgs: ~**19,000 contracts/yr**, ~**350/week**; basic contract ~**$7,000** to create, complex ~**$50,000**. **[VERIFIED]** (EY/Harvard, n=1,000) | N/A — they hold their *customers'* portfolios. Sirion alone claims 7m+ contracts under management. **[VENDOR CLAIM]** | Dry run: 1,039 entities submitting, covering **3,447 financial entities** on a consolidated basis. Per-entity ICT contract counts: **no verified figure found**. |
| **7. Customer-1 hypothesis** | See S1 §7 | See S2 §7 | See S3 §7 |

---

# S1 — Legal operations / procurement with large portfolios

## 1. The strongest pain, as a recurring event

The honest finding first: **I could not find a primary source that measures the frequency of
cross-contract trigger events.** What exists is (a) survey evidence that the underlying data is
not findable, and (b) a dense wave of law-firm client alerts in 2025 showing a live trigger.

**Trigger — tariff and price-increase waves (2025).** Through 2025, major firms published client
guidance on reviewing supplier portfolios for force majeure, price-escalation, change-in-law and
pass-through clauses in response to US tariff changes: Foley & Lardner
([Aug 2025](https://www.foley.com/insights/publications/2025/08/tariffs-and-your-contracts-why-do-force-majeure-provisions-matter/),
[Feb 2025](https://www.foley.com/insights/publications/2025/02/multinational-company-import-risks-under-trump-administration-part-iv/)),
Honigman ([alert 3028](https://www.honigman.com/alert-3028)), Irwin Mitchell
([Tariffs and supplier contracts](https://www.irwinmitchell.com/news-and-insights/expert-comment/post/102k8gs/tariffs-and-supplier-contracts)).
**[PRACTITIONER REPORT]** — these establish that the question is being asked, not how often or at
what cost.

**Corroborating trigger.** The 2026 ACC Chief Legal Officers Survey (n=1,049 CLOs, 43 countries)
records **trade and tariffs cited by 30% of respondents** as a rising priority
([ACC newsroom](https://www.acc.com/about/newsroom/news/changing-c-suite-clos-grow-strategic-leadership-ai-and-global-uncertainty)).
**[NOT VERIFIED]** — the ACC page returned HTTP 403 to me; the 30% figure is from the search
summary of that page and I could not open the primary. Treat as unconfirmed.

**Historic proof that the event class is real and expensive — LIBOR.** The ARRC's own closing
report frames legacy USD LIBOR cash products at approximately **$5 trillion** in exposure and
documents a Legacy Playbook covering contract assessment, contract remediation and fallback
communication ([ARRC Closing Report, NY Fed](https://www.newyorkfed.org/medialibrary/Microsites/arrc/files/2023/ARRC-Closing-Report.pdf)).
**[VERIFIED]** for the exposure figure and the existence of a contract-remediation workstream.
**No verified figure found** for the *number of contracts* remediated — which is precisely the
number a product like ours would want.

## 2. The current workaround and what it costs

From EY Law + Harvard Law School Center on the Legal Profession, *The General Counsel Imperative:
How does contracting complexity hide clear profitability?* — **1,000 interviews** with law
department, procurement, commercial contracting and business development leaders, 17 industries,
22 countries, January 2021
([EY](https://www.ey.com/en_gl/insights/law/the-general-counsel-imperative-how-does-contracting-complexity-hide-clear-profitability)).
All **[VERIFIED]** against that page:

- **90% report difficulty locating contracts** once executed.
- **49% have no defined process for storing executed contracts.**
- **78% do not systematically track contractual obligations.**
- **71% do not monitor contracts for deviation from standard terms.**
- **99% say they lack the data and technology needed to improve contracting.**
- A basic contract costs roughly **$7,000** to produce; a complex one averages **$50,000**.
- **Over 50%** report lost business from contracting inefficiency; **57%** of business-development
  teams report delayed revenue recognition.

The outsourced arm of the workaround is measurable. Thomson Reuters' *Alternative Legal Services
Providers 2025* puts the ALSP market at **$28.5bn**, growing at **18% CAGR 2021–2023**, with
**57% of corporate law departments** using an ALSP
([TR press release](https://www.thomsonreuters.com/en/press-releases/2025/january/alternative-legal-services-providers-2025-report-shows-segment-comprises-28-billion-of-the-legal-market)).
**[VERIFIED]** for the headline figures. **No breakdown by contract-management service found** —
so the share of that $28.5bn that is contract abstraction is unknown, and I will not guess it.

Value leakage: the widely repeated **9.2% of contract value** figure originates with
WorldCC/IACCM; I could open only WorldCC's own landing page
([Stopping the Leak](https://www.worldcc.com/resource/Stopping-the-Leak-The-value-of-contracts.html))
and not the underlying study. **[NOT VERIFIED]**. A more recent WorldCC/Ironclad figure of
**11% of value lost post-signature** is likewise reported only in secondary coverage
([PASA](https://procurementandsupply.com/procurement-contracts-leaking-11-percent-of-value-due-to-enterprise-wide-failures/)).
**[NOT VERIFIED]**. Do not put either number in a deck.

## 3. Why existing tools fall short — in buyers' terms

The strongest evidence is internal to the EY data, and it is the most important finding in this
section: **78% do not track obligations and 71% do not monitor term deviation, in a population
where 70% claim a formal contracting-technology strategy** (EY, as above) **[VERIFIED]**. A
repository that stores the PDF and a dozen metadata fields does not answer "which contracts let
this counterparty raise prices, as amended, as of today". That is a *shape* mismatch, and it is
the closest thing in this document to direct support for H1.

Counter-evidence, and it is serious. The 2025 WorldCC/Sirion CCM Benchmark Report finds
**70–80% of organisations lack clear accountability for contracting performance**
([GlobeNewswire release](https://www.globenewswire.com/news-release/2025/11/05/3182060/0/en/2025-CCM-Benchmark-Report-Highlights-the-Importance-of-Contracting-Maturity-Amid-Global-Uncertainty.html))
**[VENDOR CLAIM]**. If nobody owns the number, nobody has a budget line for fixing it, and the
sale has no natural sponsor. That is the standard failure mode for legal-ops tooling and it is
not a technology problem we can solve.

## 4. Buyer vs user, and procurement path

- **Signs:** General Counsel / Chief Legal Officer, or Chief Procurement Officer. The CLOC 2025
  State of the Industry (n=186 organisations, 14 countries, from the 2024 Harbor Law Department
  Survey) reports median internal legal spend **$20.1m** and external **$19.5m**
  ([CLOC newsdesk](https://cloc.org/newsdesk/2025-state-of-the-industry-report/)) **[VERIFIED]**
  for sample and spend; I downloaded the [SOTI PDF](https://cloc.org/wp-content/uploads/2025/02/2025-CLOC-2025-SOTI-Report.pdf)
  but it is image-only and I could not extract its contract-management detail — **[NOT VERIFIED]**
  for anything beyond the newsdesk page.
- **Works in it:** contract managers, category managers, paralegals, commercial managers.
- **Path:** legal ops builds the case → IT security / privacy review → procurement → legal
  (ironically, their own contract). **Sales cycle 6–12 months [HYPOTHESIS]** — I found no
  published measurement of legal-tech sales-cycle length and will not invent one.

## 5. Budget evidence (primary, public)

Queried [USAspending.gov API](https://api.usaspending.gov/) directly, award types A–D. **[VERIFIED]**:

| Award | Recipient | Agency | Amount | Period |
|---|---|---|---|---|
| Icertis Contract Management platform licences ("brand name or equal") | AccessAgility LLC | DHS | **$1,332,543** | from 2026-09-01 |
| Agreement-tool replacement software + implementation | **Agiloft Inc** | US DOT | **$618,072** | from 2018-06-11 |
| ICAT — commercial end-to-end CLM SaaS for the ITIPSS contract portfolio | MSM Group | US DOT | **$778,725** | 2023-04 → 2027-04 |
| DocuSign CLM licences | Advanced Computer Concepts | DoD | **$152,441** | 2024-08 → 2027-07 |
| Real-estate data analysis incl. **lease abstraction** (services) | Koniag Technology Solutions | DOJ | **$2,762,637** | from 2021-06 |

Keyword searches for **"Evisort"** and **"contract abstraction"** in US federal awards returned
**zero results** — a useful negative: the abstraction *service* is not bought under that name
federally.

Commercial list prices are not published. Third-party aggregators put Icertis median ACV at
**~$88k** with enterprise deals $150k–$500k+ — **[NOT VERIFIED]**, these are resale/benchmark
sites, not the vendor, and I would not cite them to a buyer.

**UK Contracts Finder: no usable evidence found.** I queried the
[OCDS search API](https://www.contractsfinder.service.gov.uk/Published/Notices/OCDS/Search) for
award-stage notices 2022–2026 on several CLM keyword variants; the keyword parameter returned
notices unrelated to the query (building refurbishments, etc.) and zero CLM awards matched on
title or description. This is an API limitation, not a finding about UK spend.

## 6. Portfolio size

**[VERIFIED]** (EY/Harvard, n=1,000): large organisations manage approximately **19,000 contracts
annually** and around **350 contracts per week**. Note carefully — this is *flow*, not *stock*.
**No verified survey figure found for the installed base** (total live agreements held), which is
the number that determines our ingestion cost. That gap matters and it is listed again in
"Where the evidence is thin".

## 7. Falsifiable customer-1 hypothesis

> We believe **corporate legal-ops or procurement teams at organisations executing ≥5,000
> contracts a year, who already own a CLM and still cannot answer portfolio questions
> (EY: 78% do not track obligations)**, currently **export to spreadsheets and commission ALSP or
> outside-counsel reviews** to answer **"which agreements, as amended, permit/forbid X as of
> date D, and show me the sentence"**, and would pay **$50k–$150k/yr** for a queryable,
> citation-backed layer over their existing repository.
>
> **FALSIFIED IF:** in 10 structured interviews with such teams, fewer than 5 can name a specific
> cross-contract question from the last 12 months that took more than 3 person-days; **or** fewer
> than 3 can name the budget line and the named individual who would sign; **or** ≥7 say their
> existing CLM's search already answered it well enough that nobody escalated.

## 8. Five interview questions (past behaviour)

1. **"Walk me through the last time someone asked you a question that spanned more than twenty
    contracts. What was the question, who asked, and what did you actually do that week?"**
    *Good:* a dated event, a named requester, a named spreadsheet, a count of hours or an invoice.
    *Bad:* "we get those all the time" with no instance; or a description of a feature they wish existed.
2. **"Show me the last spreadsheet you built to answer one of these. What columns are in it, and
    where did each column come from?"** *Good:* they open it; columns trace to specific contracts
    and people; they point at the column that was wrong. *Bad:* it does not exist, or it is a
    vendor's export nobody edits.
3. **"When tariffs changed last year, what did your team do in the first two weeks?"**
    *Good:* a concrete triage — a list pulled, N contracts read, outside counsel scoped at $X.
    *Bad:* "we advised the business" / "we monitor the situation".
4. **"Tell me about the last time an answer you gave turned out to be wrong because a contract had
    been amended. What happened next?"** *Good:* a specific incident with a consequence and a
    process change. *Bad:* "that's why we're careful".
5. **"What did you spend outside your software budget on contract review in the last year —
    outside counsel, an ALSP, temps — and what was the invoice for?"** *Good:* numbers, vendor
    names, a purchase order. *Bad:* "it comes out of the legal budget somewhere".

---

# S2 — Teams building contract or legal-AI products

## 1. The strongest pain, as a recurring event

**Trigger — a fabricated or unsupported citation reaching a customer or a court.** Damien
Charlotin's AI Hallucination Cases database ([damiencharlotin.com/hallucinations](https://www.damiencharlotin.com/hallucinations/))
held **2,046 cases as of 2026-09-21**, covering ~40 jurisdictions from Q2 2023, of which the US
accounts for 1,397, Canada 218, Australia 112, Israel 57; **815 involve lawyers** and 1,175 pro-se
litigants. Inclusion requires a court to have found or clearly implied actual reliance on
fabricated material — allegations do not count. **[VERIFIED]** (I opened the database page).

Note what this does and does not prove. It proves that *unsupported output has legal consequences
and is being counted*, which is why every builder in this space now ships citations. It does
**not** prove that builders would buy a substrate rather than build one. Those are different
claims and the ticket asks about the second.

**Trigger — a benchmark or customer discovers the citations are wrong anyway.** Stanford RegLab /
HAI, *Hallucination-Free? Assessing the Reliability of Leading AI Legal Research Tools*
([arXiv 2405.20362](https://arxiv.org/pdf/2405.20362), [RegLab](https://reglab.stanford.edu/publications/hallucination-free-assessing-the-reliability-of-leading-ai-legal-research-tools/)),
the first preregistered empirical evaluation of these tools, later peer-reviewed in the *Journal
of Empirical Legal Studies* (2025): **Lexis+ AI hallucinated ~17%, Westlaw AI-Assisted Research
~33%, GPT-4 ~43%** of the time, against public vendor claims of "100% hallucination-free linked
legal citations" and "avoid hallucinations by relying on trusted content". **[VERIFIED]**.

That is the single best piece of evidence in this whole document for the *technical* premise of
the product: retrieval grounding at chunk level does not produce defensible citations. It is
about legal *research*, not contracts, which weakens the transfer — flag that.

## 2. The current workaround and its cost

**Build.** The consistent pattern in builder-facing writing is a seven-part in-house stack:
ingestion/parsing, legal-structure-aware chunking, vector store, auth/security review, a labelled
eval set, logging/monitoring, and ongoing maintenance against layout drift. Figures quoted:
**$40k–$120k of engineering before the first production query** and **6–16 weeks** to a custom
pipeline. Sources are vendor blogs selling the alternative
([Reducto](https://reducto.ai/blog/build-vs-buy-ai-document-ingestion),
[Nutrient](https://www.nutrient.io/blog/build-vs-buy-document-extraction/),
[Genta](https://genta.dev/resources/ai-contract-review-software-mid-market)) — **[VENDOR CLAIM]**,
and these numbers are marketing, not measurement.

**Buy, narrowly.** Zuva sells exactly the H2 shape — a contracts AI API for developers
([zuva.ai/api](https://zuva.ai/api/), [pricing](https://zuva.ai/pricing/)), with **1,400+
built-in fields**, a free tier of **25 files / 25 extractions / 25 classifications per day**, and
pay-as-you-go at **$1.25 per document plus $0.0015 per field per page**, behind a **$5,000
minimum commitment**. **[VERIFIED]** for the API's existence and field count from zuva.ai;
**[NOT VERIFIED]** for the exact price points, which I obtained via search summary of the pricing
page rather than by opening it (the `/pricing/` URL 404'd for my fetcher).

**This is the price anchor for H2 and it is low.** $1.25/document for field extraction sets the
reference point a builder will compare us to. Our ingest budget in
`pipeline-comparison-and-acceptance.md` §2.4 is ≤$0.09 per 10-page document — comfortably under,
which is good news, but it also means the *price ceiling* for this segment is roughly a dollar a
document, not an enterprise seat licence.

## 3. Why existing tools fall short — and the strongest counter-evidence in this document

**Zuva's own trajectory is the thing to stare at.** Zuva was spun out of Kira Systems when Litera
acquired Kira in August 2021, taking 34 employees, the ML research team and rights to a decade of
contract-AI development, and raised **CAD $20m Series A led by Insight Partners**
([LawSites](https://www.lawnext.com/2024/09/kira-spin-off-zuva-unveils-new-contract-review-ai-for-in-house-legal-teams-zuva-analyze.html),
[CCBJ](https://ccbjournal.com/news/kira-systems-spinoff-company-zuva-announces-first-product-launch-docai)).
Its first product was **DocAI, a developer API** — the purest expression of H2 that has ever been
funded. Since then it launched **Zuva Analyze**, an end-user product for in-house legal teams
(2024), and by 2026 its own About page leads with **sell-side M&A diligence products** —
diligence reviews and bidder-question management — describing the pivot as coming from
interviewing "about 150 M&A professionals" ([zuva.ai/about](https://zuva.ai/about/)).
**[VERIFIED]** from Zuva's own page.

A best-in-class team, well funded, with the best contract-extraction models available and a
decade of training data, started as a developer API and moved up-stack **twice**. The API still
exists; it is no longer the story. **That is direct, named, primary evidence against H2's
business model**, and it should not be explained away. The most likely reading: builders in this
market are few, price-sensitive, and either build it themselves or get acquired before they scale
a substrate bill.

**Market-structure counter-evidence.** The two notable contract-AI exits went *into* end-user
platforms, not into infrastructure: Workday acquired Evisort for **$311m in cash**, closing
2024-10-08 ([Workday newsroom](https://newsroom.workday.com/2024-09-17-Workday-Signs-Definitive-Agreement-to-Acquire-Evisort), amount per
[Workday 10-Q](https://www.sec.gov/Archives/edgar/data/1327811/000132781124000242/wday-20241031.htm)),
and DocuSign acquired Lexion for **$165m in cash**
([DocuSign](https://www.docusign.com/company/news-center/docusign-announces-agreement-to-acquire-lexion)).
**[VERIFIED]**. Value accrued to the application layer.

## 4. Buyer vs user, and procurement path

- **Signs:** founder/CTO at a startup; VP Engineering or Head of Product at a CLM vendor.
- **Works in it:** their own backend engineers.
- **Path:** free tier → self-serve card → annual commit with a security questionnaire. Zuva's
  $5k minimum commitment is a concrete data point on where self-serve stops **[NOT VERIFIED]**.
- **Cycle: days to weeks for the first dollar, months for a meaningful commit [HYPOTHESIS]**.
- **The structural risk:** a CLM vendor is a competitor with a make-or-buy decision, not a
  customer. Every feature we ship that they value is a feature they can justify building.

## 5. Budget evidence

Money exists in the segment, though not necessarily *for us*. Legal tech raised **$4.28bn across
107 rounds** or **$5.99bn with fourteen $100m+ rounds** in 2025, depending on tracker
([Artificial Lawyer](https://www.artificiallawyer.com/2026/01/06/legal-tech-raised-6bn-in-2025-as-ai-boom-shows-divisions/),
[Crunchbase News](https://news.crunchbase.com/venture/ai-legal-tech-investment-all-time-high-filevine/)).
**[VERIFIED]** that these figures were published; the trackers disagree by 40%, which tells you
how much weight to put on either. The LegalTech Fund closed a **$110m second fund** in Nov 2025
([LawSites](https://www.lawnext.com/2025/11/the-legaltech-fund-closes-110-million-second-fund-nearly-4x-its-first.html))
**[VERIFIED]**.

**No evidence found** of any legal-AI company disclosing what it spends on third-party document
or extraction infrastructure. That is the number that would actually validate H2 and it is not
public.

## 6. Portfolio size

Not applicable directly — builders hold their customers' corpora. The only scale figure I could
open is Sirion's marketing claim of **7m+ contracts worth nearly $800bn across 1m+ suppliers and
customers in 100+ languages** ([GlobeNewswire](https://www.globenewswire.com/news-release/2025/11/05/3182060/0/en/2025-CCM-Benchmark-Report-Highlights-the-Importance-of-Contracting-Maturity-Amid-Global-Uncertainty.html))
**[VENDOR CLAIM]**. It is the right order of magnitude for what a substrate under a CLM vendor
would have to ingest, and it is a warning about unit economics at $0.09/doc.

## 7. Falsifiable customer-1 hypothesis

> We believe **venture-funded contract/legal-AI startups with 5–40 engineers who already ship a
> citation feature**, currently **maintain an in-house parse→chunk→embed→cite pipeline plus a
> hand-built eval set**, to answer **"show the customer the exact sentence, and don't let a
> deleted document leave stale facts behind"**, and would pay **$2k–$15k/month** for a hosted
> substrate with span-enforced provenance, reversible resolution and cascading deletion.
>
> **FALSIFIED IF:** in 10 interviews with such teams, ≥7 say the grounding layer is *core IP* they
> will not outsource; **or** fewer than 3 have ever had a customer escalate an unsupported-citation
> incident; **or** ≥5 say their existing stack (a parsing API + pgvector + a reranker) already
> satisfies their customers' evidence requirements; **or** none will put a number on what they
> currently spend on that layer.
>
> **Additional pre-registered falsifier from the Zuva evidence:** if fewer than 2 of 10 are
> willing to sign a paid pilot within 60 days, treat H2 as falsified regardless of enthusiasm.

## 8. Five interview questions

1. **"Tell me about the last time a customer challenged an answer your product produced. What did
    you have to show them, and how long did it take to reconstruct?"** *Good:* an incident, a
    ticket, a change they shipped afterwards. *Bad:* "our citations are solid".
2. **"Walk me through what happens in your system today when a customer deletes a document. What
    exactly gets removed, and how do you know?"** *Good:* they describe a real cascade, or admit
    honestly that embeddings and caches go stale. *Bad:* "it's soft-deleted" with no follow-up.
3. **"How many engineer-weeks went into your parsing and citation layer in the last year, and
    what broke most often?"** *Good:* a number and a named failure (scanned PDFs, tables,
    amendments). *Bad:* "we use LlamaIndex".
4. **"The last time you upgraded the underlying model, what regressed, and what did you have to
    re-check by hand?"** *Good:* a concrete regression and a manual re-review. *Bad:* "it just got
    better".
5. **"What line items on your AWS/vendor bill are for document processing, and what would you
    have to see to move one of them to a third party?"** *Good:* a number and a stated condition
    (SOC 2, self-hosting, a price per document). *Bad:* "we'd never outsource that" — which is
    itself a clean falsification signal, so record it.

---

# S3 — EU financial entities and the DORA register of information

## 1. The strongest pain, as a recurring event

**Trigger — the annual register of information submission.** Regulation (EU) 2022/2554 (DORA)
Article 28(3) requires financial entities to maintain a register of information on **all**
contractual arrangements for the use of ICT services from third-party providers, at **entity,
sub-consolidated and consolidated** level. The structure and content are fixed by Commission
Implementing Regulation (EU) **2024/2956**, published in the OJ on 2024-12-02, with templates in
**Annexes I–IV**, including supply-chain and subcontracting information
([EUR-Lex](https://eur-lex.europa.eu/eli/reg_impl/2024/2956/oj/eng),
[Norton Rose Fulbright](https://www.nortonrosefulbright.com/en/inside-fintech/blog/2024/12/published-in-oj-dora-implementing-regulation-on-standard-templates-for-the-register-of-information)).
**[VERIFIED]** for the existence, citation and annex structure. **I could not open the EUR-Lex
full text** — both `CELEX:32022R2554` and the ELI URL returned empty bodies to my fetcher — so the
verbatim wording of Art. 28(3) and Art. 30 is **[NOT VERIFIED]** and must be read before this is
used in a sales conversation.

**Cadence:** competent authorities were required to report registers to the ESAs by **30 April
2025**, with national submission deadlines earlier and varying — 31 March (AT), 4 April (IE),
10 April (BE), 15 April (LU), 22 April (ES)
([EBA press release](https://www.eba.europa.eu/publications-and-media/press-releases/esas-announce-timeline-collect-information-designation-critical-ict-third-party-service-providers),
[CSSF](https://www.cssf.lu/en/2025/04/dora-submission-timeframe-for-register-of-information-edesk-portal-open-as-of-1-april-2025/),
[DNB](https://www.dnb.nl/en/sector-news/supervision-2025/dora-reporting-dora-registers-of-information-in-april-2025/)).
**[VERIFIED]**. The register also feeds the ESAs' designation of **critical ICT third-party
service providers**, so its contents have supervisory consequences beyond the filing itself.

This is the only segment here with a **dated, statutory, annually recurring, cross-contract
event**. Everything else in this document is episodic.

## 2. The current workaround and what it costs

**Measured failure of the current approach.** ESAs summary report *Key findings from the 2024 ESAs
Dry Run exercise*, ESA 2024 35, 17 December 2024
([PDF](https://www.eba.europa.eu/sites/default/files/2024-12/c1454b59-15cc-445e-be14-966e3338cedc/ESA%202024%2035%20DORA%20Dry%20Run%20exercise%20summary%20report%20for%20publication.pdf)) —
I extracted and read the text. All **[VERIFIED]**:

- **1,039 financial entities** across all 27 Member States submitted registers by 2024-08-30;
  most submitted on a consolidated basis, so the registers **covered 3,447 financial entities**.
- **116 data-quality checks** were run on every register that passed technical integration.
- Of **947** registers analysed, **6.5% passed all checks**; 50% of the remainder failed fewer
  than five.
- **86% of all data errors were missing mandatory information.**
- The **next most frequent failure was unique identifiers** for the financial entities and their
  ICT third-party providers — LEI was mandatory for the financial entities, while providers could
  be identified by other identifiers.
- Error rates by entity type, as a proportion of data points submitted: credit institutions
  **1.9%**, investment firms **2.4%**, insurance/reinsurance **3.3%**.

Two of those bullets map onto this product's two stated differentiators almost exactly. *Missing
mandatory information* is a coverage-and-provenance problem: every field must come from somewhere
in a contract, and somebody must be able to point at where. *Identifier failures* is an entity
resolution problem, and DORA makes LEI the canonical identifier — the same identifier our
acceptance test already measures coverage against
(`pipeline-comparison-and-acceptance.md` §2.3, "LEI/CIK coverage on the partner's corpus").

**What it costs.** Rubrik Zero Labs / Wakefield Research surveyed **350 CISOs** at finance and
banking companies with 500+ employees: **47% of UK respondents and 38% of EU respondents spent
over €1m** on DORA compliance; a further 28% (UK) and 30% (EU) spent €501k–€1m
([Infosecurity Magazine](https://www.infosecurity-magazine.com/news/dora-compliance-costs-soar/)).
**[VENDOR CLAIM]** — vendor-sponsored, and the respondents are CISOs, who may not own the register.

The claims that Deloitte found most institutions at €2–5m, that McKinsey found €5–15m, and that
**46% cite the register of information as their biggest hurdle**, appear only in secondary
aggregations I could not trace to a primary report. **[NOT VERIFIED]** — the 46% in particular is
the number I most want and least trust.

## 3. Why existing tools fall short

GRC and third-party-risk platforms hold *vendor* records; the register requires **contract-level**
facts — arrangement dates, termination notice periods, governing law, data locations, subcontracting
chains, function identifiers — which live in the PDFs and their amendments, not in the vendor master.
**[HYPOTHESIS]** — I did not find a buyer saying this in their own words, and the many "DORA
register" vendor pages I found are marketing. The ESAs' 86%-missing-mandatory-information finding
is *consistent* with this explanation but does not establish it: the fields could equally be
missing because nobody was asked to fill them.

**No evidence found** of a financial entity publicly describing how it built its register.

## 4. Buyer vs user, and procurement path

- **Signs:** Head of ICT Third-Party Risk, CISO, or COO, spending from a named DORA programme
  budget. **[HYPOTHESIS]**
- **Works in it:** TPRM analysts, with legal doing the contract reading, and regulatory-reporting
  staff doing the XBRL/CSV conversion. **[HYPOTHESIS]**
- **Path:** regulatory-change budget → security and outsourcing review (which, for a regulated
  financial entity, means *we* become an ICT third-party arrangement subject to Art. 30 contract
  terms and enter their own register — a real friction we should price in). **[VERIFIED]** that
  DORA imposes contractual requirements on ICT providers; **[NOT VERIFIED]** as to the specific
  Art. 30 clause list, since I could not open the regulation text.
- **Cycle: 3–9 months [HYPOTHESIS]**, compressed near the April deadline.

## 5. Budget evidence

- **[VENDOR CLAIM]** Rubrik/Wakefield, above: the €1m band, n=350.
- **[VERIFIED]** The regulatory machinery is real and funded at EU level: the dry run involved
  1,039 entities, workshops, a data-point model, taxonomy and conversion tooling, all published by
  the ESAs.
- **No evidence found** of procurement records for DORA-register-specific contract-data tooling in
  EU TED, and I did not successfully query TED for this pass. That is a gap worth closing before
  committing to this segment.

## 6. Portfolio size

**No verified figure found** for the number of ICT contractual arrangements a typical financial
entity holds. A secondary source attributes "an average of 147 ICT third-party arrangements" to a
2024 EBA survey ([Rescana](https://www.rescana.com/learn/frameworks/dora-third-party-risk/)) —
I could not locate that EBA survey. **[NOT VERIFIED]**, and I would not repeat it.

What *is* **[VERIFIED]** is the scale of the reporting population: 1,039 submitting entities
covering 3,447 financial entities in a *voluntary* dry run, against a mandatory population of all
EU banks, insurers, investment firms, payment and e-money institutions.

## 7. Falsifiable customer-1 hypothesis

> We believe **EU financial entities with >€10bn assets that failed data-quality checks on their
> 2025 or 2026 register submission**, currently **hand-compile the register into spreadsheets from
> procurement systems plus manual contract reading, then convert to CSV/XBRL**, to answer
> **"for every ICT contractual arrangement, as amended, what are the mandatory Annex I fields and
> which sentence of which contract supports each"**, and would pay **€75k–€250k/yr** for a
> field-level register feed where every value carries its source span and every provider name is a
> resolved, LEI-linked entity with a reversible merge history.
>
> **FALSIFIED IF:** in 10 interviews with ICT third-party risk leads, ≥6 say the register is
> populated from the vendor master and procurement system rather than from contracts; **or** ≥6
> say their competent authority's feedback contained no material findings; **or** none can name a
> budget owner distinct from the general DORA programme; **or** the 2026 ESAs feedback shows
> aggregate pass rates above ~70%, which would mean the industry solved it with spreadsheets and
> the window has closed.

## 8. Five interview questions

1. **"Walk me through April 2025. Who assembled the register, from what systems, and how many
    people touched it?"** *Good:* named systems, a headcount, a date the spreadsheet froze.
    *Bad:* "compliance handled it".
2. **"What did your competent authority come back with after your submission, and what did you
    have to fix?"** *Good:* specific failed checks, a remediation list, a deadline. *Bad:* "we
    haven't heard anything" — which is also informative, and a falsifier.
3. **"For the fields you had to read out of contracts — termination notice, governing law,
    subcontracting, data location — how did you get them, and how do you know they're right
    today?"** *Good:* a named person reading PDFs, or an abstraction vendor and an invoice.
    *Bad:* "they're in the system".
4. **"Tell me about the last time a provider was renamed, acquired or novated. How did you find
    every arrangement affected, and how long did it take?"** *Good:* a specific corporate event
    and a manual reconciliation. *Bad:* "our vendor master handles that".
5. **"What did you spend on the register specifically last year — consultants, tooling, internal
    days — and who approved it?"** *Good:* a number and a name. *Bad:* "it's part of the DORA
    programme".

---

# Where the evidence is thin

Read this section before quoting anything above.

1. **No primary source measures the frequency of cross-contract trigger events for S1.** The whole
   H1 story rests on EY's "90% have difficulty locating contracts" plus law-firm alerts. That is
   evidence of *latent* difficulty, not of a recurring, budgeted, painful event. This is the single
   biggest hole in this pass.
2. **The two headline value-leakage numbers (9.2%, 11%) are unverified.** Both trace to WorldCC
   studies I could not open. They are in every CLM deck and they should not be in ours.
3. **WorldCC benchmark reports are members-only.** The 2023 (700+ organisations, 70+ countries),
   2025 CCM (1,041 organisations) and US Government 2026 (574 respondents) reports exist and their
   sample sizes are listed publicly, but the findings are behind registration. I used only the
   press release. A membership would materially improve this document.
4. **CLOC's 2025 SOTI PDF is an image scan.** I could not extract its contract-management detail.
   Someone should read it with OCR.
5. **The ACC 2026 CLO survey page returned 403.** The "30% cite trade and tariffs" figure is
   unconfirmed.
6. **I could not open the DORA regulation text itself.** Everything about Art. 28(3)/Art. 30 here
   is from the implementing regulation's structure and secondary legal commentary. Fix before use.
7. **UK Contracts Finder's OCDS keyword search did not work** for me — it returned notices
   unrelated to the query. So there is *no* UK public-procurement evidence in this document, and
   none of the EU TED evidence the ticket asked for. Both remain open.
8. **No public figure exists for what any legal-AI company spends on document infrastructure.**
   H2's budget question is therefore unanswered by public data; only interviews can settle it.
9. **Installed-base contract counts are missing everywhere.** EY gives annual flow (19,000/yr);
   nobody gives stock. Our ingestion cost model depends on stock.
10. **Build-cost figures for S2 ($40k–$120k, 6–16 weeks) come exclusively from vendors selling the
    alternative.** Treat as advertising.
11. **Pharma and insurance were not disproved — they were not investigated to a conclusion.** I
    found nothing at the quality bar in the time available. "No evidence found" here means
    "I looked briefly", not "it isn't there".

---

# Blunt assessment

## Ranked by strength of evidence that the pain is real and recurring

1. **S3 (DORA).** A regulator names the artefact, fixes the fields, sets an annual deadline, and
   **published a measurement of how badly the industry did it**: 6.5% passing, 86% of errors being
   missing mandatory data, identifiers the next worst. Nobody else in this document has an external
   party quantifying their failure.
2. **S2 (builders).** The *technical* pain is the best-evidenced thing here — 2,046 judicial
   findings, and a preregistered Stanford study showing 17–33% hallucination against "hallucination-
   free" marketing. Recurring, consequential, documented.
3. **S1 (legal ops).** Large, chronic, extremely well surveyed — and chronic is the problem. EY's
   90%/78%/71% describe a condition people have lived with for a decade, not an event that forces a
   purchase this quarter.

## Ranked by strength of evidence that money moves

1. **S1.** Unambiguous. A $28.5bn ALSP market, 57% of law departments using one, and primary US
   federal awards of $1.33m (Icertis), $778k (CLM SaaS), $618k (Agiloft). The money is demonstrably
   spent on this problem, at these prices, by organisations of this shape.
2. **S3.** Plausible and large, but the only cost evidence is a vendor-sponsored CISO survey and a
   chain of untraceable Deloitte/McKinsey figures. **No procurement record found** for a
   register-specific contract-data tool.
3. **S2.** Weakest, and the evidence actively points the other way. The price anchor is ~$1.25 a
   document. The best-funded attempt at exactly this product — Zuva, out of Kira, with Insight
   money and a decade of models — started as a developer API and has moved up-stack twice, now
   leading with sell-side M&A diligence. The exits (Evisort $311m, Lexion $165m) went into
   application platforms. Venture money is pouring into legal tech, but into *applications*.

## Who I would talk to first

**S3 — EU financial entities whose 2025 or 2026 register drew data-quality findings.** Ten
interviews, starting with entities in jurisdictions whose regulators published feedback.

Why, plainly:

- It is the only segment with a **dated recurring event** and a **published measure of failure**.
- The two failure modes the ESAs measured — missing mandatory fields, and identifier errors —
  are, respectively, the provenance problem and the entity-resolution problem this product is
  built around. **LEI is the canonical identifier**, and our acceptance test already measures LEI
  coverage. That is not a coincidence we engineered; it is a fit we can test cheaply in week one.
- The deliverable is a **filing, not an answer**, which makes the pilot's success condition
  objective: fewer failed checks. No inter-annotator agreement argument, no "is this answer good".
- It is small enough to be a wedge and adjacent enough to S1 to expand into: an entity that can
  answer register questions across ICT contracts can be asked the same questions about every other
  contract class.

**The honest caveat on that choice:** S3's *money* evidence is the second-weakest of the three. I
am recommending the segment with the best pain evidence and mediocre budget evidence over the
segment with the best budget evidence and mediocre pain evidence. That trade is defensible only
because the pain evidence is *external and quantified* — and it is exactly what the first three
interviews should attack.

## What would change my mind

- **Toward S1:** if 5 of 10 legal-ops interviews produce a dated cross-contract question from the
  last 12 months that consumed >3 person-days *and* a named budget owner. The budget is already
  proven; only the event is missing. If the event shows up, S1 becomes first choice immediately,
  because it is the larger market and the procurement path is worn smooth.
- **Away from S3:** if the 2026 ESAs feedback shows pass rates recovering above ~70%, or if ≥6 of
  10 interviewees say the register is populated from the vendor master rather than from contracts.
  Either kills it. The first is checkable without interviews — **check it before booking any.**
- **Toward S2:** if ≥3 of 10 builders will sign a paid pilot inside 60 days. Enthusiasm without a
  signature in this segment means nothing; Zuva had enthusiasm.
- **Away from everything:** if in 30 total interviews nobody describes an incident where a *wrong
  or unsupported* answer had a consequence, then span-level evidence is a feature nobody is
  buying, and the wedge is wrong regardless of segment.

## One thing this pass could not do

Neither hypothesis is confirmed and neither is dead. H1 has money without a proven event. H2 has a
proven technical problem with a named precedent for the business model failing. S3 has an event and
a regulator-measured failure with unproven money. **That is a three-way tie that only interviews
break**, which is the correct outcome for a desk-research pass — and it is why §"Five interview
questions" appears three times above rather than once.
