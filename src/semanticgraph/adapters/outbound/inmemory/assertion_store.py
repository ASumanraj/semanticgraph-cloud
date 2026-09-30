"""In-memory AssertionStore implementation."""

from __future__ import annotations

from uuid import UUID

from semanticgraph.domain.models.entities import TenantId
from semanticgraph.domain.provenance.models import Assertion, Fact


class InMemoryAssertionStore:
    """Satisfies AssertionStore port. Facts and assertions are tenant-isolated in memory."""

    def __init__(self) -> None:
        # tenant_id -> {fact_id: Fact}
        self._facts: dict[UUID, dict[UUID, Fact]] = {}

    @staticmethod
    def _assertions_match(x: Assertion, y: Assertion) -> bool:
        if x.id == y.id:
            return True
        x_doc = x.document_id.value if hasattr(x.document_id, "value") else x.document_id
        y_doc = y.document_id.value if hasattr(y.document_id, "value") else y.document_id
        x_chunk = (
            x.chunk_id.value
            if hasattr(x.chunk_id, "value")
            else (
                x.chunk_id
                or (
                    x.spans[0].chunk_id.value
                    if (x.spans and hasattr(x.spans[0].chunk_id, "value"))
                    else (x.spans[0].chunk_id if x.spans else None)
                )
            )
        )
        y_chunk = (
            y.chunk_id.value
            if hasattr(y.chunk_id, "value")
            else (
                y.chunk_id
                or (
                    y.spans[0].chunk_id.value
                    if (y.spans and hasattr(y.spans[0].chunk_id, "value"))
                    else (y.spans[0].chunk_id if y.spans else None)
                )
            )
        )
        if x_doc is not None and y_doc is not None and x_doc != y_doc:
            return False
        if x_chunk is not None and y_chunk is not None and x_chunk != y_chunk:
            return False
        x_spans = sorted((s.start_offset, s.end_offset, s.quote) for s in x.spans)
        y_spans = sorted((s.start_offset, s.end_offset, s.quote) for s in y.spans)
        return x_spans == y_spans

    async def save_fact(self, tenant_id: TenantId, fact: Fact) -> None:
        """Persists a Fact together with its mandatory Assertions and EvidenceSpans."""
        if not fact.assertions:
            raise ValueError("Cannot persist a Fact without at least one supporting Assertion")
        for a in fact.assertions:
            if not a.spans:
                raise ValueError("Assertion must hold at least one EvidenceSpan")

        tenant_facts = self._facts.setdefault(tenant_id.value, {})
        existing = tenant_facts.get(fact.id)
        if existing is not None:
            existing.claim = fact.claim
            for a in fact.assertions:
                if not any(self._assertions_match(x, a) for x in existing.assertions):
                    existing.assertions.append(a)
        else:
            unique_assertions: list[Assertion] = []
            for a in fact.assertions:
                if not any(self._assertions_match(x, a) for x in unique_assertions):
                    unique_assertions.append(a)
            fact.assertions = unique_assertions
            tenant_facts[fact.id] = fact

    async def get_fact(self, tenant_id: TenantId, fact_id: UUID) -> Fact | None:
        """Retrieves a Fact with all its Assertions and EvidenceSpans."""
        tenant_facts = self._facts.get(tenant_id.value, {})
        return tenant_facts.get(fact_id)

    async def get_live_facts(self, tenant_id: TenantId) -> list[Fact]:
        """Returns all facts that currently have at least one active assertion."""
        tenant_facts = self._facts.get(tenant_id.value, {})
        return [f for f in tenant_facts.values() if f.is_alive]

    async def delete_assertion(self, tenant_id: TenantId, assertion_id: UUID) -> None:
        """Deletes an assertion and its evidence spans across facts in this tenant."""
        tenant_facts = self._facts.get(tenant_id.value, {})
        for fact in tenant_facts.values():
            surviving = [a for a in fact.assertions if a.id != assertion_id]
            if len(surviving) != len(fact.assertions):
                fact.assertions = surviving


# Alias
InMemoryProvenanceRepository = InMemoryAssertionStore
