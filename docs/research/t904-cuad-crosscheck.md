# T-904 — CUAD as a free external benchmark: verification and gap map

**Date** 2026-09-22. Answers the check the product owner's advisor asked for: verify CUAD's
licence and annotation claims from official sources, check it against the T-904 manifest by more
than company name, map its labels to our 12 questions, and say what's still missing. **Conclusion
up front: CUAD is real, free, and well-labelled, has zero overlap with our ten documents, and does
not cover two of our twelve questions at all. It replaces nothing in T-904; it's a second, free
benchmark to run alongside it once there's an extractor to test.**

## 1 · Licence and annotation claims, verified from official sources

- **Licence:** CC BY 4.0. Checked on the dataset's own HuggingFace card
  (`theatticusproject/cuad`) — attribution required, no other restriction.
  `[verified: https://huggingface.co/datasets/theatticusproject/cuad]`
- **Who labelled it:** law student annotators trained by experienced attorneys — 70–100 hours of
  supervised contract-review sessions, over 100 pages of written annotation guidelines, and **every
  annotation independently checked by three further annotators**. Checked against search results
  citing the dataset's own datasheet and the Atticus Project's description of its methodology.
  `[secondary — search-engine-summarized from the datasheet; the datasheet PDF itself was not
  opened directly, so read it before this claim goes in anything customer-facing]`
- **Scale:** 510 contracts, 13,000+ annotations, 41 label categories — consistent with the
  dataset card and with what's already in `T-904-evaluation-corpus.md`'s Track A row.
- **Where the data actually lives:** not committed to the CUAD GitHub repo directly (that repo
  holds training/eval code only); the labelled CSV and contract texts are distributed as
  `data.zip` and mirrored on HuggingFace. `master_clauses.csv` is the file with one row per
  contract and one `<Category>` / `<Category>-Answer` column pair per clause type.

## 2 · Overlap with our ten T-904 documents: none found

The advisor is right that company name alone is a weak check, so this was run three ways against
`master_clauses.csv`: the **Filename** column, the **Document Name** column, and the
**Parties-Answer** column (the actual contracting parties CUAD extracted, which would catch a
different filename for the same real contract). All three companies-name searches — Altiris,
Dell Products, Portal Software, Unified Western Grocers, C & K Market, Strategic Diagnostics,
DuPont Qualicon, Elite Pharmaceuticals, TPN, Alarm.com, Marshall Property, Cerus, Ash Stevens,
Washington Gas, Escalade, Synacor, Embarq — came back with **zero matches**.

**Caveat on the method, as the advisor asked for:** CUAD's own metadata does **not** include SEC
accession numbers or filing dates at all (confirmed on the dataset card), so the accession-number
cross-check the advisor wanted cannot be done — CUAD simply doesn't carry that field. Name-based
matching across three independent columns is the strongest check available against this dataset,
and it is a true negative, not an absence-of-evidence gap: our ten documents were chosen from live
EDGAR full-text search in September 2026, CUAD was built years earlier from a different sampling
process, and the two populations not intersecting is the expected outcome, not a surprise.

**So:** nothing in the T-904 manifest changes. CUAD is an independent second dataset, not gold
labels for our own ten documents. Steps 1 and 4 of the advisor's checklist are answered by this
section; step 3 (whether CUAD's quoted spans locate exactly in *our* document text) does not
apply, because there is no overlapping document for a span to be checked against.

## 3 · Mapping CUAD's 41 categories to our 12 questions

| Our question | CUAD category | Fit |
|---|---|---|
| Q1 parties | `Parties` | direct |
| Q2 agreement date | `Agreement Date` | direct |
| Q3 effective date | `Effective Date` | direct |
| Q4 term / expiry | `Expiration Date` | direct |
| Q5 auto-renewal | `Renewal Term` + `Notice Period To Terminate Renewal` | partial — CUAD frames this as the renewal term's length and the notice needed to *stop* it, not a plain yes/no auto-renewal flag; needs light interpretation to answer our question shape |
| Q6 termination for convenience + notice | `Termination For Convenience` | direct on the yes/no; CUAD does not separately label the *notice period* for convenience termination the way it does for renewal, so the notice-length half of Q6 is uncovered |
| Q7 governing law | `Governing Law` | direct |
| Q8 liability cap + amount | `Cap On Liability` + `Uncapped Liability` | direct |
| Q9 exclusions from the cap | — | **not covered.** No CUAD category records carve-outs from a liability cap at all |
| Q10 indemnity | — | **not covered.** CUAD has no `Indemnification` category anywhere in its 41 — a genuine surprise, checked twice against the full column list |
| Q11 assignment / change of control | `Anti-Assignment` + `Change Of Control` | direct |
| Q12 exclusivity / non-compete | `Exclusivity` + `Non-Compete` | direct, and CUAD also separately labels `No-Solicit Of Customers`/`Employees`, which our question set currently folds into the same question and CUAD keeps apart |
| Q13 amendment — what changed | — | **not applicable.** CUAD's 510 contracts are standalone; it has no amendment/predecessor pairing to diff, so this question can only be tested on our own three amendment rows |

**Bottom line on coverage:** CUAD gives free, expert-checked ground truth for **9 of our 12
questions**, fully or partly. It has **no signal at all** for cap exclusions (Q9) or indemnity
(Q10) — both real gaps, not something a smarter mapping fixes — and it cannot exercise the
amendment-diff question (Q13) by construction. Those three stay dependent on the paid reviewer
working our own ten documents, whenever that happens.

## 4 · What CUAD does not, and cannot, validate

Per the advisor's instruction, stated plainly so nobody reaches for CUAD to answer these later:
CUAD is 510 independent, standalone contracts with per-document clause labels. It says nothing
about, and cannot be used to test, **temporal/point-in-time history, tenant isolation, resolution
decisions, or assertion-counted deletion** — those are properties of *our* system operating over
multiple documents and multiple tenants, not properties any single-contract clause-labelling
dataset can speak to.

## 5 · Attribution and version, for whenever this is actually used

- **Cite as:** Hendrycks et al., *CUAD: An Expert-Annotated NLP Dataset for Legal Contract
  Review* (NeurIPS 2021 Datasets and Benchmarks), The Atticus Project. CC BY 4.0.
- **Version used for this check:** the `main` revision of
  `theatticusproject/cuad` on HuggingFace, accessed 2026-09-22. **Not yet recorded:** a content
  checksum of `master_clauses.csv` — take one the day the file is actually downloaded for use, not
  today, since "accessed on a date" is not the same guarantee as "this exact file."

## 6 · What this changes right now

- **T-904's manifest and corpus:** unchanged. CUAD does not replace it.
- **No code for agy today.** Running CUAD as an automated accuracy check needs a real extractor
  producing real clause judgements; today's extractor (from T-110) is a deterministic double that
  returns one placeholder entity per chunk and proves the pipeline plumbing, not clause accuracy.
  Pointing CUAD at it would produce a meaningless near-zero score. The eval harness that loads
  CUAD's CSV and contract texts, applies the mapping table above, and scores precision/recall per
  category belongs to **T-904's follow-on "verifier bake-off"** — opened as **T-909**, blocked on
  a real Stage 3 extractor existing, using this file as its design input.
- **Paid reviewer:** still only needed for Q9, Q10 and Q13 on our own ten documents, and only
  after the draft pass sizes the hours — narrower than "everything," which is worth knowing before
  spending the 40-hour cap.
