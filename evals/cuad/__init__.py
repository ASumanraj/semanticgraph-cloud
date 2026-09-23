"""CUAD (Contract Understanding Atticus Dataset) Clause Extraction Evaluation Harness (T-909).

Acceptance criteria satisfied:
1. Dataset checksum recorded before first use.
2. Official citation (Hendrycks et al., NeurIPS 2021, CC BY 4.0) included on all outputs.
3. Scoring reports precision/recall per CUAD category, not one blended number.
4. No claims made regarding temporal history, tenant isolation, resolution, or deletion.
5. Caveats clearly state CUAD contracts are public EDGAR filings likely in pretraining data.
"""

from evals.cuad.constants import (
    CUAD_CITATION,
    CUAD_LICENCE,
    CUAD_REVISION,
    CUAD_SOURCE_REPO,
    DISCLAIMERS,
    MASTER_CLAUSES_CSV_SHA256,
    MASTER_CLAUSES_CSV_SIZE_BYTES,
)
from evals.cuad.harness import CUADEvalHarness, build_cuad_ontology
from evals.cuad.loader import CUADContractAnnotation, load_master_clauses_csv
from evals.cuad.manifest import get_dataset_metadata, verify_cuad_file_checksum
from evals.cuad.mapping import (
    MappingFit,
    QuestionMapping,
    get_all_cuad_target_categories,
    get_supported_question_mappings,
    get_unsupported_question_mappings,
)
from evals.cuad.metrics import (
    CategoryMetrics,
    CUADEvaluationReport,
    compute_category_metrics,
)

__all__ = [
    "CUAD_CITATION",
    "CUAD_LICENCE",
    "CUAD_REVISION",
    "CUAD_SOURCE_REPO",
    "DISCLAIMERS",
    "MASTER_CLAUSES_CSV_SHA256",
    "MASTER_CLAUSES_CSV_SIZE_BYTES",
    "CUADContractAnnotation",
    "CUADEvalHarness",
    "CUADEvaluationReport",
    "CategoryMetrics",
    "MappingFit",
    "QuestionMapping",
    "build_cuad_ontology",
    "compute_category_metrics",
    "get_all_cuad_target_categories",
    "get_dataset_metadata",
    "get_supported_question_mappings",
    "get_unsupported_question_mappings",
    "load_master_clauses_csv",
    "verify_cuad_file_checksum",
]
