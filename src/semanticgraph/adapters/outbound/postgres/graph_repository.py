"""
PostgreSQL Graph Repository: Persistence and Retrieval for Entities and Edges.

Satisfies:
- EntityStorePort (save_raw_entities, save_edges, find_similar_entities)
- SubgraphReaderPort (search_subgraph)

Upholds:
- Irreversible Rule 1: Provenance is mandatory (chunk_id and valid character span).
- Irreversible Rule 2: Tenant isolation fails closed under transaction-scoped SET LOCAL.
- Idempotent and retry-safe: duplicate writes on same entities/edges do not duplicate rows.
- Deep interface: hidden recursive CTE traversal behind depth-bounded subgraph search.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from semanticgraph.adapters.outbound.postgres.models import SQLEdge, SQLRawEntity
from semanticgraph.domain.models.entities import (
    ChunkId,
    Edge,
    EntityId,
    EntityKind,
    EvidenceSpan,
    GoldenRecord,
    RawEntity,
    ResolutionStatus,
    TenantId,
)


def _validate_entity_provenance(entity: RawEntity) -> EvidenceSpan:
    if not entity.spans:
        raise ValueError(
            f"Entity '{entity.name}' has no evidence span; provenance is mandatory per Rule 1"
        )
    span = entity.spans[0]
    if span.chunk_id is None or span.chunk_id.value is None:
        raise ValueError(
            f"Entity '{entity.name}' evidence span missing chunk_id; Rule 1 requires provenance"
        )
    if (
        span.start_offset is None
        or span.end_offset is None
        or span.start_offset < 0
        or span.end_offset < span.start_offset
    ):
        raise ValueError(
            f"Entity '{entity.name}' evidence span has invalid offsets "
            f"[{span.start_offset}, {span.end_offset}]"
        )
    if not span.quote or not isinstance(span.quote, str) or not span.quote.strip():
        raise ValueError(
            f"Entity '{entity.name}' evidence span has empty or invalid quote; "
            "Rule 1 requires provenance"
        )
    return span


def _validate_edge_provenance(edge: Edge) -> EvidenceSpan:
    if not edge.spans:
        raise ValueError(
            f"Edge '{edge.edge_type}' has no evidence span; provenance is mandatory per Rule 1"
        )
    span = edge.spans[0]
    if span.chunk_id is None or span.chunk_id.value is None:
        raise ValueError(
            f"Edge '{edge.edge_type}' evidence span missing chunk_id; Rule 1 requires provenance"
        )
    if (
        span.start_offset is None
        or span.end_offset is None
        or span.start_offset < 0
        or span.end_offset < span.start_offset
    ):
        raise ValueError(
            f"Edge '{edge.edge_type}' evidence span has invalid offsets "
            f"[{span.start_offset}, {span.end_offset}]"
        )
    if not span.quote or not isinstance(span.quote, str) or not span.quote.strip():
        raise ValueError(
            f"Edge '{edge.edge_type}' evidence span has empty or invalid quote; "
            "Rule 1 requires provenance"
        )
    return span


def _escape_like(pattern: str) -> str:
    """Escapes SQL LIKE wildcard characters ('%', '_', and '\\')."""
    return pattern.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _map_sql_entity_to_domain(row: SQLRawEntity) -> RawEntity | GoldenRecord:
    if row.kind == "golden_record":
        return GoldenRecord(
            id=EntityId(value=row.id),
            tenant_id=TenantId(value=row.tenant_id),
            canonical_name=row.name,
            entity_type=row.entity_type,
            kind=EntityKind.GOLDEN_RECORD,
        )
    return RawEntity(
        id=EntityId(value=row.id),
        tenant_id=TenantId(value=row.tenant_id),
        name=row.name,
        entity_type=row.entity_type,
        golden_record_id=EntityId(value=row.golden_record_id) if row.golden_record_id else None,
        resolution_status=ResolutionStatus(row.resolution_status),
        kind=EntityKind(row.kind),
        spans=[
            EvidenceSpan(
                chunk_id=ChunkId(value=row.chunk_id),
                start_offset=row.start_offset,
                end_offset=row.end_offset,
                quote=row.quote,
            )
        ],
    )


class PostgresEntityStore:
    """Outbound adapter implementing EntityStorePort.

    Persists raw extracted entities and edges with mandatory provenance.
    Enforces that edge endpoints point to real, persisted entity rows.
    Guarantees idempotent and retry-safe writes.
    """

    def __init__(self, session_factory: Callable[[], AsyncSession]) -> None:
        self._session_factory = session_factory

    @asynccontextmanager
    async def _tenant_session(self, tenant_id: TenantId) -> AsyncIterator[AsyncSession]:
        session = self._session_factory()
        if session.in_transaction():
            bind = session.bind or session.get_bind()
            if bind.dialect.name == "postgresql":
                await session.execute(
                    text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"),
                    {"tenant_id": str(tenant_id.value)},
                )
            yield session
        else:
            async with session, session.begin():
                bind = session.bind or session.get_bind()
                if bind.dialect.name == "postgresql":
                    await session.execute(
                        text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"),
                        {"tenant_id": str(tenant_id.value)},
                    )
                yield session

    async def save_raw_entities(self, tenant_id: TenantId, entities: list[RawEntity]) -> None:
        """Persists raw extracted entities for a tenant.

        Idempotent and retry-safe: duplicate writes update metadata without duplicating rows.
        Fails loudly if provenance is missing or invalid (Rule 1).
        """
        if not entities:
            return

        validated_spans = [_validate_entity_provenance(e) for e in entities]

        async with self._tenant_session(tenant_id) as session:
            for entity, span in zip(entities, validated_spans, strict=True):
                # 1. Check by primary key ID
                res = await session.execute(
                    select(SQLRawEntity).where(
                        SQLRawEntity.id == entity.id.value,
                        SQLRawEntity.tenant_id == tenant_id.value,
                    )
                )
                sql_entity = res.scalars().first()

                if not sql_entity:
                    # 2. Check if an entity with same chunk_id, name, and span already exists
                    # (handles retried extraction steps with newly generated UUIDs)
                    res_match = await session.execute(
                        select(SQLRawEntity).where(
                            SQLRawEntity.tenant_id == tenant_id.value,
                            SQLRawEntity.chunk_id == span.chunk_id.value,
                            SQLRawEntity.name == entity.name,
                            SQLRawEntity.start_offset == span.start_offset,
                            SQLRawEntity.end_offset == span.end_offset,
                        )
                    )
                    sql_entity = res_match.scalars().first()
                    if sql_entity:
                        entity.id = EntityId(value=sql_entity.id)
                        sql_entity.updated_at = datetime.now(UTC)
                        session.add(sql_entity)
                        continue

                    # Insert new entity row
                    sql_entity = SQLRawEntity(
                        id=entity.id.value,
                        tenant_id=tenant_id.value,
                        name=entity.name,
                        entity_type=entity.entity_type,
                        golden_record_id=(
                            entity.golden_record_id.value if entity.golden_record_id else None
                        ),
                        resolution_status=(
                            entity.resolution_status.value
                            if isinstance(entity.resolution_status, ResolutionStatus)
                            else str(entity.resolution_status)
                        ),
                        kind=(
                            entity.kind.value
                            if isinstance(entity.kind, EntityKind)
                            else str(entity.kind)
                        ),
                        chunk_id=span.chunk_id.value,
                        start_offset=span.start_offset,
                        end_offset=span.end_offset,
                        quote=span.quote,
                        created_at=datetime.now(UTC),
                        updated_at=datetime.now(UTC),
                    )
                    session.add(sql_entity)
                else:
                    sql_entity.name = entity.name
                    sql_entity.entity_type = entity.entity_type
                    sql_entity.resolution_status = (
                        entity.resolution_status.value
                        if isinstance(entity.resolution_status, ResolutionStatus)
                        else str(entity.resolution_status)
                    )
                    sql_entity.golden_record_id = (
                        entity.golden_record_id.value if entity.golden_record_id else None
                    )
                    sql_entity.updated_at = datetime.now(UTC)
                    session.add(sql_entity)

    async def save_edges(self, tenant_id: TenantId, edges: list[Edge]) -> None:
        """Persists graph edges connecting entities.

        Validates that edge endpoints point to real persisted entity rows.
        Idempotent and retry-safe: duplicate writes update metadata without duplicating rows.
        Fails loudly if provenance is missing or invalid (Rule 1).
        """
        if not edges:
            return

        validated_spans = [_validate_edge_provenance(e) for e in edges]

        async with self._tenant_session(tenant_id) as session:
            for edge, span in zip(edges, validated_spans, strict=True):
                # Watch 2: Verify endpoints exist in entities table for this tenant
                res_src = await session.execute(
                    select(SQLRawEntity.id).where(
                        SQLRawEntity.id == edge.source_entity_id.value,
                        SQLRawEntity.tenant_id == tenant_id.value,
                    )
                )
                if not res_src.scalars().first():
                    raise ValueError(
                        f"Edge '{edge.id}' source_entity_id '{edge.source_entity_id.value}' "
                        f"does not exist in entities table for tenant {tenant_id.value}"
                    )

                res_tgt = await session.execute(
                    select(SQLRawEntity.id).where(
                        SQLRawEntity.id == edge.target_entity_id.value,
                        SQLRawEntity.tenant_id == tenant_id.value,
                    )
                )
                if not res_tgt.scalars().first():
                    raise ValueError(
                        f"Edge '{edge.id}' target_entity_id '{edge.target_entity_id.value}' "
                        f"does not exist in entities table for tenant {tenant_id.value}"
                    )

                # Check by primary key ID
                res_edge = await session.execute(
                    select(SQLEdge).where(
                        SQLEdge.id == edge.id,
                        SQLEdge.tenant_id == tenant_id.value,
                    )
                )
                sql_edge = res_edge.scalars().first()

                if not sql_edge:
                    # Check if an edge with same endpoints, chunk, type, and span already exists
                    res_edge_match = await session.execute(
                        select(SQLEdge).where(
                            SQLEdge.tenant_id == tenant_id.value,
                            SQLEdge.chunk_id == span.chunk_id.value,
                            SQLEdge.source_entity_id == edge.source_entity_id.value,
                            SQLEdge.target_entity_id == edge.target_entity_id.value,
                            SQLEdge.edge_type == edge.edge_type,
                            SQLEdge.start_offset == span.start_offset,
                            SQLEdge.end_offset == span.end_offset,
                        )
                    )
                    sql_edge = res_edge_match.scalars().first()
                    if sql_edge:
                        sql_edge.weight = edge.weight
                        sql_edge.valid_from = edge.valid_from
                        sql_edge.valid_to = edge.valid_to
                        session.add(sql_edge)
                        continue

                    # Insert new edge row
                    sql_edge = SQLEdge(
                        id=edge.id,
                        tenant_id=tenant_id.value,
                        source_entity_id=edge.source_entity_id.value,
                        target_entity_id=edge.target_entity_id.value,
                        edge_type=edge.edge_type,
                        weight=edge.weight,
                        valid_from=edge.valid_from,
                        valid_to=edge.valid_to,
                        chunk_id=span.chunk_id.value,
                        start_offset=span.start_offset,
                        end_offset=span.end_offset,
                        quote=span.quote,
                        created_at=datetime.now(UTC),
                    )
                    session.add(sql_edge)
                else:
                    sql_edge.weight = edge.weight
                    sql_edge.valid_from = edge.valid_from
                    sql_edge.valid_to = edge.valid_to
                    session.add(sql_edge)

    async def find_similar_entities(
        self, tenant_id: TenantId, name: str, threshold: float = 0.85
    ) -> list[RawEntity]:
        """Finds entities similar to the given surface name via ILIKE match.

        Note: `threshold` is reserved for future fuzzy/vector similarity matching (Stage 3).
        Currently surface name matching performs an exact substring ILIKE search with
        escaped wildcards.
        """
        escaped_name = _escape_like(name.strip())
        async with self._tenant_session(tenant_id) as session:
            result = await session.execute(
                select(SQLRawEntity)
                .where(
                    SQLRawEntity.tenant_id == tenant_id.value,
                    SQLRawEntity.name.ilike(f"%{escaped_name}%", escape="\\"),
                )
                .order_by(SQLRawEntity.name)
            )
            rows = result.scalars().all()
            mapped = [_map_sql_entity_to_domain(r) for r in rows]
            return [e for e in mapped if isinstance(e, RawEntity)]  # type: ignore[return-value]


class PostgresSubgraphReader:
    """Outbound adapter implementing SubgraphReaderPort.

    Performs seed entity matching and depth-bounded recursive CTE graph traversal.
    Tenant-scoped through _tenant_session / SET LOCAL.
    """

    def __init__(self, session_factory: Callable[[], AsyncSession]) -> None:
        self._session_factory = session_factory

    @asynccontextmanager
    async def _tenant_session(self, tenant_id: TenantId) -> AsyncIterator[AsyncSession]:
        session = self._session_factory()
        if session.in_transaction():
            bind = session.bind or session.get_bind()
            if bind.dialect.name == "postgresql":
                await session.execute(
                    text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"),
                    {"tenant_id": str(tenant_id.value)},
                )
            yield session
        else:
            async with session, session.begin():
                bind = session.bind or session.get_bind()
                if bind.dialect.name == "postgresql":
                    await session.execute(
                        text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"),
                        {"tenant_id": str(tenant_id.value)},
                    )
                yield session

    async def search_subgraph(
        self, tenant_id: TenantId, query: str, depth: int = 2
    ) -> list[RawEntity | GoldenRecord | Edge]:
        """Retrieves an ego-graph or connected subgraph around query entities.

        Matches seed entities by name (ILIKE), then expands depth hops over the edges
        table via a depth-bounded recursive CTE.
        """
        if not query or not query.strip():
            return []

        safe_depth = max(0, depth)
        escaped_query = _escape_like(query.strip())
        query_pattern = f"%{escaped_query}%"

        async with self._tenant_session(tenant_id) as session:
            # 1. Match seed entities
            seed_result = await session.execute(
                select(SQLRawEntity).where(
                    SQLRawEntity.tenant_id == tenant_id.value,
                    SQLRawEntity.name.ilike(query_pattern, escape="\\"),
                )
            )
            seed_entities = seed_result.scalars().all()
            if not seed_entities:
                return []

            seed_ids: list[UUID] = [e.id for e in seed_entities]

            # If depth == 0, return only seed entities
            if safe_depth == 0:
                return [_map_sql_entity_to_domain(e) for e in seed_entities]

            # 2. Depth-bounded recursive CTE traversal over edges
            cte_sql = text("""
                WITH RECURSIVE traversed_edges AS (
                    -- Level 1: edges directly connected to seed entities
                    SELECT
                        e.id,
                        e.tenant_id,
                        e.source_entity_id,
                        e.target_entity_id,
                        e.edge_type,
                        e.weight,
                        e.valid_from,
                        e.valid_to,
                        e.chunk_id,
                        e.start_offset,
                        e.end_offset,
                        e.quote,
                        1 AS current_depth,
                        ARRAY[e.id] AS path
                    FROM edges e
                    WHERE e.tenant_id = :tenant_id
                      AND (e.source_entity_id = ANY(:seed_ids)
                           OR e.target_entity_id = ANY(:seed_ids))

                    UNION

                    -- Recursive step: expand outward to adjacent edges up to :depth
                    SELECT
                        e.id,
                        e.tenant_id,
                        e.source_entity_id,
                        e.target_entity_id,
                        e.edge_type,
                        e.weight,
                        e.valid_from,
                        e.valid_to,
                        e.chunk_id,
                        e.start_offset,
                        e.end_offset,
                        e.quote,
                        te.current_depth + 1 AS current_depth,
                        te.path || e.id AS path
                    FROM edges e
                    JOIN traversed_edges te
                      ON (e.source_entity_id = te.target_entity_id
                          OR e.source_entity_id = te.source_entity_id
                          OR e.target_entity_id = te.target_entity_id
                          OR e.target_entity_id = te.source_entity_id)
                    WHERE te.current_depth < :depth
                      AND e.tenant_id = :tenant_id
                      AND NOT (e.id = ANY(te.path))
                )
                SELECT DISTINCT
                    id,
                    tenant_id,
                    source_entity_id,
                    target_entity_id,
                    edge_type,
                    weight,
                    valid_from,
                    valid_to,
                    chunk_id,
                    start_offset,
                    end_offset,
                    quote
                FROM traversed_edges;
            """)

            edges_res = await session.execute(
                cte_sql,
                {
                    "tenant_id": tenant_id.value,
                    "seed_ids": seed_ids,
                    "depth": safe_depth,
                },
            )
            edge_rows = edges_res.fetchall()

            # Collect reached entity IDs
            reached_entity_ids = set(seed_ids)
            domain_edges: list[Edge] = []
            for er in edge_rows:
                reached_entity_ids.add(er.source_entity_id)
                reached_entity_ids.add(er.target_entity_id)
                domain_edges.append(
                    Edge(
                        id=er.id,
                        tenant_id=TenantId(value=er.tenant_id),
                        source_entity_id=EntityId(value=er.source_entity_id),
                        target_entity_id=EntityId(value=er.target_entity_id),
                        edge_type=er.edge_type,
                        weight=float(er.weight),
                        valid_from=er.valid_from,
                        valid_to=er.valid_to,
                        spans=[
                            EvidenceSpan(
                                chunk_id=ChunkId(value=er.chunk_id),
                                start_offset=er.start_offset,
                                end_offset=er.end_offset,
                                quote=er.quote,
                            )
                        ],
                    )
                )

            # Fetch all reached entity rows from DB
            entities_res = await session.execute(
                select(SQLRawEntity).where(
                    SQLRawEntity.tenant_id == tenant_id.value,
                    SQLRawEntity.id.in_(reached_entity_ids),
                )
            )
            all_entity_rows = entities_res.scalars().all()
            domain_entities = [_map_sql_entity_to_domain(e) for e in all_entity_rows]

            return list(domain_entities) + list(domain_edges)


class PostgresGraphRepository(PostgresEntityStore, PostgresSubgraphReader):
    """Deep module combining entity persistence and subgraph reading."""

    def __init__(self, session_factory: Callable[[], AsyncSession]) -> None:
        super().__init__(session_factory=session_factory)
