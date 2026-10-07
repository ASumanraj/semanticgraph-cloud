# T-227 · A capped, valid measurement of Gemini clause extraction on CUAD

**Stage** 4 · **Type** work · **Status** claimed · **Owner** Antigravity · **Branch** `t-227-cuad-capped-measurement`

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

- [ ] Each of the four defects has a unit test that fails on the current `main` and passes on the fix (cross-contract false match; short-substring false match; empty category reported as "not evaluated"; match rule documented)
- [ ] `python -m evals.cuad.harness run` (or equivalent, documented in the README) runs the sample, enforces both caps, resumes after an interruption, and scores offline from the saved predictions
- [ ] A **smoke run of 3 contracts** is done first and its output shown; **stop and report before the capped run** so scoring can be reviewed on real output
- [ ] The capped run (30 contracts) completes within the caps, with total calls and tokens reported
- [ ] A results note in `docs/research/` gives per-category precision, recall, F1, **support**, and a **95% Wilson interval** for precision and recall; categories with support below 10 are marked "too few to judge"; there is **no blended number**; the table cites CUAD (Hendrycks et al., NeurIPS 2021, CC BY 4.0)
- [ ] The note states, plainly: these figures are **not comparable with published CUAD results** (different metric and sample); CUAD contracts are likely in the model's pretraining data; nothing here says anything about temporal history, isolation, merge decisions or deletion; chunk slicing may cost recall; the sample is 30 contracts
- [ ] `ruff check .` and `ruff format --check .` clean; full suite green; CI green

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
