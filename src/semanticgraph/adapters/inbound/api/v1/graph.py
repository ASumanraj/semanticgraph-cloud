"""
Inbound Adapter: Knowledge Graph Retrieval Route (v1).

Exposes GET /api/v1/graph for subgraph inspection and exploration.
Per T-218 Slice 3:
- UI-agnostic response schema: nodes, edges, truncated.
- Optional query parameter: with query -> search_subgraph; without query -> get_overview.
- Strictly tenant-scoped via CurrentTenantDep (X-Tenant-ID header), never query parameter.
- Bounded traversal and capped results (depth max 3, entities max 200, edges max 400).
- Honest empty 200 response when tenant has no graph data.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from semanticgraph.adapters.inbound.api.dependencies import CurrentTenantDep
from semanticgraph.composition.container import SubgraphReaderDep
from semanticgraph.domain.models.entities import Edge, GoldenRecord, RawEntity

MAX_ENTITIES = 200
MAX_EDGES = 400
MAX_DEPTH = 3


class ProvenanceResponse(BaseModel):
    chunk_id: UUID = Field(description="UUID of the semantic chunk containing the evidence")
    start_offset: int = Field(description="0-indexed character start offset within the chunk")
    end_offset: int = Field(description="Character end offset within the chunk")
    quote: str = Field(description="Exact verbatim quote from the chunk text")


class GraphNodeResponse(BaseModel):
    id: UUID = Field(description="Entity or Golden Record UUID")
    name: str = Field(description="Entity surface name or canonical name")
    entity_type: str = Field(description="Ontological entity type")
    kind: str = Field(description="Node kind: raw_entity or golden_record")
    provenance: ProvenanceResponse | None = Field(
        default=None, description="Source evidence span from extraction"
    )


class GraphEdgeResponse(BaseModel):
    id: UUID = Field(description="Edge UUID")
    source: UUID = Field(description="Source entity UUID")
    target: UUID = Field(description="Target entity UUID")
    edge_type: str = Field(description="Ontological edge type")
    weight: float = Field(default=1.0, description="Edge weight / confidence")
    valid_from: datetime | None = Field(default=None, description="Bitemporal valid-from timestamp")
    valid_to: datetime | None = Field(default=None, description="Bitemporal valid-to timestamp")
    provenance: ProvenanceResponse | None = Field(
        default=None, description="Source evidence span from extraction"
    )


class GraphResponse(BaseModel):
    nodes: list[GraphNodeResponse] = Field(default_factory=list, description="Graph nodes")
    edges: list[GraphEdgeResponse] = Field(default_factory=list, description="Graph edges")
    truncated: bool = Field(default=False, description="Whether the result was truncated by caps")


router = APIRouter(
    prefix="/api/v1/graph",
    tags=["Graph"],
)


@router.get("", response_model=GraphResponse)
async def get_graph(
    tenant: CurrentTenantDep,
    subgraph_reader: SubgraphReaderDep,
    query: Annotated[
        str | None,
        Query(max_length=200, description="Optional search query to locate seed entities"),
    ] = None,
    depth: Annotated[
        int,
        Query(ge=0, description="Graph expansion depth (default 2, clamped to 3)"),
    ] = 2,
) -> GraphResponse:
    """Retrieve the tenant's knowledge graph or a query-focused subgraph.

    Tenant scoping is strictly enforced via CurrentTenantDep from the X-Tenant-ID header.
    Note: CurrentTenantDep is an unsigned header for scoping, not verified authentication (Stage 5).
    """
    clamped_depth = min(max(0, depth), MAX_DEPTH)
    truncated = False

    if query is not None and query.strip():
        items = await subgraph_reader.search_subgraph(
            tenant, query=query.strip(), depth=clamped_depth
        )
        raw_entities: list[RawEntity | GoldenRecord] = [
            item for item in items if isinstance(item, (RawEntity, GoldenRecord))
        ]
        raw_edges: list[Edge] = [item for item in items if isinstance(item, Edge)]

        if len(raw_entities) > MAX_ENTITIES:
            truncated = True
            raw_entities = raw_entities[:MAX_ENTITIES]

        allowed_ids = {e.id.value if hasattr(e.id, "value") else e.id for e in raw_entities}
        filtered_edges = [
            e
            for e in raw_edges
            if (
                e.source_entity_id.value
                if hasattr(e.source_entity_id, "value")
                else e.source_entity_id
            )
            in allowed_ids
            and (
                e.target_entity_id.value
                if hasattr(e.target_entity_id, "value")
                else e.target_entity_id
            )
            in allowed_ids
        ]
        if len(filtered_edges) < len(raw_edges) or len(filtered_edges) > MAX_EDGES:
            truncated = True
            filtered_edges = filtered_edges[:MAX_EDGES]
    else:
        # Request 1 extra to detect truncation accurately
        raw_entities, raw_edges = await subgraph_reader.get_overview(
            tenant, limit_entities=MAX_ENTITIES + 1, limit_edges=MAX_EDGES + 1
        )
        if len(raw_entities) > MAX_ENTITIES:
            truncated = True
            raw_entities = raw_entities[:MAX_ENTITIES]

        allowed_ids = {e.id.value if hasattr(e.id, "value") else e.id for e in raw_entities}
        filtered_edges = [
            e
            for e in raw_edges
            if (
                e.source_entity_id.value
                if hasattr(e.source_entity_id, "value")
                else e.source_entity_id
            )
            in allowed_ids
            and (
                e.target_entity_id.value
                if hasattr(e.target_entity_id, "value")
                else e.target_entity_id
            )
            in allowed_ids
        ]
        if len(raw_edges) > MAX_EDGES or len(filtered_edges) < len(raw_edges):
            if len(raw_edges) > MAX_EDGES:
                truncated = True
            filtered_edges = filtered_edges[:MAX_EDGES]

    nodes_response: list[GraphNodeResponse] = []
    for ent in raw_entities:
        ent_id = ent.id.value if hasattr(ent.id, "value") else ent.id
        ent_name = ent.canonical_name if isinstance(ent, GoldenRecord) else ent.name
        ent_kind = ent.kind.value if hasattr(ent.kind, "value") else str(ent.kind)
        ent_prov: ProvenanceResponse | None = None
        if isinstance(ent, RawEntity) and ent.spans:
            s = ent.spans[0]
            c_id = s.chunk_id.value if hasattr(s.chunk_id, "value") else s.chunk_id
            ent_prov = ProvenanceResponse(
                chunk_id=c_id,
                start_offset=s.start_offset,
                end_offset=s.end_offset,
                quote=s.quote,
            )
        nodes_response.append(
            GraphNodeResponse(
                id=ent_id,
                name=ent_name,
                entity_type=ent.entity_type,
                kind=ent_kind,
                provenance=ent_prov,
            )
        )

    edges_response: list[GraphEdgeResponse] = []
    for edge in filtered_edges:
        edge_id = edge.id.value if hasattr(edge.id, "value") else edge.id
        src_id = (
            edge.source_entity_id.value
            if hasattr(edge.source_entity_id, "value")
            else edge.source_entity_id
        )
        tgt_id = (
            edge.target_entity_id.value
            if hasattr(edge.target_entity_id, "value")
            else edge.target_entity_id
        )
        edge_prov: ProvenanceResponse | None = None
        if edge.spans:
            s = edge.spans[0]
            c_id = s.chunk_id.value if hasattr(s.chunk_id, "value") else s.chunk_id
            edge_prov = ProvenanceResponse(
                chunk_id=c_id,
                start_offset=s.start_offset,
                end_offset=s.end_offset,
                quote=s.quote,
            )
        edges_response.append(
            GraphEdgeResponse(
                id=edge_id,
                source=src_id,
                target=tgt_id,
                edge_type=edge.edge_type,
                weight=edge.weight,
                valid_from=edge.valid_from,
                valid_to=edge.valid_to,
                provenance=edge_prov,
            )
        )

    return GraphResponse(
        nodes=nodes_response,
        edges=edges_response,
        truncated=truncated,
    )
