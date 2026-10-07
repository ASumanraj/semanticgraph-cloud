# CUAD Clause Extraction Evaluation Harness (T-909)

## 1. Overview & Dataset Citation

This package implements an automated evaluation harness for scoring contract clause extraction against
the **Contract Understanding Atticus Dataset (CUAD)**.

- **Citation:**
  > Hendrycks et al., *CUAD: An Expert-Annotated NLP Dataset for Legal Contract Review*
  > (NeurIPS 2021 Datasets and Benchmarks), The Atticus Project. CC BY 4.0.
- **Licence:** Creative Commons Attribution 4.0 International (CC BY 4.0)
- **Source Repository:** [`theatticusproject/cuad`](https://huggingface.co/datasets/theatticusproject/cuad)
- **Git Revision:** `a3c393f5d103fd0c516374e4fdff676c8176dcb1`

## 2. Dataset Content Checksum (Recorded Before First Use)

Per §5 of `docs/research/t904-cuad-crosscheck.md` and T-909 Acceptance, content checksums are
recorded before first use rather than relying on access dates:

| File | SHA-256 Checksum | Size (bytes) |
|---|---|---|
| `CUAD_v1/master_clauses.csv` | `4da237bec677bf5b02212d523857cd57a801adde60e8021de063c8cc06823720` | 3,955,428 |

## 3. Scope & Question Mapping

CUAD provides ground truth for **9 of 12** T-904 benchmark questions:

| Question | Description | CUAD Categories | Fit |
|---|---|---|---|
| **Q1** | Parties | `Parties` | Direct |
| **Q2** | Agreement Date | `Agreement Date` | Direct |
| **Q3** | Effective Date | `Effective Date` | Direct |
| **Q4** | Term / Expiration Date | `Expiration Date` | Direct |
| **Q5** | Auto-Renewal | `Renewal Term`, `Notice Period To Terminate Renewal` | Partial |
| **Q6** | Termination for Convenience | `Termination For Convenience` | Direct |
| **Q7** | Governing Law | `Governing Law` | Direct |
| **Q8** | Liability Cap & Uncapped Liability | `Cap On Liability`, `Uncapped Liability` | Direct |
| **Q9** | Cap Exclusions | *(None)* | **Not covered** by CUAD |
| **Q10** | Indemnification | *(None)* | **Not covered** by CUAD |
| **Q11** | Assignment & Change of Control | `Anti-Assignment`, `Change Of Control` | Direct |
| **Q12** | Exclusivity & Non-Compete | `Exclusivity`, `Non-Compete` | Direct |
| **Q13** | Amendment Diff | *(None)* | **Not applicable** (standalone contracts) |

## 4. Evaluation Reporting Policy (Per-Category Scoring)

To ensure that weak categories cannot hide behind strong ones, the harness **never** collapses results into
a single blended score. Reports compute and display precision, recall, and F1 strictly per category.

## 5. Architectural Disclaimers & Boundary Constraints

1. **System Property Inapplicability:**
   CUAD consists of independent, single-contract documents. It cannot and does not test:
   - Temporal / point-in-time graph traversal
   - Tenant isolation and row-level security
   - Decision-log-driven entity resolution
   - Assertion-counted deletion cascades
   - Pipeline latency or throughput

2. **Pretraining Contamination Caveat:**
   CUAD contracts are public SEC EDGAR filings and are likely present in LLM pretraining data.
   Scores obtained on CUAD should be understood as a baseline on public contracts, not a guarantee
   of identical performance on novel private enterprise contracts.

## 6. Binding Data Terms & Privacy Constraints (NVIDIA API Trial)

Trial use is governed by the **NVIDIA API Trial Terms of Service**:
- **Evaluation only:** Trial access is strictly for internal testing and measurement, never production.
- **Provider data retention:** Inputs and outputs sent to the trial endpoint may be retained and used by NVIDIA to train and improve its models.
- **Strict data segregation:** **Public CUAD contract text only.** Never submit customer contracts, interview transcripts, founder notes, or confidential materials to this endpoint.
- **Model distinction:** Figures obtained from the trial endpoint reflect `nvidia/nemotron-3-super-120b-a12b`, **not** production models (Claude 3.5 Sonnet or Gemini 2.5 Flash).
- **No marketing claims:** These benchmark results must never be cited or quoted as product accuracy in customer pitches or investor materials.

## 7. How to Run the Evaluation

### Prerequisites
Set `NVIDIA_API_KEY` in your environment or `.env` file (never commit or print this key).

```bash
# 1. Download CUAD dataset (pinned Hugging Face revision)
python -m evals.cuad.harness download --output-dir evals/cuad/data

# 2. Run model probe across candidate models
python -m evals.cuad.harness probe

# 3. Run development sample (5 contracts, seed 1337, disjoint from test sample)
python -m evals.cuad.harness run --provider nvidia --mode dev

# 4. Run full test sample (30 contracts, seed 42, frozen prompt hash b63f8a79...)
python -m evals.cuad.harness run --provider nvidia --mode test --sample-seed 42 --max-contracts 30
```

Key CLI options for `run`:
- `--provider`: `nvidia` (default for T-227) or `gemini`.
- `--model`: Model ID (defaults to `nvidia/nemotron-3-super-120b-a12b` for NVIDIA).
- `--mode`: `dev` (5 contracts) or `test` (30 contracts).
- `--max-calls`: Hard runaway guard on provider attempts (default: 900).
- `--predictions-dir`: Output directory for JSONL records (default: `evals/cuad/raw_predictions`).

## 8. How to Rescore Offline

The harness supports complete offline rescoring from saved prediction JSONL logs without making any model provider calls or consuming API quota:

```bash
# Rescore offline using saved predictions
python -m evals.cuad.harness rescore --predictions-file evals/cuad/raw_predictions/predictions.jsonl --data-dir evals/cuad/data --parties-mode both
```

The `rescore` command:
1. Re-evaluates date parsing under strict component validation (day, month, year required) and displays a before/after comparison showing false positives eliminated on Agreement Date and Effective Date.
2. Evaluates Parties under both exact-name matching and defined-term-alias matching.
3. Renders the complete benchmark results table with `k/n` on every precision, recall, presence, and quote-found rate.

