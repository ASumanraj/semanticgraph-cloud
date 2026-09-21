# Contract-AI market and the first customer — synthesis

**T-907 · 2026-09-21.** Built from two source-level passes:
[`contract-ai-vendors.md`](contract-ai-vendors.md) (what eight vendors document) and
[`contract-ai-buyers.md`](contract-ai-buyers.md) (three customer segments). This file reconciles
them and takes a position. Read the "evidence gaps" section before quoting anything.

Labels: **[verified]** a primary source states it · **[checked here]** re-verified while writing this
· **[agent-reported]** from a research pass and not re-checked · **[vendor claim]** ·
**[hypothesis]**.

---

## Bottom line

1. **Neither hypothesis is confirmed and neither is dead.** Desk research cannot pick customer one;
   the buyer pass itself calls it a three-way tie that only interviews break.
2. **Two of the plan's six differentiators are weaker than the plan says.** Amendment linking is
   already shipped by three vendors, and tenant isolation is invisible to a buyer who holds a SOC 2.
   Strike both from the pitch.
3. **The defensible claim is narrower and different in kind.** No vendor exposes the evidence
   span, the resolution decision, or the deletion cascade *as data an engineer can build on*, and no
   vendor documents a point-in-time query. That is a property of a **record**.
4. **That points at builders, and builders are where a named precedent failed.** Zuva built exactly
   the developer API and moved up-stack twice. The vendor evidence favours H2; the business evidence
   punishes it. Do not resolve that by choosing the comfortable reading.
5. **Before booking any interview, run four free checks** (below). One of them can kill the
   strongest candidate segment in an afternoon.

---

## Where the two passes disagree

| Question | Vendor pass says | Buyer pass says |
|---|---|---|
| Which hypothesis do the differentiators support? | **H2** — none of the incumbents' answer surfaces is a gap; the *unexposed evidence, decision and deletion data* is | H2 has **the weakest** business evidence: Zuva (Kira spin-out, decade of data) launched a developer API and moved up-stack twice; exits went into application platforms |
| Is legal-ops portfolio Q&A open? | Not really — Workday, CoCounsel and LinkSquares all ship a credible answer surface; CoCounsel's tabular analysis may satisfy most portfolio questions | The money is real — US federal awards to Icertis, Agiloft and others — but no source shows the cross-contract *event* recurs |
| Which segment first? | — | **S3, EU financial entities and the DORA register**, on pain evidence; S1 on money evidence |

Both are right about what they measured. The synthesis is that **the product's kernel suits builders
and its business case is proven only for finished applications**, so the real question is whether
customer one buys a *record* or a *filing built from one*.

---

## What survives the competitor review

| Differentiator | Verdict | How to say it |
|---|---|---|
| **Character spans** | Still unique — but only as *data* | "The span is a field your code can read." Several vendors highlight a sentence in the UI; **no API in the set returns a citation with a location**. Never pitch "we highlight the source" |
| **Assertion-counted deletion** | Unclaimed and under-rated | A compliance claim: every vendor has `DELETE`, none documents what happens to extracted fields, embeddings, dashboards or LinkSquares' generated restated agreement. Checkable with one SQL query in front of privacy counsel; a week-five question, not a week-one one |
| **Point-in-time temporal query** | Open | "What was in force on date X, and which amendment superseded it." Ironclad gives two states, Icertis a history a human reads, LinkSquares a regenerated document; none documents an as-of query |
| **Immutable ontology versions** | Reframe | Configurable fields are table stakes and Workday does them well. What nobody documents is what happens to old values when a field definition changes. Pitch "your Q1 and Q3 numbers came from the same rules, provably" |
| **Retractable resolution log** | Real, unasked | Incumbents avoided automated resolution (their entity hierarchies are manual), so no buyer has been burned by an over-merge. Defensible in a demo; not a reason to take the first meeting |
| **Amendment linking** | **Partly taken — drop it** | Ironclad documents a non-destructive rollup with revert. **[checked here]** Ironclad's own help pages confirm it, with limits: *properties roll up, not clauses*, and of the lifecycle fields only the expiration date. LinkSquares generates restated text; Icertis allows chains |
| **Database-enforced isolation** | Cost of entry | Harvey publishes SOC 2 Type II, ISO 27001/27701/42001, named residency regions and contractual zero data retention. A questionnaire is answered by the certificate, not the DDL |

Two open risks the plan has not priced: **Docusign** has the best ingest position and an explicit
strategy of being the substrate under Harvey, Legora and CoCounsel, and its developer docs could not
be read by the research agent; and a **filterable table** (CoCounsel's tabular analysis) may already
answer most real portfolio questions, which is the vector-RAG baseline problem in its contracts form.

---

## The three segments

| | **S1 · legal-ops / procurement portfolios** | **S2 · builders of contract/legal AI** | **S3 · EU financial entities, DORA register** |
|---|---|---|---|
| Pain is real and recurring | Chronic, well surveyed (EY/Harvard n=1,000: 90% find locating contracts hard, 78% don't track obligations) — a condition people have lived with for a decade, **not a forcing event** | Best-evidenced *technical* pain: Stanford's preregistered study (17–33% hallucination against "hallucination-free" marketing) | **Dated, statutory, annual, and a regulator measured the failure** |
| Money moves | **Strongest**: public US federal awards ($1.33m Icertis to DHS, $778k CLM SaaS, $618k Agiloft) **[agent-reported]** | **Weakest**, and against: ~$1.25/document anchor and the Zuva precedent **[agent-reported; the pricing page was unreachable when I checked]** | Plausible, **no procurement record found** |
| Existing tools | Credible incumbents already there | Docusign as substrate is the risk | GRC/TPRM tooling — **not researched** |
| Buyer ≠ user? | Yes | Same team | Yes |

**S3's headline evidence is real. [checked here]** The ESAs' 2024 dry-run summary, confirmed across
the ESAs' own pages: **6.5% of registers passed every one of 116 data-quality checks; missing
mandatory information caused 86% of errors; the next most frequent failure was improper unique
identifiers, with the LEI mandatory** for financial entities.

**Three things temper it, and the buyer pass did not weigh them enough:**

1. **"Missing mandatory information" is not evidence that the fields live in contracts.** Many
   register fields come from procurement systems, vendor masters or internal assessments, not
   contract text. The buyer pass lists this as a kill condition; it should be tested before, not
   after, ten interviews. The claim that these errors "are literally the provenance problem" is the
   research agent's interpretation.
2. **The real competitors in S3 are DORA-compliance and third-party-risk tools, not contract-AI
   vendors, and nobody has compared them.** "Existing tools are insufficient" is unsupported here.
3. **S3 is the most certificate-demanding customer there is, and the plan defers certificates.**
   A financial entity buying from us is likely to record us as an ICT third-party provider in its own
   register, with the regulation's contractual requirements applying to our agreement **[hypothesis —
   the regulation text could not be opened by the research agent; read it before relying on this]**.
   A pre-alpha company with no SOC 2 selling into that is a mismatch worth naming now.

---

## What I recommend

**Do not pick a segment. Run four free checks first, in this order, then interview.**

1. **Classify the register's mandatory data points by source** — contract text, system of record,
   or internal assessment — using the ESAs' published data-point model. If fewer than roughly a
   third are contract-derived, S3's contract-knowledge story is small. *(The threshold is my
   judgement; set it before looking.)* Half a day.
2. **Read the 2026 ESAs feedback on register quality.** If aggregate pass rates have recovered above
   about 70%, the window has closed and no interview is needed to know it.
3. **Read Docusign's developer documentation in a browser.** It is the most likely channel partner
   and the most likely to close the gap by default.
4. **Look at CoCounsel's tabular analysis against a real portfolio question**, if a trial is
   obtainable, before a buyer does it for you.

Then interview, and **let the falsifiers decide**:

- **Toward S1** if 5 of 10 produce a dated cross-contract question from the last 12 months that took
  more than three person-days *and* name a budget owner.
- **Toward S2** if 3 of 10 builders will sign a paid pilot within 60 days. Enthusiasm without a
  signature is meaningless here; Zuva had enthusiasm.
- **Away from S3** if 6 of 10 say the register is populated from the vendor master, or the 2026
  pass rate is above about 70%.
- **Away from everything** if across about 30 interviews nobody describes an incident where a wrong
  or unsupported answer had a consequence. Then span-level evidence is a feature nobody is buying,
  and the wedge is wrong whatever the segment.

Thirty interviews is a lot for one founder. **Start with five per segment**; the purpose is to
falsify, and the checks above may remove a segment before you finish.

**Packaging is one decision, not three architectures.** The kernel — span as data, decision log,
deletion cascade — is the same for every segment. S2 gets it as an API; S3 would get a
register-shaped view on top of it. The plan's API-first shape survives either way.

---

## The customer-one hypothesis

Stated for S3 because it has the only externally measured failure, and **conditional on check 1**:

> We believe **EU financial entities that failed data-quality checks on a register submission**,
> currently **hand-compile the register from procurement systems and manual contract reading**, to
> answer **"for every ICT contractual arrangement, as amended, what does each mandatory field say
> and which sentence supports it."** They would pay **€75k–€250k a year** for a field-level feed
> where every value carries its source span and every provider is a resolved, LEI-linked entity with
> a reversible merge history.
>
> **Falsified if** any one holds: at least a third of the mandatory fields are not contract-derived
> (check 1); 2026 pass rates exceed about 70% (check 2); 6 of 10 interviewees populate the register
> from the vendor master; or none can name a budget owner distinct from the general DORA programme.

**[hypothesis]** The price band comes from the buyer pass, which found no procurement record to
support it. The alternatives for S1 and S2, each with its own kill condition, are in
`contract-ai-buyers.md`.

## Five interview questions, for any segment

These ask about the past. Each has a bad answer to listen for.

1. **"Tell me about the last time someone needed an answer that required reading many contracts, or
   many versions of one, at once. What was the question and who was asking?"** *Bad:* a general
   complaint with no date.
2. **"How did you get the answer, how long did it take, and how did you know it was right?"**
   *Bad:* "our system handles that."
3. **"Has a wrong or unsupported answer ever had a consequence? What happened?"** *This is the
   question that can kill the whole wedge.* *Bad:* "no, we double-check everything" with no example.
4. **"What did you spend on this last year — tools, services, people-days — and who approved it?"**
   *Bad:* "it's part of a larger programme."
5. **"When a contract was deleted, amended, or a counterparty was renamed or acquired, what
   happened to everything derived from it?"** *Bad:* "it just updates."

Segment-specific sets, with good and bad answers, are in the buyer pass.

---

## What this changes in the repo

- **Pitch language:** remove "nobody links amendments" and any "we highlight the source" claim; add
  "the span is data", "as-of queries" and the deletion cascade as a compliance claim. Done in
  `ENTERPRISE_PLAN.md` Part 0.1 for amendments' sibling claims; the amendment point is new here.
- **T-904:** the clause-type shortlist should include contract-derived register fields once check 1
  identifies them.
- **T-908 (new):** checks 1 and 2 as a research ticket.
- **The acceptance protocol** should compare against a filterable-table baseline as well as the wiki
  and vector baselines.

## Evidence gaps — read before quoting

1. **No primary source measures how often S1's cross-contract trigger occurs.** The biggest hole.
2. **The 9.2% and 11% value-leakage figures are unverified** and traced to members-only WorldCC
   studies. Keep them out of any deck.
3. **The DORA regulation text was never read** by the research agent (EUR-Lex returned empty).
   Everything about Article 28(3) and Article 30 is unverified.
4. **No UK or EU procurement evidence** — the keyword searches failed.
5. **No public figure for what any legal-AI company spends on document infrastructure.** H2's budget
   question can only be settled by interviews.
6. **Installed-base contract counts are missing everywhere.** Our ingest cost model depends on the
   stock of contracts, and nobody publishes it; ask in interviews.
7. **The Zuva pricing and the Workday and Docusign acquisition prices ($311m and $165m) are
   [agent-reported]**; I could not open Zuva's pricing page when I checked.
8. **Several vendors' help sites block automated fetch** (LinkSquares, Ironclad's support site,
   Sirion, Litera, Docusign's developer site). Claims from those are marked as index-verified or not
   verified in the vendor pass.
9. **Pharma and insurance were not investigated to a conclusion.** "No evidence found" there means
   "looked briefly."
10. **No vendor-neutral benchmark exists** for portfolio Q&A, amendments, resolution or citation
    granularity. A design partner's sealed holdout is therefore the only evidence available — for us
    and for every competitor.
