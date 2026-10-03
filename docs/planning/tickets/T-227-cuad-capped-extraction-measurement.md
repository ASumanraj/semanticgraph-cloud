# T-227 · A capped, valid measurement of Gemini clause extraction on CUAD

**Stage** 4 · **Type** work · **Status** open · **Owner** — · **Branch** `t-227-cuad-capped-measurement`

**Scope**
- `evals/cuad/**`
- `tests/unit/evals/**`
- `docs/research/**` (the results note only)
- `.gitignore` (for the downloaded contract texts and the raw predictions)

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
