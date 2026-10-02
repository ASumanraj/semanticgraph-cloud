# T-223 · Buyer-workflow interview guide and decision rules

**Status:** draft for the founder's approval. The acceptance criteria of
[T-223](../planning/tickets/T-223-buyer-workflow-interviews.md) require this guide and its pass/fail
rules to be committed **before the first interview**. Thresholds marked *(proposed)* are the
reviewer's suggestion and need the founder's sign-off, or changes, before any call is made.

## 1. What this is for

One question: **does anyone have a recent, costly, repeated problem of finding what a change affects
and proving the answer from the source, badly enough to try something new?** It is not a sales call,
a demo, or a survey of opinions about our ideas. We learn from what people *did*, not what they say
they would do.

Hypotheses under test (from `evidence-first-temporal-contract-graph-prior-art.md` and T-907):
a change (a document, an amendment, a counterparty, a rule) forces a team to find and prove what it
affects; the current process is slow or error-prone; someone owns a budget for it. Each can be wrong.

## 2. Rules for the interviewer (read before every call)

1. **Ask about the last time, not about the future.** "Tell me about the last time X happened." Never
   "would you use…" or "would you pay for…". People are bad at predicting their own behaviour and good at
   describing what they did.
2. **Do not pitch, demo or describe the product** until the last five minutes, if at all. One sentence at
   most when asked: "We are researching how teams handle changes across large sets of agreements."
3. **Do not use our vocabulary first.** Not "knowledge graph", "provenance", "bi-temporal", "golden
   record". Use their words. Note which words *they* use.
4. **Do not lead.** Ask "What did they ask you to show?" not "Did they ask for the source text?"
5. **Get specifics:** dates, counts, hours, tools, names of roles. Vague answers ("it's a pain") are
   not evidence; ask "when was the last time, and what happened?"
6. **Silence is a tool.** Let the answer finish. Do not fill gaps with your own idea.
7. **Compliments, opinions and "sounds great" are not data.** Commitments are: an intro to a
   colleague, a redacted example, a second call, a named budget owner, a pilot discussion.
8. **Do not claim anything is "first"** or describe competitors as inadequate. We do not know their
   products from the inside.
9. **Privacy:** record the person's *role and organisation type* only, never names, and never write down
   document text. Do not ask for confidential material on the first call. Offer to sign an NDA before
   any document is shared.

## 3. Who to talk to

Five interviews per segment (T-223). Start with one segment and finish it before starting the next.

| Segment | Who | Trigger events to ask about |
|---|---|---|
| A. Regulatory-change remediation | EU data-practice lawyers, in-house counsel, contract managers | Data Act: existing contracts and the 12 Sep 2027 window; DORA ICT contract updates; SCC replacement; GDPR repapering |
| B. Sub-processor mapping | Data protection officers, privacy counsel | A vendor changes sub-processors; a DPA is replaced; a customer asks "who processes our data?" |
| C. Amended credit agreements | Credit operations, agent-bank staff, fund administrators | An amendment and restatement; a covenant test date; a lender asks what the current terms are |
| D. Builders (from T-907) | Engineers or product owners at teams building contract or legal-AI tools | A customer demands citations or deletion; a model upgrade changes extracted results |

**Screener** (two questions, before booking): "In the last twelve months, did you have to find every
agreement affected by a change, such as a new rule, an amendment, or a vendor change?" and "Roughly
how many agreements were in scope?" Book only people who answer yes. A no is still useful: ask who
does handle it.

**Finding people.** Ask for introductions from your own network first. Then professional communities and
conference speaker lists in each field. Ask each interviewee for two names. Do not scrape or bulk-email;
every first contact is personal and asks for twenty-five minutes of someone's time.

### Outreach message (adapt, keep it short)

> Hello [first name], I am researching how teams handle changes across large sets of agreements, for
> example after a new regulation or an amendment. I am not selling anything. Would you give me about
> 25 minutes to describe the last time this came up for you, and how it was handled? I would keep your
> role and organisation type only, and no names or documents. Happy to share what I learn across the
> conversations. Thank you.

## 4. The interview (25 to 30 minutes)

**Opening (2 min).** Thank them. Say what you are researching in one sentence. Say you are learning
from their experience and have nothing to sell. Ask permission to take notes; do not record audio unless
they agree explicitly.

**A. Context (3 min).** What is your role? What kinds of agreements do you work with, and roughly how
many? Who else is involved when something changes?

**B. The last time (10 min). The core of the interview.**
1. Tell me about the most recent time something changed that meant checking a set of agreements. What
   was the trigger? When was it?
2. How did you find out which agreements were affected? Walk me through, step by step.
3. How many agreements were involved, and how long did it take, start to finish? How many people?
4. What tools or documents did you use at each step?
5. What went wrong, or nearly did? Was anything missed, found late, or redone?
6. Who asked you to prove the result, and in what form? What did they ask to see?
7. How did you deal with amendments, side letters or older versions?
8. How did you know which version or date applied?

**C. Cost and ownership (4 min).**
1. What did that cost you, in hours or money, if you can estimate? What happens if it is wrong?
2. Who decides what is spent on handling this? Who signed off the last tool or service you bought for
   it?
3. When did you last try something new for this? What happened? If nothing, why not?
4. What do you use today, and what do you dislike about it?

**D. Frequency (2 min).** How often does something like this happen? When is the next one?

**E. Commitment probes (3 min). Only after the story.**
- "Who else should I talk to about this?"
- "If I had a redacted example of what such a result could look like, would you look at it?" (an
  offered, specific next step, not a feature description)
- "Would it be useful to talk again in a few weeks?"
Record exactly what they commit to, if anything.

**Close (1 min).** Thank them. Ask if they would like a summary of what you learn.

### Segment add-ons (use only if relevant, after B)

- **A:** Which contracts were in scope of the rule? How did you decide whether an amendment counted as a
  new agreement? How do you track contract dates?
- **B:** How do you know your sub-processor list is current? What happened the last time a vendor
  changed it? Who asks you for the list?
- **C:** How do you determine the current terms after several amendments? How do you test covenants,
  and on which date?
- **D:** What did your customer ask you to show about where an extracted value came from? What happens
  to data derived from a document when it is deleted? Have you tried building this yourself?

## 5. What to record (one row per interview)

Use roles and organisation types only. Do not record names, contact details beyond a coded id, or
document text.

| Field | Notes |
|---|---|
| Interview id, date, segment | e.g. A-03 |
| Role, organisation type and size | |
| Trigger event | What changed, and when (within the last 12 months?) |
| Scale | Agreements in scope; hours; people involved |
| Tools used | |
| What went wrong | |
| Evidence demanded, and by whom | Their words |
| Unprompted mentions | Tick if raised **before** we mentioned it: source text for each finding; the state as of a date; correcting a wrong match between parties; deleting a source and what depends on it |
| Budget owner named | Yes/No, and role |
| Last purchase for this problem | |
| Commitments made | Specific: intro, redacted example, second call, pilot discussion |
| Notable quotes | Marked as quotes, with the role |
| Interviewer notes | What I asked that led the answer |

## 6. Decision rules (set before the first call) *(proposed)*

Judge each segment on its five interviews only, and write the verdict down before reading across
segments.

**Strong signal (continue and consider a pilot) when all of these hold:**
- at least **3 of 5** describe a specific change event within the last 12 months involving at least
  **50 agreements** and at least **16 hours** of work;
- at least **2 of 5** name who holds the budget, or describe buying something for this before;
- at least **2 of 5** make a **specific commitment** (a redacted example, an introduction, or a pilot
  conversation);
- at least **2 of 5** raise at least one of the four guarantees **unprompted** (source text for each
  finding, the state as of a date, correcting a wrong match, deletion).

**Weak or no signal (drop or deprioritise the segment) when any of these holds:**
- **0 or 1** of 5 had a real event in the last 12 months;
- nobody names a budget owner or a previous purchase;
- the only commitments are compliments.

**Mixed** (somewhere between): run five more in the same segment, or reframe the question, and say which.

**What the result decides.** A lifecycle or obligations layer is not built unless a segment shows a
strong signal. A segment with a strong signal gets a pilot offer (T-223's offers), and the benchmark
(T-224) and the capped extraction measurement (T-227) are used to prepare it. If every segment is weak,
we report that plainly and revisit the wedge.

## 7. Bias traps to avoid

- **Confirmation:** hearing "that would be useful" as demand. Count only past events and commitments.
- **Anchoring the answer:** naming a feature in a question. Re-ask neutrally.
- **Friendly samples:** interviewing only people who like us. Include people we do not know.
- **Survivorship:** talking only to those who bought tools. Ask those who did *not* too.
- **Summarising too early:** write the row before discussing it with anyone.

## 8. After the five

Write a one-page findings note per segment: current process, cost of a change, who pays, whether the
four guarantees mattered unprompted, the verdict against section 6, and the single falsifier that
decided it. Link it from T-223. Do not describe findings as proof of market demand beyond what the five
interviews support.
