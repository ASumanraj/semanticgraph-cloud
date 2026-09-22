"""
Inbound Adapter: Fact Retrieval Route (v1).

Per T-110 acceptance criteria:
- GET /api/v1/facts/{id} returns claim and evidence spans (chunk_id, offsets, quote).
- Enforces strict tenant isolation via X-Tenant-ID (stand-in until Stage 5).
- Returns 404 if fact does not exist or has 0 live assertions (irreversible rule 4).
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter
from pydantic import BaseModel, Field

from semanticgraph.adapters.inbound.api.dependencies import CurrentTenantDep
from semanticgraph.composition.container import AssertionStoreDep
from semanticgraph.domain.exceptions import DomainException


class EvidenceSpanResponse(BaseModel):
    chunk_id: UUID = Field(description="UUID of the semantic chunk containing the evidence")
    start_offset: int = Field(description="0-indexed character start offset within the chunk")
    end_offset: int = Field(description="Character end offset within the chunk")
    quote: str = Field(description="Exact verbatim quote from the chunk text")


class FactResponse(BaseModel):
    id: UUID = Field(description="Unique identifier of the Fact")
    claim: str = Field(description="The factual claim asserted")
    evidence_spans: list[EvidenceSpanResponse] = Field(
        default_factory=list, description="Evidence spans supporting this claim"
    )


router = APIRouter(
    prefix="/api/v1/facts",
    tags=["Facts"],
)


@router.get(
    "/{fact_id}",
    response_model=FactResponse,
    responses={
        404: {"description": "Fact not found or no live assertions remain"},
    },
)
async def get_fact(
    tenant: CurrentTenantDep,
    fact_id: UUID,
    assertion_store: AssertionStoreDep,
) -> FactResponse:
    """Retrieve a Fact and its supporting EvidenceSpans by ID.

    Tenant context is extracted from X-Tenant-ID (stand-in until Stage 5 auth).
    Facts die by assertion count: a fact with 0 live assertions returns 404.
    """
    fact = await assertion_store.get_fact(tenant, fact_id)
    if fact is None or not fact.is_alive:
        raise DomainException(
            message=f"Fact '{fact_id}' not found",
            code="FACT_NOT_FOUND",
        )

    evidence_spans: list[EvidenceSpanResponse] = []
    for assertion in fact.assertions:
        for span in assertion.spans:
            chunk_id_val = span.chunk_id.value if hasattr(span.chunk_id, "value") else span.chunk_id
            evidence_spans.append(
                EvidenceSpanResponse(
                    chunk_id=chunk_id_val,
                    start_offset=span.start_offset,
                    end_offset=span.end_offset,
                    quote=span.quote,
                )
            )

    return FactResponse(
        id=fact.id,
        claim=fact.claim,
        evidence_spans=evidence_spans,
    )
