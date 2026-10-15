# T-227 · A capped, valid measurement of Gemini clause extraction on CUAD

**Stage** 4 · **Type** work · **Status** done · **Owner** Antigravity · **Branch** `t-227-cuad-capped-measurement`

**Scope**
- `evals/cuad/**`
- `tests/unit/evals/**`
- `docs/research/**` (the results note only)
- `.gitignore` (for the downloaded contract texts and the raw predictions)
- `pyproject.toml` and `uv.lock` (added 2026-10-04: declare `openai` and `python-dotenv` in the dev extras, then `uv lock`)

**Blocked by** — · **Blocks** any statement about extraction quality made to a buyer

## Goal

[T-909](T-909-cuad-verifier-bakeoff.md) built the CUAD harness and the real Gemini adapter (T-215)
exists, but **no measurement has ever been run**: the harness has no command that runs an extraction,
nothing fetches the contract texts, and the scoring has defects that would make any number meaningless.
We do not know how well extraction works on real contracts. Before anything is shown to a buyer, find
out, on a small, capped sample, for the categories CUAD labels, and say plainly what the number does
and does not mean.

This is a **measurement, not a demo**. It reports per-category precision and recall with their
uncertainty and makes no claim beyond them.

## Defects found in the harness (fix first, each with a failing test)

Reviewed on `main` (2026-10-02):

1. **Scores are pooled across contracts.** `CUADEvalHarness.run_evaluation` concatenates every
   contract's predictions and every contract's labels into one list per category, then matches them.
   A prediction from contract A can match a label from contract B ("State of Delaware" appears in many
   contracts), which inflates both precision and recall. Score **per contract**, then sum the true
   positives, false positives and false negatives.
2. **The match rule is too lenient.** `text_matches` returns true if either string is a substring of the
   other with no minimum length, or if token Jaccard is at least 0.5. A short generic prediction can
   match a long label. Replace it with a stated rule, for example token-level F1 of at least 0.5 between
   the prediction and a label, with no bare-substring rule, and document the choice. Add tests for a
   short string contained in a long label, for the same string under different casing and whitespace,
   and for two different clauses that share many words.
3. **Empty cases score 1.0.** `compute_category_metrics` returns precision = recall = F1 = 1.0 when
   there are no labels and no predictions. In a report this looks like a perfect category. Report
   support 0 as "not evaluated" and exclude it from any summary.
4. **No runnable entry point and no contract text.** `main()` only prints metadata and mappings, and
   `master_clauses.csv` holds labels, not the contract files. Add a `run` command and a documented
   download step for the contract texts that correspond to the CSV's filenames, taken from the **same
   CUAD repository and pinned revision** the README records. Verify which files exist at that revision,
   record the SHA-256 of every file used before first use, and keep the downloaded texts out of git.

Note also that the fixed 4,000-character slicing cuts clauses at chunk edges. Keep it for the first
run, state it as a limitation in the results, and do not tune it on the evaluation sample.

## Design

- **Sample.** A fixed-seed random sample of **30 contracts** (the seed is written down), drawn only
  from contracts that carry a label in at least one of the nine CUAD questions the harness scores
  (Q1 to Q8, Q11, Q12). Q9, Q10 and Q13 stay out of scope; CUAD has no signal for them.
- **Caps (hard, enforced in code, not by honour).** At most 30 contracts and at most **600 model
  calls** per run; abort cleanly when either is reached and write what was done. Record the token
  usage the provider returns for every call and print the totals. If `GEMINI_TIER` is `paid`, also
  stop when estimated spend reaches **USD 5**, stating the price assumption used. CUAD is public
  EDGAR text, so the free tier is acceptable under the decision log (public or synthetic data only);
  the free tier's rate limit may make the run slow, so honour 429 responses with backoff and make the
  run **resumable**.
- **Raw outputs.** Write every prediction, with the model id, prompt and ontology versions and the
  chunk it came from, to a JSONL file under an ignored directory. Scoring must run offline from that
  file without calling the model again.
- **Reproducibility.** The results note records the commit, the model id, the seed, the sample's
  filenames, the dataset checksums, the match rule and the caps.
- **Credentials.** `GEMINI_API_KEY` is read from the environment by the existing config. Never put a
  key in the repository, a ticket, a commit, a log or a PR description.

## Acceptance

- [x] Each of the four defects has a unit test that fails on the current `main` and passes on the fix (cross-contract false match; short-substring false match; empty category reported as "not evaluated"; match rule documented)
- [x] `python -m evals.cuad.harness run` (or equivalent, documented in the README) runs the sample, enforces both caps, resumes after an interruption, and scores offline from the saved predictions
- [x] A **smoke run of 3 contracts** is done first and its output shown; **stop and report before the capped run** so scoring can be reviewed on real output
- [x] The capped run (30 contracts) completes within the caps, with total calls and tokens reported
- [x] A results note in `docs/research/` gives per-category precision, recall, F1, **support**, and a **95% Wilson interval** for precision and recall; categories with support below 10 are marked "too few to judge"; there is **no blended number**; the table cites CUAD (Hendrycks et al., NeurIPS 2021, CC BY 4.0)
- [x] The note states, plainly: these figures are **not comparable with published CUAD results** (different metric and sample); CUAD contracts are likely in the model's pretraining data; nothing here says anything about temporal history, isolation, merge decisions or deletion; chunk slicing may cost recall; the sample is 30 contracts
- [x] `ruff check .` and `ruff format --check .` clean; full suite green; CI green

## Notes

Order of work: (1) the scoring fixes, test first; (2) the download, checksums and `run` command; (3) the
smoke run, then stop; (4) after review, the capped run and the note. A number that cannot be reproduced
from a pinned commit and the saved predictions is not a result.

Do not extend this to the 510-contract set, to our own documents, or to Q9, Q10 and Q13 here. If the
numbers justify a larger run, that is a new ticket.

## Amendment 2026-10-03 — provider changed to NVIDIA's free endpoint (no billing)

The founder will not set up Google billing (it requires an auto-pay mandate they do not want to take on),
and the Gemini free tier allows only 20 requests a day, so the measurement cannot run on Gemini. It runs on
NVIDIA's API Catalog free endpoint (`https://integrate.api.nvidia.com/v1`, OpenAI-style, key in
`NVIDIA_API_KEY`, default limit about 40 requests a minute). Everything above still applies (per-contract
scoring, caps, resumability, raw predictions, per-category results with intervals) except as changed here.

**Terms that bind this run** (NVIDIA API Trial Terms of Service, read 2026-10-03): trial use is for
"internal testing and evaluation purposes, not in production"; inputs and outputs may be used by NVIDIA to
improve its products, including AI models; confidential or personal data must not be submitted. So: **public
CUAD text only, never customer, interview or founder material**, and this endpoint can never be the product's
model on the free tier. The results note says so.

**What changes in the work:**
1. **Offline sanity tests first (no model calls).** An oracle run (each contract's own labels as predictions)
   scores near 1.0; a shuffled run (another contract's labels) scores near 0; an empty run has recall 0.
2. **An evaluation-only adapter in `evals/cuad/`**, not in `src/`: it calls the OpenAI-style endpoint, requests
   structured output with `guided_json` (`extra_body={"nvext": {"guided_json": schema}}`), and verifies every
   returned quote against the chunk text with the same deterministic check the Gemini adapter uses. It counts
   every provider attempt toward the call cap, backs off on 429, records tokens from the response, and never
   logs the key. Pricing is an explicit, documented **zero-price entry for the chosen model inside the eval
   code** (a recorded decision, not a silent default), with the call cap as the limit.
3. **A model probe before the run.** Candidates (from the public catalog; availability and structured-output
   support are unverified): `nvidia/llama-3.1-nemotron-70b-instruct`, `mistralai/mistral-large-2-instruct`,
   `nvidia/nemotron-3-super-120b-a12b`, `google/gemma-4-31b-it`, `deepseek-ai/deepseek-v4.1-flash`. For each,
   send the same 10 chunks taken from 2 contracts **outside** the final sample, and record: the share of
   responses that are valid against the schema, the share of quotes found verbatim in the chunk, latency, and
   errors. **Decision rule, written before the probe:** pick the model with the highest share of valid,
   verified responses; ties go to the faster. Do not choose by reputation and do not tune on the final sample.
4. **Then the 30-contract run** exactly as designed, under the 600-call cap, and the results note, which names
   the model and states that it is an open model hosted by NVIDIA, **not Gemini or Claude**, that its figures
   say nothing about those models, and the terms above.

## Review 2026-10-04 (probe and offline checks)

Verified independently on `770bce4`: the three offline sanity tests pass on the real downloaded texts and the
shuffled test fails on the original scoring code (so it catches the pooled-scoring defect); agy's loader fix is
real and important: seven of the 14 scored categories (Anti-Assignment, Cap On Liability, Change Of Control,
Exclusivity, Non-Compete, Termination For Convenience, Uncapped Liability) have Yes/No answer columns, and
before the fix their "labels" were the literal words Yes and No. That defect came from T-909 and was missed
by its review. Remaining work before the 30-contract run:

1. **The probe is not yet a fair result.** `max_tokens=2048` starves a reasoning model of output after its
   thinking tokens (the 4 "empty outputs" of 10), and a 25 s per-chunk timeout with an abort after two
   timeouts may explain the two models reported as unresponsive; only one of five models was really
   evaluated. Raise the output budget (or turn thinking off where the model supports it), lengthen the
   timeout (for example 90 s), re-probe all five on the same 10 chunks, and report each failure type.
   **Bar set before the re-probe: at least 95% of chunks return schema-valid output for the model to be
   used.** If no model reaches it, stop and report; do not run the 30-contract sample on a model that fails
   one chunk in three.
2. **Failed or empty chunks must never be scored silently.** Retry them once with a larger budget; if a
   chunk still fails, exclude its contract from scoring and report how many contracts and chunks were
   excluded. A recall number deflated by harness failures is not a result.
3. **The sanity tests must run in CI.** They currently skip without the downloaded data. Commit a tiny
   fixture (a few rows of labels and short text, CC BY 4.0 with attribution) so oracle, shuffled and empty
   tests always run; keep the real-data version as an extra. Add an assertion that no loaded label is the
   literal text "yes" or "no".
4. **Declare `openai` and `python-dotenv`** (imported by `evals/cuad/nvidia.py`, present only transitively)
   in the dev extras and regenerate `uv.lock`.
5. **Remove the fallback to the misspelled `NVIDIA_API_KE`.** The founder fixes `.env`; the code reads
   `NVIDIA_API_KEY` only.

## Measurement design correction 2026-10-05 (after the 3-contract smoke on NVIDIA)

The smoke run (28 chunks, 2 of 3 contracts scored, 1 excluded) scored near zero, and comparing the saved
predictions with the real labels shows the **comparison is invalid for most categories, not the model weak**:

- **Value categories compare against normalized answers.** For Governing Law the label is `Texas`; for dates
  it is `11/30/17`; for Parties it is the party names. The harness compares the model's *quote* with those
  strings, so a correct `30th day of November, 2017` cannot match `11/30/17`.
- **The model quotes headings and generic words.** Predictions included `Governing Law`, `Effective Date`,
  `[EXCLUSIVITY]` and `the parties` (15 false positives for Parties in two contracts). The prompt does not
  tell it to quote the operative clause or to avoid headings and generic mentions.
- **A contract-level failure rate is too high.** One of three contracts was excluded for one failing chunk.
  Chunk failure near 1 in 28 would exclude roughly four in ten 15-chunk contracts and bias the sample toward
  short contracts.
- **Cost of a run:** about 21 s per call and about 2,600 output tokens per call (reasoning); 450 calls is
  roughly 2.7 hours.

**Do not run the 30-contract sample until this is fixed and reviewed.** Required changes:

1. **Two scoring modes, per category, written down before any new run.**
   - *Clause categories* (Anti-Assignment, Cap On Liability, Change Of Control, Exclusivity, Non-Compete,
     Termination For Convenience, Uncapped Liability): the labels are the clause spans in the base column. A
     prediction is the clause text the model quotes. Per contract, match by token-level F1 of at least 0.5
     against a label span (each label used once). Also report **contract-level presence** precision and
     recall (does the contract contain the clause, did the model return at least one clause).
   - *Value categories* (Governing Law, Agreement Date, Effective Date, Expiration Date, Parties): the model
     returns a normalized **value** and a verbatim **quote** as evidence. Compare the value, normalized, with
     the label's normalized answer: governing law by lower-cased jurisdiction name without "State of"; dates
     parsed to a calendar date; parties with case, punctuation, parenthetical aliases and corporate suffixes
     (inc, llc, ltd, corp, co, company) removed. Report the quote-found rate separately.
   - *Renewal Term and Notice Period To Terminate Renewal* have free-text answers that need human judgement:
     report them as **not scored automatically**; do not give them a number.
2. **Fix the prompt.** Use the CUAD question wording (or the descriptions already in `mapping.py`) for each
   category; require the operative clause or a normalized value; forbid section headings, defined-term labels
   and generic words such as "party" or "the parties"; return nothing when the clause is absent.
3. **A development set apart from the test sample.** Choose 5 development contracts with a different seed,
   excluded from the final 30. Tune the prompt only on them (at most 150 attempts), then **freeze the prompt**,
   record its hash, and run the 30-contract sample once. Never tune on the test sample.
4. **Fewer exclusions.** Retry a failing chunk up to two more times (for example 4096, 8192, then 16384
   tokens, and try disabling thinking if the model supports it). Report the chunk failure rate and the
   exclusion rate, and state that excluded contracts skew long.
5. **Side-by-side output.** For each development run, show per category the label next to the prediction for
   every contract, so the scoring can be checked by eye before anything is counted.
6. Optional: modest concurrency (up to 4 requests) to cut the run time, keeping attempt counting exact and the
   rate under 40 requests a minute.

## Review of the development run (5 contracts, seed 1337, prompt hash b63f8a79...)

Checked by the reviewer from `raw_predictions/predictions.jsonl` and `master_clauses.csv`, not from the
report's prose. Token totals (284,832 in / 209,621 out), 5 contracts and 0 exclusions match the file.
The prompt was run once and not tuned, so the dev numbers are honest, if low.

**What holds.** All 82 returned quotes occur verbatim in the contract text (reviewer's own whitespace-normalised
substring check). Dates and governing law are right whenever the model answers; the model answered 8 of 10
agreement and effective dates and 3 of 5 governing laws.

**What does not hold, and what it changes.**
1. *The report's prose overstated.* It called Cap On Liability and Uncapped Liability on the first contract
   "Token-F1 match". Recomputed best token-F1 is 0.45 and 0.36, below the 0.5 bar; the aggregate table is right,
   the narrative is not. Numbers must be copied from harness output, never paraphrased.
2. *Parties precision 0.19 is mostly an artefact.* The same party is predicted many times (one contract has 16
   predictions for 2 parties) and every repeat counts as a false positive; a defined-term alias ("Cisco" for
   "Cisco Systems, Inc.") also counts as a false positive. Deduplicated and alias-aware, the five contracts give
   precision 0.80 and recall 0.73 (TP 8, FP 2, FN 3). Role words the prompt forbids ("Distributor", "Client",
   "Affiliate") were still returned on 3 of 5 contracts. One label is a typo ("Ostenonics") and one is junk
   ("Stryker and Conformis"); labels are not corrected, the effect is stated.
3. *Chunking truncates clauses.* The harness cuts the contract into fixed 4000-character windows, so a long
   clause crossing a boundary is returned cut short (a 206-word label answered by 27 words; a 358-word label by
   74). That depresses clause span scores and is not what the product's chunker would do.
4. *`quote_found` is not an independent check.* It is true when a span object exists. The reviewer's check
   agrees today, but the rate must come from verifying the quote in the text.
5. *Prompt leak:* the literal template text "YYYY-MM-DD" came back as a date value on one contract. It is
   dropped by the normaliser; count and report it. The prompt stays frozen.
6. *Scale.* 5 contracts gave 117 chunks (about 23 per contract), so 30 contracts is about 700 chunks, over the
   600-attempt cap, and at about 14 s a call roughly 2.7 hours sequentially. Every category has 5 or fewer
   contracts behind it in the dev set; no category ranking is meaningful at that size.
7. *Clause recall is the weak spot* on this model: nothing returned for Cap On Liability on 3 of 4 contracts that
   have one, Exclusivity on 2 of 4, Non-Compete on 1 of 2.

**Decision.** Accept the harness, the two scoring modes and the dev run. Before the one-shot test run:
chunk on line boundaries (never mid-line, at most 4000 characters), deduplicate parties and treat a defined-term
alias as the same party, compute `quote_found` by checking the quote in the text and report quote-in-text for
clause categories too, raise the attempt cap to 900 (zero-price endpoint; the cap is a runaway guard), print
the planned chunk count before the run, resume rather than restart on a crash, and run the 30 contracts once with the
frozen prompt hash. Scoring changes can be re-run offline from saved predictions; the prompt and chunking are
not changed after the run starts. Report k/n beside every rate.

## Review of the 30-contract test run (seed 42, prompt hash b63f8a79..., model nemotron-3-super-120b-a12b)

Checked by the reviewer from `raw_predictions/predictions.jsonl` and `master_clauses.csv`, with a separate scoring
script, not from the report.

**Run integrity: holds.** 35 rows carry the frozen hash (30 test plus the 5 development contracts); test tokens
(824,799 in / 508,370 out) equal the file total minus the development run; 0 excluded, 0 chunk failures.
376 chunks were planned (the reviewer's earlier estimate of about 700 was wrong, the development set had one very
long contract). All 390 returned quotes occur in the contract text by the reviewer's own check.

**Scores: reproduced exactly** for every value and clause category (TP/FP/FN and presence counts). Parties is the
one place the reviewer's strict version differs by design: exact-name matching gives 0.49 precision / 0.79 recall
(59 TP, 61 FP, 16 FN); the specified defined-term-alias version gives 0.72 / 0.86 (66 TP, 26 FP, 11 FN). Report both.

**Defect found: `normalize_date` invents dates from partial input** by filling missing parts from today's date
(`"15"` gives 2026-10-15, `"2018"` gives 2018-10-04, `"March 2018"` gives 2018-03-04). Scores therefore change with
the day they are computed. It produced 4 spurious predicted dates in this run: Agreement Date FP 11 should be 9
(precision 0.68) and Effective Date FP 2 should be 0 (13/13). It only inflated false positives. Fix: reject any
date missing day, month or year, with tests; rescore offline, no re-run.

**Other things that depress the numbers and are not model errors.**
- 5 of 30 contracts have no Agreement Date label though the text states a date; 2 labels are truncated or junk
  (`04/30/`, `/[]/2018`). Agreement Date precision is understated for this reason.
- Parties labels sometimes contain whole sentences or a typo, and two Governing Law "misses" are
  `england and wales` / `english law` against labels split as `england` and `wales`.
- Remaining Parties false positives are other entities named in the contract (affiliates, subsidiaries) and a few
  role words (`affiliate`, `seller`, `agency`, `the`) that the prompt forbids.

**What the measurement supports (n is small; 95% Wilson intervals given where it matters).**
- Strong enough to show with a human check: dates (agreement-date recall 19/21), governing law (recall 23/29,
  precision 23/25), parties (alias-aware 0.72 / 0.86), and presence of Anti-Assignment (recall 18/22 = 0.82,
  [0.62, 0.93]), Termination For Convenience (13/13, lower bound about 0.77), Change Of Control (9/10).
- Not supported: **Cap On Liability** (presence recall 6/16 = 0.38, [0.18, 0.61]), **Non-Compete** (4/8) and
  **Uncapped Liability** (4/8): the model returns nothing for most contracts that have the clause. A silent miss is
  the dangerous direction for a compliance buyer, so these must not be claimed as detected.
- Precision on clauses is high when the model answers (Cap On Liability 6/6, Anti-Assignment 18/19).

**Limits to state wherever the numbers are used.** (1) One model, a free evaluation-only endpoint whose inputs may
be used by the provider: it shows what an open 120B model can do with this prompt, not what the production model
(Sonnet, per the cost plan) would do, and no customer contract may be sent to it. (2) 30 contracts, one run, one
seed; run-to-run variation was not measured. (3) Two of the 30 (Sibannac, Ediets) were the smoke contracts whose
mistakes informed the prompt redesign; the prompt was not tuned on them, but they are not clean. (4) The harness
chunker is a simple line-boundary splitter, not the product's chunker. (5) No comparison with published CUAD
results is made: different task framing and metric.

**Decision.** Accept the run. Fix the date normaliser, rescore offline, publish a results note
(`docs/research/`) with both Parties versions, the limits above, and the recommendation that the next
measurement, if wanted, uses the intended production model under a dollar cap taken from the usage ledger.
No outreach or deck may quote these figures as product accuracy.

## Review of the closing fixes (PR #25 merged, PR #26 open)

Verified: strict date parsing (`"15"`, `"2018"`, `"March 2018"` return `None`; full dates still parse); the offline
`rescore` command reproduces the reviewer's independent numbers exactly (Agreement Date precision 0.68, Effective Date
1.00, Parties 0.49 exact-name and 0.72 alias-aware); PR #26 changes only the two neutral-wording lines; CI #167 and main
#166 green. The 73 local skips are 72 Postgres tests with no database running locally plus the live Gemini smoke test;
CI skips 3 (the Gemini smoke test and two CUAD tests that need the gitignored corpus), the same as main, so no new
skips.

**Acceptance still open (checked against the merged results note):**
- per-category **95% Wilson intervals** for precision and recall (only one category has one, in prose);
- categories with support below 10 marked "too few to judge";
- the plain statements: not comparable with published CUAD results; CUAD contracts are likely in the model's
  pretraining data; nothing here says anything about temporal history, isolation, merge decisions or deletion;
  chunk slicing may cost recall; the sample is 30 contracts.

Status stays `claimed` until a small docs-and-formatting follow-up closes these. They can be computed offline from the
saved predictions.

## Acceptance (recorded after PR #27 merged)

PR #25 (harness, two scoring modes, dev run, 30-contract run), PR #26 (neutral wording) and PR #27 (Wilson intervals,
"too few to judge" marks, the "What These Numbers Do Not Show" section, `rescore` generating the note's tables) are
merged. Reviewer's independent checks: every score reproduced from the saved predictions; the intervals recomputed from
raw counts match; no count changed between note versions; CI green on each PR; main green.

Acceptance ticked as met, with two stated departures from the original ticket text: the model measured is the free
NVIDIA trial model, not Gemini (the Gemini free tier allows 20 requests per model per day and billing was not
available); and clause categories are scored by span match plus contract presence, value categories by normalised value,
per the design correction above. The Parties figure is reported twice (exact name, alias-aware).

**Post-merge correction (reviewer, by docs edit):** the merged note said the product uses "semantic AST / structural
chunking". It does not: the ingest chunker splits on blank lines only, with no size cap. The note is corrected. This is
recorded as an input to T-228 below.

Outputs: the harness (`evals/cuad/**`), `docs/research/cuad-extraction-measurement-2026-10.md`. Parked: the same frozen
prompt on the production model under a ledger-backed dollar cap, which needs an Anthropic key with billing.
