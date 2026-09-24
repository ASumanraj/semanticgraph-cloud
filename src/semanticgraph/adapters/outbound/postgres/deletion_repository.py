"""PostgreSQL Assertion-Counted Deletion Repository (T-206).

Upholds:
- Irreversible Rule 4: Facts die by assertion count. Deleting a document removes its assertions;
  a fact survives while any other document still asserts it.
- Single-transaction cascade across:
  chunks -> assertions -> evidence_spans -> facts -> mentions -> memberships ->
  golden_records -> embeddings -> caches -> community_summaries -> eval_fixtures.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import delete, func, text, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from semanticgraph.adapters.outbound.postgres.models import (
    SQLAssertion,
    SQLChunkEmbedding,
    SQLClusterMembership,
    SQLCommunitySummary,
    SQLDocument,
    SQLEdge,
    SQLEvalFixture,
    SQLEvidenceSpan,
    SQLExtractionRun,
    SQLFact,
    SQLGoldenRecord,
    SQLMention,
    SQLQueryCache,
    SQLRawEntity,
    SQLSemanticChunk,
)
from semanticgraph.application.use_cases.delete_document import (
    DeletionRepositoryPort,
    DeletionResult,
)
from semanticgraph.domain.models.entities import TenantId


class PostgresDeletionRepository(DeletionRepositoryPort):
    """PostgreSQL adapter executing transactional assertion-counted deletion cascade."""

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

    async def delete_document_cascade(
        self, tenant_id: TenantId, document_id: UUID
    ) -> DeletionResult:
        """Executes full cascade erasure of document and dependent records in one transaction."""
        async with self._tenant_session(tenant_id) as session:
            # 1. Verify document exists for tenant
            doc_stmt = select(SQLDocument).where(
                SQLDocument.tenant_id == tenant_id.value,
                SQLDocument.id == document_id,
            )
            doc_res = await session.execute(doc_stmt)
            doc = doc_res.scalar_one_or_none()
            if doc is None:
                return DeletionResult(document_id=document_id)

            # 2. Collect chunks belonging to document
            chunk_stmt = select(SQLSemanticChunk.id).where(
                SQLSemanticChunk.tenant_id == tenant_id.value,
                SQLSemanticChunk.document_id == document_id,
            )
            chunk_ids = list((await session.execute(chunk_stmt)).scalars().all())

            # 3. Collect assertions referencing document or chunks
            assert_cond = SQLAssertion.document_id == document_id
            if chunk_ids:
                assert_cond = assert_cond | SQLAssertion.chunk_id.in_(chunk_ids)

            assert_stmt = select(SQLAssertion.id, SQLAssertion.fact_id).where(
                SQLAssertion.tenant_id == tenant_id.value,
                assert_cond,
            )
            assert_rows = (await session.execute(assert_stmt)).all()
            assertion_ids = [r[0] for r in assert_rows]
            affected_fact_ids = list({r[1] for r in assert_rows if r[1] is not None})

            # 4. Collect mentions and affected clusters
            mention_cond = SQLMention.document_id == document_id
            if chunk_ids:
                mention_cond = mention_cond | SQLMention.chunk_id.in_(chunk_ids)

            mention_stmt = select(SQLMention.id).where(
                SQLMention.tenant_id == tenant_id.value,
                mention_cond,
            )
            mention_ids = list((await session.execute(mention_stmt)).scalars().all())

            affected_cluster_ids: list[UUID] = []
            if mention_ids:
                mem_stmt = select(SQLClusterMembership.cluster_id).where(
                    SQLClusterMembership.tenant_id == tenant_id.value,
                    SQLClusterMembership.mention_id.in_(mention_ids),
                    SQLClusterMembership.is_active == True,  # noqa: E712
                )
                affected_cluster_ids = list(set((await session.execute(mem_stmt)).scalars().all()))

            # 5. Purge embeddings, caches, community summaries, eval fixtures
            emb_del = delete(SQLChunkEmbedding).where(
                SQLChunkEmbedding.tenant_id == tenant_id.value,
                SQLChunkEmbedding.document_id == document_id,
            )
            emb_res = await session.execute(emb_del)
            purged_embeddings_count = emb_res.rowcount or 0

            cache_del = delete(SQLQueryCache).where(
                SQLQueryCache.tenant_id == tenant_id.value,
                SQLQueryCache.document_id == document_id,
            )
            cache_res = await session.execute(cache_del)
            purged_caches_count = cache_res.rowcount or 0

            comm_del = delete(SQLCommunitySummary).where(
                SQLCommunitySummary.tenant_id == tenant_id.value,
                SQLCommunitySummary.document_id == document_id,
            )
            comm_res = await session.execute(comm_del)
            purged_summaries_count = comm_res.rowcount or 0

            eval_del = delete(SQLEvalFixture).where(
                SQLEvalFixture.tenant_id == tenant_id.value,
                SQLEvalFixture.document_id == document_id,
            )
            eval_res = await session.execute(eval_del)
            purged_eval_fixtures_count = eval_res.rowcount or 0

            # 6. Delete evidence spans
            span_cond = None
            if assertion_ids and chunk_ids:
                span_cond = SQLEvidenceSpan.assertion_id.in_(
                    assertion_ids
                ) | SQLEvidenceSpan.chunk_id.in_(chunk_ids)
            elif assertion_ids:
                span_cond = SQLEvidenceSpan.assertion_id.in_(assertion_ids)
            elif chunk_ids:
                span_cond = SQLEvidenceSpan.chunk_id.in_(chunk_ids)

            if span_cond is not None:
                span_del = delete(SQLEvidenceSpan).where(
                    SQLEvidenceSpan.tenant_id == tenant_id.value,
                    span_cond,
                )
                await session.execute(span_del)

            # 7. Delete assertions
            deleted_assertions_count = 0
            if assertion_ids:
                assert_del = delete(SQLAssertion).where(
                    SQLAssertion.tenant_id == tenant_id.value,
                    SQLAssertion.id.in_(assertion_ids),
                )
                assert_res = await session.execute(assert_del)
                deleted_assertions_count = assert_res.rowcount or 0

            # 8. Delete memberships and mentions
            deleted_mentions_count = 0
            if mention_ids:
                mem_del = delete(SQLClusterMembership).where(
                    SQLClusterMembership.tenant_id == tenant_id.value,
                    SQLClusterMembership.mention_id.in_(mention_ids),
                )
                await session.execute(mem_del)

                mention_del = delete(SQLMention).where(
                    SQLMention.tenant_id == tenant_id.value,
                    SQLMention.id.in_(mention_ids),
                )
                mention_res = await session.execute(mention_del)
                deleted_mentions_count = mention_res.rowcount or 0

            # 8.5 Delete entities and edges belonging to document's chunks
            deleted_entities_count = 0
            deleted_edges_count = 0
            if chunk_ids:
                # Collect entities belonging to this document's chunks
                ent_stmt = select(SQLRawEntity.id).where(
                    SQLRawEntity.tenant_id == tenant_id.value,
                    SQLRawEntity.chunk_id.in_(chunk_ids),
                )
                doc_entity_ids = list((await session.execute(ent_stmt)).scalars().all())

                # Delete edges from this document's chunks or referencing deleted entities
                edge_cond = SQLEdge.chunk_id.in_(chunk_ids)
                if doc_entity_ids:
                    edge_cond = (
                        edge_cond
                        | SQLEdge.source_entity_id.in_(doc_entity_ids)
                        | SQLEdge.target_entity_id.in_(doc_entity_ids)
                    )

                edge_del = delete(SQLEdge).where(
                    SQLEdge.tenant_id == tenant_id.value,
                    edge_cond,
                )
                edge_res = await session.execute(edge_del)
                deleted_edges_count = edge_res.rowcount or 0

                # Delete entities belonging to this document's chunks
                ent_del = delete(SQLRawEntity).where(
                    SQLRawEntity.tenant_id == tenant_id.value,
                    SQLRawEntity.chunk_id.in_(chunk_ids),
                )
                ent_res = await session.execute(ent_del)
                deleted_entities_count = ent_res.rowcount or 0

            # 9. Delete chunks
            deleted_chunks_count = 0
            if chunk_ids:
                chunk_del = delete(SQLSemanticChunk).where(
                    SQLSemanticChunk.tenant_id == tenant_id.value,
                    SQLSemanticChunk.id.in_(chunk_ids),
                )
                chunk_res = await session.execute(chunk_del)
                deleted_chunks_count = chunk_res.rowcount or 0

            # 9.5 Dissociate extraction runs from deleting document
            await session.execute(
                update(SQLExtractionRun)
                .where(
                    SQLExtractionRun.tenant_id == tenant_id.value,
                    SQLExtractionRun.document_id == document_id,
                )
                .values(document_id=None)
            )

            # 10. Delete document
            await session.delete(doc)

            # 11. Garbage-collect facts: Irreversible Rule 4 (Facts die by assertion count)
            deleted_facts_count = 0
            retained_facts_count = 0
            for fact_id in affected_fact_ids:
                cnt_stmt = select(func.count(SQLAssertion.id)).where(
                    SQLAssertion.tenant_id == tenant_id.value,
                    SQLAssertion.fact_id == fact_id,
                )
                cnt_res = await session.execute(cnt_stmt)
                remaining_assertions = cnt_res.scalar() or 0
                if remaining_assertions == 0:
                    fact_del = delete(SQLFact).where(
                        SQLFact.tenant_id == tenant_id.value,
                        SQLFact.id == fact_id,
                    )
                    await session.execute(fact_del)
                    deleted_facts_count += 1
                else:
                    retained_facts_count += 1

            # 12. Re-materialize or purge affected Golden Records
            deleted_golden_records_count = 0
            rematerialized_golden_records_count = 0
            for cluster_id in affected_cluster_ids:
                rem_mems_stmt = select(SQLClusterMembership.mention_id).where(
                    SQLClusterMembership.tenant_id == tenant_id.value,
                    SQLClusterMembership.cluster_id == cluster_id,
                    SQLClusterMembership.is_active == True,  # noqa: E712
                )
                rem_mention_ids = list((await session.execute(rem_mems_stmt)).scalars().all())
                if not rem_mention_ids:
                    gr_del = delete(SQLGoldenRecord).where(
                        SQLGoldenRecord.tenant_id == tenant_id.value,
                        SQLGoldenRecord.id == cluster_id,
                    )
                    await session.execute(gr_del)
                    deleted_golden_records_count += 1
                else:
                    m_stmt = select(SQLMention).where(
                        SQLMention.tenant_id == tenant_id.value,
                        SQLMention.id.in_(rem_mention_ids),
                    )
                    m_rows = list((await session.execute(m_stmt)).scalars().all())
                    if m_rows:
                        canonical_name = max(m_rows, key=lambda m: len(m.name)).name
                        gr_stmt = select(SQLGoldenRecord).where(
                            SQLGoldenRecord.tenant_id == tenant_id.value,
                            SQLGoldenRecord.id == cluster_id,
                        )
                        gr = (await session.execute(gr_stmt)).scalar_one_or_none()
                        if gr:
                            gr.canonical_name = canonical_name
                            gr.updated_at = datetime.now(UTC)
                            session.add(gr)
                            rematerialized_golden_records_count += 1

            await session.flush()

            return DeletionResult(
                document_id=document_id,
                deleted_chunks_count=deleted_chunks_count,
                deleted_assertions_count=deleted_assertions_count,
                deleted_facts_count=deleted_facts_count,
                retained_facts_count=retained_facts_count,
                deleted_mentions_count=deleted_mentions_count,
                purged_embeddings_count=purged_embeddings_count,
                purged_caches_count=purged_caches_count,
                purged_summaries_count=purged_summaries_count,
                purged_eval_fixtures_count=purged_eval_fixtures_count,
                rematerialized_golden_records_count=rematerialized_golden_records_count,
                deleted_golden_records_count=deleted_golden_records_count,
                deleted_entities_count=deleted_entities_count,
                deleted_edges_count=deleted_edges_count,
            )
