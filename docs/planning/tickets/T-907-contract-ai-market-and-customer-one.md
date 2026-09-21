# T-907 · Contract-AI market: who is customer one?

**Stage** — · **Type** research · **Status** done · **Owner** claude · **Branch** `t-907-contract-ai-market`

**Scope**
- `docs/research/**`

**Blocked by** — · **Blocks** the choice of design partners (T-904 needs a reviewer; this decides whose documents)

## Question

The plan compares GraphRAG vendors, which is not the market a contracts customer lives in. Their
real alternatives are contract lifecycle management suites, contract-analytics tools and
LLM-native legal AI. Nothing so far shows who the first customer is, what they do today, or
whether they would pay for an auditable contract knowledge layer.

**Hypothesis under test — not yet a market gap:**

> Legal-operations or procurement teams managing large agreement portfolios need trustworthy
> answers across contracts, amendments, counterparties and time — not just clause extraction
> from one document.

A second hypothesis has to be tested against it, because the plan's declared wedge is a
developer-platform API rather than an end-user product:

> Teams *building* contract or legal-AI products need a substrate that provides span-level
> evidence, reversible resolution and precise deletion, and would rather buy it than build it.

## Method

Two research passes, then a synthesis written here:

1. **Vendors** — six to eight contract-AI products across four archetypes (lifecycle suites,
   contract analytics, LLM-native legal AI, platform-embedded), compared from primary sources on
   portfolio questions, amendments, entity resolution, temporal queries, evidence granularity,
   deletion and audit, APIs, integrations, and deployment including self-hosted and air-gapped.
2. **Buyers** — three customer segments, the trigger events that force cross-contract or
   time-based questions, the current workaround, and any evidence of budget.

Every claim carries one of four labels: **verified** (a primary source says it), **vendor claim**,
**practitioner report** (anecdotal), or **hypothesis**. A feature is not called a market gap
until the evidence supports it, and "not documented" is an answer.

## Resolution

Done 2026-09-21. Reports in `docs/research/`: `contract-ai-vendors.md`,
`contract-ai-buyers.md` and the synthesis `contract-ai-market-and-customer-one.md`.

**Neither hypothesis is confirmed, and none is dead.** The vendor pass favours builders (no
vendor exposes evidence spans, resolution decisions or deletion as data); the buyer pass finds
the weakest business evidence for builders (Zuva's developer API moved up-stack twice) and the
best pain evidence in EU financial entities compiling the DORA register of information. Two plan
differentiators are weaker than stated: amendment linking is partly shipped by three vendors, and
database-enforced isolation is invisible next to a SOC 2 certificate.

Decision: do not pick a customer yet. Run four free checks first (T-908 covers the first two),
then five interviews per segment with the falsifiers written in the synthesis. Claims that were
not verified are listed there under "Evidence gaps".
