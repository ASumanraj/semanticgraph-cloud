# CUAD Clause Extraction Measurement Note (October 2026)

**Ticket:** T-227 (Capped CUAD extraction measurement)  
**Date:** 2026-10-07  
**Author:** Antigravity (Pair Programming Assistant)  
**Evaluation Model:** `nvidia/nemotron-3-super-120b-a12b` (hosted via NVIDIA API Catalog)  
**Dataset:** CUAD v1 (`Hendrycks et al., NeurIPS 2021 Datasets and Benchmarks`, The Atticus Project, CC BY 4.0)  
**Dataset Checksum:** SHA-256 `4da237bec677bf5b02212d523857cd57a801adde60e8021de063c8cc06823720`  
**Test Sample:** 30 contracts (fixed random seed 42, drawn from Part I & Part II 194-contract text population)  
**Prompt SHA-256 Hash:** `b63f8a790f5dc3cc42dbf70aaad2309725bb87e8774c42ec6a0efcc05a6893b9` (frozen after 5-contract dev run)

---

## 1. Terms of Use & Binding Constraints

This evaluation was conducted under the **NVIDIA API Trial Terms of Service** (reviewed 2026-10-03):
- Trial access is strictly for **internal testing and evaluation purposes, not in production**.
- Inputs and outputs may be used by NVIDIA to improve its products and AI models. Confidential, proprietary, or personal data must not be submitted.
- **Data scope:** Public CUAD contracts only. **Never customer, interview, or founder material.**
- **Endpoint status:** This evaluation endpoint cannot be used for the product's runtime or free tier.
- **Model distinction:** The evaluated model is an open-weights 120B model (`nvidia/nemotron-3-super-120b-a12b`) hosted by NVIDIA. **These figures say nothing about the models named in ENTERPRISE_PLAN.md, not evaluated here** (the planned production models per the cost architecture in `ENTERPRISE_PLAN.md`).
- **No product-accuracy claims:** No marketing outreach, investor update, or pitch deck may quote these figures as SemanticGraph Cloud product accuracy.

---

## 2. Methodology & Measurement Design

### 2.1 Population & Sample Selection
- Upstream CUAD v1 contains 510 annotated contracts in `master_clauses.csv`. At the pinned revision, text files (`.txt`) exist for 200 contracts across Part I (100) and Part II (100); Part III contracts are PDF-only upstream. 194 contracts match annotations in `master_clauses.csv` and form the accessible population.
- **Development set:** 5 contracts selected with random seed 1337, strictly disjoint from the test sample. Used for prompt formulation and verification before test execution.
- **Prompt Freeze:** The extraction prompt was finalized during the dev run and frozen with SHA-256 hash `b63f8a790f5dc3cc42dbf70aaad2309725bb87e8774c42ec6a0efcc05a6893b9`. No prompt modifications were permitted after freeze.
- **Test sample:** 30 contracts selected with fixed random seed 42 (`random.Random(42).shuffle(test_pool)[:30]`).

### 2.2 Chunking and Provider Execution
- **Chunking:** Line-boundary chunker (`chunk_contract_by_lines`, max 4,000 characters). Splits only on newline boundaries (`\n`) to prevent truncating words or lines mid-sentence.
- **Retry Ladder & Exclusions:** Failed chunks escalate through a token budget ladder (4,096 tokens, then 8,192, then 16,384 tokens). If any chunk fails after retries, the entire contract is excluded to avoid biased partial-contract scoring.
- **Run Execution:**
  - Planned chunks: 376 chunks across 30 contracts.
  - Actual provider attempts: 383 (376 base chunk calls + 7 retries at 8,192 tokens).
  - Failed chunks: 0 (0.0%).
  - Excluded contracts: 0 (0.0%).
  - Call cap: 900 attempts (well under cap).
  - Spend: $0.00 USD (explicit zero-price trial schedule).
  - Tokens: 824,799 input tokens, 508,370 output tokens (reasoning-intensive).
  - Elapsed time: 3,529.5s (~58.8 minutes).
  - Resumability: Every chunk response recorded with contract, model, tokens, and prompt hash in `evals/cuad/raw_predictions/predictions.jsonl`.

### 2.3 Two Scoring Modes
To prevent false matches identified in earlier smoke runs (where normalized answers were improperly compared to raw quotes), two scoring modes were implemented:
1. **Value Categories** (`Agreement Date`, `Effective Date`, `Expiration Date`, `Governing Law`, `Parties`):
   - Compares the model's normalized value against the ground truth normalized answer.
   - Governing Law: lower-cased jurisdiction without "State of" or choice-of-law boilerplate.
   - Dates: strict calendar date (`YYYY-MM-DD`).
   - Parties: punctuation, corporate suffixes (`inc`, `llc`, `ltd`, etc.), and defined-term aliases handled per mode. Predictions deduplicated per contract.
   - Quote-in-text: every returned verbatim quote is checked for exact occurrence in the full contract text.
2. **Clause Categories** (`Anti-Assignment`, `Cap On Liability`, `Change Of Control`, `Exclusivity`, `Non-Compete`, `Termination For Convenience`, `Uncapped Liability`):
   - Span matching: Token-level F1 >= 0.5 against ground-truth clause spans per contract.
   - Contract-level presence: Precision, recall, and F1 measuring whether the contract contains the clause and whether the model identified at least one valid instance.
   - Quote-in-text: checked against the full contract text.
3. **Non-Scored Categories** (`Renewal Term`, `Notice Period To Terminate Renewal`):
   - Marked as **not scored automatically** due to unstructured natural-language phrasing requiring human adjudication.

---

## 3. Benchmark Results (30-Contract Test Sample)

The following tables are reproduced directly from the test harness offline rescoring (`python -m evals.cuad.harness rescore`). Every rate reports exact counts (`k/n`).

### 3.1 Value Categories (Normalized Value Matching)

| Category | Precision | Recall | F1 | TP | FP | FN | Support | Quote Found |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Agreement Date** | 0.68 (19/28) | 0.90 (19/21) | 0.78 | 19 | 9 | 2 | 21 | 100.0% (35/35) |
| **Effective Date** | 1.00 (13/13) | 0.81 (13/16) | 0.90 | 13 | 0 | 3 | 16 | 100.0% (16/16) |
| **Expiration Date** | 0.88 (7/8) | 0.50 (7/14) | 0.64 | 7 | 1 | 7 | 14 | 100.0% (11/11) |
| **Governing Law** | 0.92 (23/25) | 0.79 (23/29) | 0.85 | 23 | 2 | 6 | 29 | 100.0% (26/26) |
| **Parties (Alias-Aware)** | 0.72 (66/92) | 0.86 (66/77) | 0.78 | 66 | 26 | 11 | 77 | 100.0% (205/205) |

*Literal template strings detected in responses (e.g. `'YYYY-MM-DD'`): 3.*

### 3.2 Clause Categories (Span F1 >= 0.5 & Contract Presence)

| Category | Span Prec | Span Rec | Span F1 | Pres Prec | Pres Rec | Pres F1 | Support | Quote In Text |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Anti-Assignment** | 0.65 (17/26) | 0.74 (17/23) | 0.69 | 0.95 (18/19) | 0.82 (18/22) | 0.88 | 23 | 100.0% (26/26) |
| **Cap On Liability** | 0.83 (5/6) | 0.28 (5/18) | 0.42 | 1.00 (6/6) | 0.38 (6/16) | 0.55 | 18 | 100.0% (6/6) |
| **Change Of Control** | 0.70 (7/10) | 0.70 (7/10) | 0.70 | 0.90 (9/10) | 0.90 (9/10) | 0.90 | 10 | 100.0% (10/10) |
| **Exclusivity** | 0.56 (5/9) | 0.50 (5/10) | 0.53 | 0.83 (5/6) | 0.71 (5/7) | 0.77 | 10 | 100.0% (9/9) |
| **Non-Compete** | 0.83 (5/6) | 0.29 (5/17) | 0.43 | 0.80 (4/5) | 0.50 (4/8) | 0.62 | 17 | 100.0% (6/6) |
| **Termination For Convenience** | 0.65 (11/17) | 0.79 (11/14) | 0.71 | 0.81 (13/16) | 1.00 (13/13) | 0.90 | 14 | 100.0% (17/17) |
| **Uncapped Liability** | 0.67 (4/6) | 0.44 (4/9) | 0.53 | 0.67 (4/6) | 0.50 (4/8) | 0.57 | 9 | 100.0% (6/6) |

### 3.3 Non-Scored Categories

| Category | Status |
| :--- | :--- |
| **Renewal Term** | not scored automatically (free-text human adjudication required) |
| **Notice Period To Terminate Renewal** | not scored automatically (free-text human adjudication required) |

---

## 4. Date Normalizer Defect & Offline Rescore Comparison

### 4.1 Root Cause of Defect
The original implementation of `normalize_date` relied on `dateutil.parser.parse(text)`. Under standard `dateutil` behavior, any missing date field (day, month, or year) was implicitly populated using `datetime.now()`. As a result:
- Input `"15"` evaluated to `2026-10-15`.
- Input `"2018"` evaluated to `2018-10-04`.
- Input `"March 2018"` evaluated to `2018-03-04`.

This caused scores to fluctuate based on the day the evaluation script was executed and introduced spurious false positives on partial mentions.

### 4.2 Fix and Rescore
`normalize_date` was revised to enforce strict date component completeness using two boundary default sentinels (`datetime(1001, 1, 1)` and `datetime(3001, 12, 31)`). If any component is absent, the outputs diverge and the function deterministically returns `None`.

| Category | Version | Precision | Recall | F1 | TP | FP | FN | Support |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Agreement Date** | Before (dateutil default) | 0.63 (19/30) | 0.90 (19/21) | 0.75 | 19 | 11 | 2 | 21 |
| | **After (strict parsing)** | **0.68 (19/28)** | **0.90 (19/21)** | **0.78** | **19** | **9** | **2** | **21** |
| **Effective Date** | Before (dateutil default) | 0.87 (13/15) | 0.81 (13/16) | 0.84 | 13 | 2 | 3 | 16 |
| | **After (strict parsing)** | **1.00 (13/13)** | **0.81 (13/16)** | **0.90** | **13** | **0** | **3** | **16** |
| **Expiration Date** | Before (dateutil default) | 0.88 (7/8) | 0.50 (7/14) | 0.64 | 7 | 1 | 7 | 14 |
| | **After (strict parsing)** | **0.88 (7/8)** | **0.50 (7/14)** | **0.64** | **7** | **1** | **7** | **14** |

**Impact:** Eliminates 4 false positives across the sample (2 on Agreement Date, 2 on Effective Date). Effective Date precision rises to 100% (13/13).

---

## 5. Parties Matching: Exact-Name vs. Alias-Aware

Because contracts routinely introduce defined-term parenthetical aliases (e.g. `Cisco Systems, Inc. ("Cisco")`), evaluation was conducted under both exact-name matching and defined-term-alias matching:

| Mode | Precision | Recall | F1 | TP | FP | FN | Support |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Exact-Name Only** | 0.49 (59/120) | 0.77 (59/77) | 0.60 | 59 | 61 | 18 | 77 |
| **Defined-Term-Alias Aware** | **0.72 (66/92)** | **0.86 (66/77)** | **0.78** | **66** | **26** | **11** | **77** |

### Breakdown of Discrepancy:
1. **Defined-Term Aliases:** Under exact-name matching, predicting `"Cisco"` when the ground-truth label is `"Cisco Systems, Inc. ("Cisco")"` is penalized as a false positive. In alias-aware mode, aliases declared in parentheticals are treated as valid matches for the party.
2. **Remaining False Positives (26 FP in Alias-Aware):**
   - Entities named elsewhere in the contract (subsidiaries, parent companies, guarantors) that are not primary contracting parties.
   - Minor role words occasionally retained by the model (`affiliate`, `seller`, `agency`).

---

## 6. Ground-Truth Data Quality Observations

Several apparent errors in model predictions are attributable to imperfections in the CUAD dataset ground truth:
1. **Missing Agreement Date Labels:** In 5 of the 30 contracts, CUAD provides no Agreement Date label even though the preamble clearly states an execution date that the model extracted correctly. This deflates reported Agreement Date precision.
2. **Corrupted Date Labels:** Two ground-truth labels in CUAD are truncated or unparseable text (`"04/30/"` and `"/[]/2018"`).
3. **Jurisdiction Splitting:** CUAD splits governing law for `"England and Wales"` into separate rows (`"England"` and `"Wales"`), causing a joint jurisdiction extraction to record an artificial miss.
4. **Parties Typographical Errors:** Ground-truth labels occasionally include typos (e.g. `"Ostenonics"` for Osteonics) or conflate separate parties into single label cells (`"Stryker and Conformis"`). Ground-truth labels were left unedited; their impact is noted here.

---

## 7. Mandatory Statement: Unsupported Categories

> [!WARNING]
> **Cap On Liability, Non-Compete, and Uncapped Liability are NOT supported.**
> 
> The model fails to extract these clauses on the majority of contracts that contain them:
> - **Cap On Liability:** Contract presence recall is **6/16 = 38%** (95% Wilson confidence interval: [0.18, 0.61]).
> - **Non-Compete:** Contract presence recall is **4/8 = 50%**.
> - **Uncapped Liability:** Contract presence recall is **4/8 = 50%**.
> 
> In compliance and legal due-diligence workflows, **a silent omission is the most dangerous failure mode**. When the model identifies a clause, its precision is high (Cap On Liability precision is 6/6 = 100%), but because it misses 50% to 62% of true instances, **these categories must never be presented to customers as automated capabilities**.

### Categories Supported for Human-in-the-Loop Review:
- **Agreement Date:** Recall 19/21 (90%), Precision 19/28 (68%).
- **Effective Date:** Recall 13/16 (81%), Precision 13/13 (100%).
- **Governing Law:** Recall 23/29 (79%), Precision 23/25 (92%).
- **Parties (Alias-Aware):** Recall 66/77 (86%), Precision 66/92 (72%).
- **Termination For Convenience (Presence):** Recall 13/13 (100%), Precision 13/16 (81%).
- **Anti-Assignment (Presence):** Recall 18/22 (82%, 95% CI: [0.62, 0.93]), Precision 18/19 (95%).
- **Change Of Control (Presence):** Recall 9/10 (90%), Precision 9/10 (90%).

---

## 8. Limitations & Evaluation Constraints

To ensure intellectual honesty, the following constraints apply to all interpretations of this data:
1. **Single Open Model on Trial Infrastructure:** The evaluation tested `nvidia/nemotron-3-super-120b-a12b`. It demonstrates what a 120B parameter open model achieves with zero-shot structured prompts, but does not represent the models named in ENTERPRISE_PLAN.md, not evaluated here.
2. **Sample Size:** 30 contracts evaluated once with seed 42. Run-to-run variance, temperature jitter, and sampling distributions were not measured across multiple seeds.
3. **Prompt Development Overlap:** Two contracts in the 30-contract test sample (`Sibannac` and `Ediets`) were included in earlier smoke testing whose failure modes informed prompt structure. While the prompt was not tuned specifically to them, they do not constitute clean out-of-sample holdouts.
4. **Harness Chunker vs. Product Pipeline:** The harness uses fixed 4,000-character line-boundary slicing. The SemanticGraph Cloud product uses semantic AST / structural chunking, which preserves semantic boundaries better than naive character windows.
5. **Metric Incomparability with Published CUAD Benchmarks:** Published CUAD benchmarks use extractive question-answering spans (evaluating SQuAD-style F1 over SQuAD-formatted JSON). This benchmark evaluates structured relational entity and clause extraction with two distinct scoring modes.
