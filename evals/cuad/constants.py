"""Constants, citations, and dataset checksums for the CUAD eval harness (T-909).

Per T-909 Acceptance:
- CUAD is cited per its licence (Hendrycks et al., NeurIPS 2021, CC BY 4.0)
  wherever a score from it is reported.
- A dataset checksum is recorded before first use (§5 of the crosscheck report),
  not just an access date.
- No claim is made that a CUAD-based score says anything about temporal history,
  tenant isolation, resolution decisions or deletion.
- Results state plainly that CUAD's contracts are likely present in model
  pretraining data.
"""

from __future__ import annotations

# Official Citation and Licence
CUAD_CITATION = (
    "Hendrycks et al., CUAD: An Expert-Annotated NLP Dataset for Legal Contract Review "
    "(NeurIPS 2021 Datasets and Benchmarks), The Atticus Project. CC BY 4.0."
)
CUAD_LICENCE = "CC BY 4.0"
CUAD_SOURCE_REPO = "theatticusproject/cuad"
CUAD_REVISION = "a3c393f5d103fd0c516374e4fdff676c8176dcb1"

# Dataset SHA-256 Checksum recorded before first use (§5 of t904-cuad-crosscheck.md)
MASTER_CLAUSES_CSV_SHA256 = "4da237bec677bf5b02212d523857cd57a801adde60e8021de063c8cc06823720"
MASTER_CLAUSES_CSV_SIZE_BYTES = 3955428

# Mandatory Disclaimers and Limitations
DISCLAIMERS = {
    "no_system_property_claims": (
        "CUAD consists of independent, standalone contracts with single-contract clause labels. "
        "It says nothing about, and cannot be used to test, temporal history, tenant isolation, "
        "resolution decisions, assertion-counted deletion, or latency. Those are system properties "
        "operating across multiple documents and tenants, not properties testable by CUAD."
    ),
    "pretraining_contamination_caveat": (
        "CUAD's contracts are public EDGAR filings and are likely present in LLM pretraining "
        "corpora, which may inflate model extraction scores relative to proprietary "
        "enterprise contracts."
    ),
    "coverage_limitations": (
        "CUAD covers 9 of 12 T-904 benchmark questions (Q1–Q8, Q11, Q12). It has no signal for "
        "liability cap exclusions (Q9) or indemnity (Q10), and cannot evaluate amendment diffing "
        "(Q13) by construction."
    ),
}
