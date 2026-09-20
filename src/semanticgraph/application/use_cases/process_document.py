"""
Use Case: Process Document.

Delegates to the canonical IngestDocumentUseCase pipeline.
Maintained for backwards-compatibility with workers or existing callers.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from semanticgraph.application.ports.outbound.document_repository import DocumentRepositoryPort
from semanticgraph.application.ports.outbound.graph_repository import GraphRepositoryPort
from semanticgraph.application.ports.outbound.llm_gateway import LLMGatewayPort
from semanticgraph.application.ports.outbound.task_publisher import TaskPublisherPort
from semanticgraph.application.use_cases.ingest_document import (
    IngestDocumentCommand,
    IngestDocumentUseCase,
)
from semanticgraph.domain.models.entities import (
    Document,
    DocumentStatus,
    Ontology,
    TenantId,
)


@dataclass
class ProcessDocumentCommand:
    tenant_id: TenantId
    document_id: UUID
    ontology: Ontology


class ProcessDocumentUseCase:
    """Delegates to the canonical IngestDocumentUseCase."""

    def __init__(
        self,
        document_repo: DocumentRepositoryPort,
        graph_repo: GraphRepositoryPort,
        llm_gateway: LLMGatewayPort,
        task_publisher: TaskPublisherPort,
    ) -> None:
        self._ingest_use_case = IngestDocumentUseCase(
            document_repo=document_repo,
            graph_repo=graph_repo,
            llm_gateway=llm_gateway,
            task_publisher=task_publisher,
        )

    async def execute(self, command: ProcessDocumentCommand) -> Document:
        return await self._ingest_use_case.execute(
            IngestDocumentCommand(
                tenant_id=command.tenant_id,
                document_id=command.document_id,
                ontology=command.ontology,
                status=DocumentStatus.RESOLVED,
            )
        )
