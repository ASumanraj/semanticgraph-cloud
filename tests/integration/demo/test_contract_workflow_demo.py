"""Integration test for the Commercial Contracts Workflow Demonstration.

Executes the full end-to-end demo and verifies all 5 Irreversible Rules:
1. Provenance is mandatory (spans located deterministically from verbatim quotes).
2. Tenant isolation fails closed under PostgreSQL RLS.
3. Non-destructive resolution preserves human precedence over model.
4. Facts die by assertion count; 0-assertion facts pruned; shared facts survive.
5. Ontologies are immutable; extraction runs stamped with ontology version.
"""

from __future__ import annotations

import os

import psycopg
import pytest
from scripts.demo_contract_workflow import run_contract_workflow_demo

DEFAULT_PG_URL = "postgresql://user:password@localhost:5432/semanticgraph"


def _postgres_is_available() -> bool:
    candidate = os.environ.get("DATABASE_URL") or DEFAULT_PG_URL
    if not candidate.startswith("postgres"):
        return False
    try:
        conn = psycopg.connect(candidate, connect_timeout=2)
        conn.close()
        return True
    except Exception:
        return False


@pytest.mark.asyncio
async def test_commercial_contracts_workflow_demo():
    """Runs the contract workflow demonstration and asserts all invariants hold."""
    if not _postgres_is_available():
        pytest.skip("PostgreSQL is not reachable for integration test")

    results = await run_contract_workflow_demo()

    assert results.get("immutability") is True, "Rule 5: Ontology immutability must be enforced"
    assert results.get("provenance_spans") is True, "Rule 1: Provenance spans must be extracted"
    assert results.get("human_precedence") is True, "Rule 3: Human precedence must outrank model"
    assert results.get("assertion_counted_deletion") is True, (
        "Rule 4: Facts must die by assertion count"
    )
    assert results.get("tenant_isolation") is True, "Rule 2: Tenant isolation must fail closed"
