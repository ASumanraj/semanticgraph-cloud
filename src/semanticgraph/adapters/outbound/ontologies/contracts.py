"""Pre-built commercial contracts vertical ontology pack loader.

Loads ontologies/contracts/ontology.yaml into a validated domain Ontology instance.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from semanticgraph.domain.models.entities import Ontology, TenantId

CONTRACTS_ONTOLOGY_DIR = Path(__file__).resolve().parents[5] / "ontologies" / "contracts"
CONTRACTS_YAML_PATH = CONTRACTS_ONTOLOGY_DIR / "ontology.yaml"
CONTRACTS_CORPUS_DIR = CONTRACTS_ONTOLOGY_DIR / "corpus"


def load_contracts_ontology_spec(path: Path | None = None) -> dict[str, Any]:
    """Read the YAML definition for the commercial contracts vertical pack."""
    spec_path = path or CONTRACTS_YAML_PATH
    if not spec_path.exists():
        raise FileNotFoundError(f"Contracts ontology file not found at {spec_path}")

    content = spec_path.read_text(encoding="utf-8")
    parsed = yaml.safe_load(content)
    if not isinstance(parsed, dict):
        raise ValueError(f"Invalid ontology YAML content at {spec_path}")
    return parsed


def build_contracts_ontology(
    tenant_id: TenantId,
    path: Path | None = None,
    version: int = 1,
) -> Ontology:
    """Instantiate a domain Ontology entity from the contracts pack for a given tenant."""
    spec = load_contracts_ontology_spec(path)
    entity_types = [et["name"] for et in spec.get("entity_types", [])]
    edge_types = [et["name"] for et in spec.get("edge_types", [])]

    return Ontology(
        tenant_id=tenant_id,
        name=spec.get("name", "commercial_contracts"),
        version=version,
        allowed_entity_types=entity_types,
        allowed_edge_types=edge_types,
        is_published=True,
    )


def load_sample_contract(filename: str) -> str:
    """Load sample text from the contracts corpus."""
    file_path = CONTRACTS_CORPUS_DIR / filename
    if not file_path.exists():
        raise FileNotFoundError(f"Sample contract {filename} not found at {file_path}")
    return file_path.read_text(encoding="utf-8")
