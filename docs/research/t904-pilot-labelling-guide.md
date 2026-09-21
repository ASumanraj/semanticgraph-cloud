# T-904 pilot — labelling guide

**For:** the product owner and friends, doing the first pass on the 10-document pilot.
**Status of what you produce: draft labels.** The wave-1 protocol reserves the word *gold* for a paid,
qualified commercial-contract reviewer. Nothing here is gold, and nothing here should ever be
described as gold. What your pass is worth: it tests this protocol, produces a first agreement
number, and gives real data on how many hours a document takes, which sets the paid reviewer's
budget (40 hours across the ten documents, reassessed before expanding).

## What you are doing

Read each contract and answer the same fixed questions about it. For every answer, copy the exact
sentence that supports it. That is all. You are not summarising, and you are not judging whether the
contract is a good deal.

The exact quote is the important part. Our system will find the quote in the document text and work
out its character position itself, so you never count characters. If the quote cannot be found in the
document, the label is rejected. This matches how the product works: it locates a quote, it does not
trust a claimed position.

## Rules

1. **Copy, do not retype.** Paste the sentence from the document text. Same wording, same numbers, same
   punctuation. Do not fix typos, and do not shorten with "…" in the middle. Two quotes are two rows.
2. **The shortest span that proves the answer.** Usually one sentence or one numbered sub-clause.
   Not the whole page, not just three words.
3. **No AI tools, and no looking at anyone else's answers, until you are told to.** A label written
   with a model's help stops being independent ground truth. If you did use one for a row, mark it
   `assisted` in the notes column. Then the row is silver, not draft.
4. **"Not present" is an answer, and it has to be earned.** Search the document (Ctrl+F) for the words
   listed beside the question before you write it, and put the words you searched in the notes column.
   Missing a clause that is there costs more than leaving a row unsure.
5. **When the contract has been amended, say so.** If a document is an amendment or a restatement, the
   answer to a question is what the document as a whole now says, and the quote is the sentence in this
   document that says it. If it only changes the clause and does not restate it, quote the change and
   write `changes clause` in the notes column. Do not go and read the original to fill gaps.
6. **Unsure is a valid confidence.** 1 = guess, 2 = probably right, 3 = certain. Use 1 freely.
7. **Log your time.** Start and stop times per document, on the `time` tab. This is the most useful
   thing you produce for planning the paid review.
8. **Do not fix disagreements.** When you compare with a friend later, mark both answers and stop.
   The reviewer decides.

## The questions (v0 — a draft; the corpus will decide the final list)

| # | Question | Answer type | Search for |
|---|---|---|---|
| Q1 | Who are the parties? | names, as written | "between", "by and among", signature block |
| Q2 | What is the agreement date? | date, or not present | "dated", "as of", "made and entered" |
| Q3 | What is the effective date, if different? | date, or same as Q2 | "effective date", "effective as of" |
| Q4 | How long does it run, or when does it expire? | value | "term", "expire", "initial term" |
| Q5 | Does it renew automatically? | yes / no / not present | "renew", "successive", "automatic" |
| Q6 | Can either party end it for convenience, and with how much notice? | yes / no + notice | "terminate", "convenience", "without cause", "days' notice" |
| Q7 | What law governs it? | jurisdiction | "governed by", "governing law", "laws of" |
| Q8 | Is liability capped? At what? | yes / no / not present + amount | "limitation of liability", "shall not exceed", "aggregate liability" |
| Q9 | Is anything excluded from that cap? | yes / no / not present + what | "except", "shall not apply to", "gross negligence", "confidential" |
| Q10 | Is there an indemnity? Who indemnifies whom? | yes / no + direction | "indemnify", "hold harmless" |
| Q11 | Can it be assigned, and what happens on a change of control? | yes / no / consent needed | "assign", "change of control", "merger" |
| Q12 | Is there exclusivity or a non-compete? | yes / no + who is bound | "exclusive", "non-compete", "shall not compete" |
| Q13 | *Amendments only:* what does this document change? | list of clauses | "hereby amended", "is deleted and replaced" |

Twelve questions on the ten documents is about 120 rows before duplicates, and the three overlap
documents give 36 questions that two people answered independently. That covers the ticket's 30-question
overlap requirement.

## How the overlap works

Everyone labels the three overlap documents (rows 10, 1 and 7 in `t904-pilot-document-selection.md`:
Synacor/Embarq, Altiris/Dell, Cerus/Ash Stevens) without comparing. Only after all
of them are finished do you compare: the reviewer scores agreement, counting an answer as matching
when the **answer value is the same and the two quotes overlap in the same clause**. The other seven
are split between people. A label is agreed only when both agree, so agreement is reported as the
share of matching answers, and disagreements are listed rather than resolved.

## Files

- Answer sheet template: `evals/labelling/answer_sheet_template.csv`. One row per answer. Make a copy
  per person and per document, or import it into one Google Sheet with the columns unchanged.
- Time log: `evals/labelling/time_log_template.csv`.
- Documents: listed with direct links, checksums and known redactions in `t904-pilot-document-selection.md`.
  Start with row 9 (Escalade, about seven pages, no redaction) to warm up. Two of the documents (Cerus and
  Synacor) have redacted numbers, so do not label a value that is masked with `[*]`; write `redacted`.
  Rows 5 and 6 are short amendments: answer only from that document and write `not in this document`
  for the rest, never from the original. Read them in the browser
  from the source, or download the exhibit text. Do not work from a summary.

## What happens next

1. You and your friends label. Send the sheets back as they are, including the rows you are unsure of.
2. I check every quote by locating it in the document text and report the rejects, the disagreements
   and your hours per document.
3. Only then does the paid reviewer start, on the same documents, with the disagreements and the
   time figures in hand. That is why the 40-hour cap can be sized from measurement.
4. Draft labels are kept and labelled *draft*. If the paid reviewer's gold differs, gold wins and
   your row stays as the record of what a non-specialist saw.

## What this pilot can and cannot show

It shows whether the questions are answerable, how long labelling takes, and whether two careful
people agree. It does not show extraction accuracy, and it does not measure anything about documents
the models have not seen: public contracts are likely in training data (an inference, not checked),
so results here are an engineering benchmark and must be reported that way.
