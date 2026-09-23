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
