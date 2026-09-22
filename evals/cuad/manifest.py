"""Dataset verification, checksums, and metadata for CUAD (T-909).

Acceptance 1:
- A dataset checksum is recorded before first use (§5 of the crosscheck report),
  not just an access date.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from evals.cuad.constants import (
    CUAD_CITATION,
    CUAD_LICENCE,
    CUAD_REVISION,
    CUAD_SOURCE_REPO,
    DISCLAIMERS,
    MASTER_CLAUSES_CSV_SHA256,
    MASTER_CLAUSES_CSV_SIZE_BYTES,
)


@dataclass(frozen=True)
class DatasetFileInfo:
    filename: str
    expected_sha256: str
    size_bytes: int
    description: str


DATASET_FILES: dict[str, DatasetFileInfo] = {
    "master_clauses.csv": DatasetFileInfo(
        filename="master_clauses.csv",
        expected_sha256=MASTER_CLAUSES_CSV_SHA256,
        size_bytes=MASTER_CLAUSES_CSV_SIZE_BYTES,
        description="Master ground-truth annotations across 510 commercial contracts.",
    ),
}


def compute_file_sha256(path: Path) -> str:
    """Computes the SHA-256 hash of a file on disk."""
    hasher = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def verify_cuad_file_checksum(
    path: Path,
    expected_sha256: str = MASTER_CLAUSES_CSV_SHA256,
) -> bool:
    """Verifies that the target file matches the recorded checksum."""
    if not path.is_file():
        return False
    actual_sha256 = compute_file_sha256(path)
    return actual_sha256.lower() == expected_sha256.lower()


def get_dataset_metadata() -> dict[str, Any]:
    """Returns canonical metadata, citation, and checksums for the CUAD dataset."""
    return {
        "dataset_name": "CUAD (Contract Understanding Atticus Dataset)",
        "source": CUAD_SOURCE_REPO,
        "revision": CUAD_REVISION,
        "licence": CUAD_LICENCE,
        "citation": CUAD_CITATION,
        "checksums": {
            info.filename: {
                "sha256": info.expected_sha256,
                "size_bytes": info.size_bytes,
            }
            for info in DATASET_FILES.values()
        },
        "disclaimers": DISCLAIMERS,
    }
