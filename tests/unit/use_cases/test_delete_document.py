"""Unit tests for DeleteDocumentUseCase (T-206).

Tests the document deletion cascade interface using in-memory fakes.
Upholds:
- Irreversible Rule 4: Facts die by assertion count.
- Single-transaction cascade across chunks, assertions, facts, embeddings,
  caches, summaries, eval fixtures.
"""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from semanticgraph.application.use_cases.delete_document import (
    DeleteDocumentCommand,
    DeleteDocumentUseCase,
    DeletionRepositoryPort,
    DeletionResult,
)
from semanticgraph.domain.models.entities import TenantId


class FakeDeletionRepository(DeletionRepositoryPort):
    """In-memory fake implementing DeletionRepositoryPort."""

    def __init__(self) -> None:
        self.calls: list[tuple[TenantId, UUID]] = []
        self.result_to_return: DeletionResult | None = None

    async def delete_document_cascade(
        self, tenant_id: TenantId, document_id: UUID
    ) -> DeletionResult:
        self.calls.append((tenant_id, document_id))
        if self.result_to_return is not None:
            return self.result_to_return
        return DeletionResult(
            document_id=document_id,
            deleted_chunks_count=3,
            deleted_assertions_count=5,
            deleted_facts_count=2,
            retained_facts_count=1,
            deleted_mentions_count=4,
            purged_embeddings_count=3,
            purged_caches_count=1,
            purged_summaries_count=1,
            purged_eval_fixtures_count=1,
            rematerialized_golden_records_count=1,
            deleted_golden_records_count=1,
        )


@pytest.fixture
def fake_repo() -> FakeDeletionRepository:
    return FakeDeletionRepository()


@pytest.fixture
def use_case(fake_repo: FakeDeletionRepository) -> DeleteDocumentUseCase:
    return DeleteDocumentUseCase(deletion_repo=fake_repo)


@pytest.mark.asyncio
async def test_delete_document_executes_cascade(
    use_case: DeleteDocumentUseCase, fake_repo: FakeDeletionRepository
) -> None:
    tenant_id = TenantId(value=uuid4())
    doc_id = uuid4()
    command = DeleteDocumentCommand(tenant_id=tenant_id, document_id=doc_id)

    result = await use_case.execute(command)

    assert len(fake_repo.calls) == 1
    assert fake_repo.calls[0] == (tenant_id, doc_id)
    assert result.document_id == doc_id
    assert result.deleted_chunks_count == 3
    assert result.deleted_assertions_count == 5
    assert result.deleted_facts_count == 2
    assert result.retained_facts_count == 1
    assert result.purged_embeddings_count == 3
    assert result.purged_caches_count == 1
    assert result.purged_summaries_count == 1
    assert result.purged_eval_fixtures_count == 1


@pytest.mark.asyncio
async def test_delete_document_command_is_frozen() -> None:
    tenant_id = TenantId(value=uuid4())
    doc_id = uuid4()
    cmd = DeleteDocumentCommand(tenant_id=tenant_id, document_id=doc_id)

    with pytest.raises((AttributeError, TypeError)):
        cmd.document_id = uuid4()  # type: ignore[misc]


@pytest.mark.asyncio
async def test_deletion_result_summary_properties() -> None:
    doc_id = uuid4()
    res = DeletionResult(
        document_id=doc_id,
        deleted_chunks_count=2,
        deleted_assertions_count=3,
        deleted_facts_count=1,
        retained_facts_count=2,
        deleted_mentions_count=2,
        purged_embeddings_count=2,
        purged_caches_count=1,
        purged_summaries_count=1,
        purged_eval_fixtures_count=1,
        rematerialized_golden_records_count=1,
        deleted_golden_records_count=0,
    )
    assert res.total_records_erased == 13
    assert res.facts_died is True
    assert res.facts_survived is True
