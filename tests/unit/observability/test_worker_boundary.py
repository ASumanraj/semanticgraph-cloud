"""Tests for worker boundary tenant propagation (T-209).

Acceptance criteria verified:
- Tenant context crosses the worker boundary explicitly.
- Inbound worker tasks restore tenant context for logging, spans, and metrics.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch
from uuid import uuid4

from semanticgraph.adapters.inbound.workers.tasks.ingestion_tasks import process_document_task
from semanticgraph.domain.models.entities import DocumentStatus, TenantId
from semanticgraph.observability.context import get_current_tenant_id


def test_worker_task_restores_tenant_context():
    """Worker task restores tenant context from header or parameters and clears it on exit."""
    tenant_id = TenantId(uuid4())
    doc_id = uuid4()

    # Verify context before task
    assert get_current_tenant_id() is None

    observed_tenant_during_task: list[TenantId | None] = []

    # Mock container use_case.execute to capture active tenant context inside worker execution
    mock_use_case = MagicMock()

    async def fake_execute(command):
        observed_tenant_during_task.append(get_current_tenant_id())
        mock_res = MagicMock()
        mock_res.status = DocumentStatus.RESOLVED
        mock_res.id = doc_id
        return mock_res

    mock_use_case.execute.side_effect = fake_execute

    with patch(
        "semanticgraph.adapters.inbound.workers.tasks.ingestion_tasks.default_container"
    ) as mock_cont:
        mock_cont.return_value.ingest_document.return_value = mock_use_case

        result = process_document_task(
            tenant_id_str=str(tenant_id.value),
            document_id_str=str(doc_id),
            ontology_dict={"name": "test_ontology"},
        )

    # Verify task returned correct result
    assert result["status"] == "resolved"
    assert result["tenant_id"] == str(tenant_id.value)

    # Verify tenant context was active inside the task
    assert len(observed_tenant_during_task) == 1
    assert observed_tenant_during_task[0] == tenant_id

    # Verify tenant context was cleanly unset after worker task completed
    assert get_current_tenant_id() is None
