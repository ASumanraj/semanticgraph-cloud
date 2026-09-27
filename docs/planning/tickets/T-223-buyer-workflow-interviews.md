# T-223 · Test real recent workflows with buyers before building a lifecycle layer

**Stage** — · **Type** research · **Status** open · **Owner** — · **Branch** `t-223-buyer-workflow-interviews`

**Scope**
- `docs/research/**`

**Blocked by** — · **Blocks** any ticket for an obligations, recurrence or lifecycle layer

## Question

[`evidence-first-temporal-contract-graph-prior-art.md`](../../research/evidence-first-temporal-contract-graph-prior-art.md)
found no publicly documented system that combines evidence spans, as-of history, reversible merges and
assertion-counted deletion over a contract portfolio. It also found no evidence that a buyer needs the
combination. This ticket tests whether anyone does, using their own recent work.

**Hypothesis under test, not settled:** when a source document, amendment, counterparty or rule changes,
some team must find what that affects and prove the answer from the source, and they cannot do it well today.

## Method

Five interviews per segment; the segments are hypotheses ranked in the prior-art note: (a) EU data-practice
law firms or in-house counsel facing the Data Act's 12 Sep 2027 window for existing contracts; (b) DPOs
maintaining sub-processor lists; (c) credit operations handling amended and restated credit agreements.
Add the builder segment from T-907 if a contact exists.

Ask about one **actual recent** case, never the graph idea. For each interview record: what source changed;
how it was handled today, and how long it took; which decisions or people it affected; what evidence they
had to produce, and to whom; who owns the budget; whether they would run a pilot on their own documents, and
what would stop them. Do not demo a graph first. Record roles and organisation types, not names, and no
document text.

Also run these as concrete offers, each with a pass criterion set **before** the first call:

1. Data Act: a one-week test on 30 redacted contracts with source-cited results. Pass: at least three send
   real contracts and one names a budget owner within 30 days.
2. Sub-processors: ask 10 DPOs for their list and three DPAs and answer "who changed since last quarter".
   Pass: at least three supply data and one asks for a recurring feed.
3. Covenants: ask eight credit-ops contacts for one anonymised amended-and-restated agreement and its
   compliance-certificate history. Pass: the reviewer agrees our answer for the covenant level at the test
   date and the superseding text.

## Acceptance

- [ ] A one-page interview guide and the pass/fail criteria written and committed before any interview
- [ ] At least five interviews in one segment, each recorded against the questions above (roles only)
- [ ] A findings note saying, per segment, what the current process is, what a change costs, who pays, and whether the four guarantees mattered to the buyer or were nice-to-have, with quotes marked as such
- [ ] An explicit go / no-go for a lifecycle layer, naming the falsifier that decided it

## Notes

DORA clause-gap checking is not a valid pitch on its own: several vendors sell it, and one verifies quotes
and records human sign-off (prior-art note, section 8). It is acceptable as one workflow inside a wider
test. Do not describe the product as "first" in any outreach.
