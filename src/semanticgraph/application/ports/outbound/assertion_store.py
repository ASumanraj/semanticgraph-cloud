"""
Outbound Port: Assertion Store.

Defines the interface for storing and retrieving facts, assertions, and evidence spans.
Hides relational persistence, span tracking, and assertion counting.
Adapters in adapters/outbound/postgres/ and adapters/outbound/inmemory/ implement this.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable
from uuid import UUID

from semanticgraph.domain.models.entities import TenantId
from semanticgraph.domain.provenance.models import Fact


@runtime_checkable
class AssertionStore(Protocol):
    """Deep interface: persists facts with mandatory assertions and evidence spans."""

    async def save_fact(self, tenant_id: TenantId, fact: Fact) -> None:
        """Persists a Fact together with its mandatory Assertions and EvidenceSpans."""
        ...

    async def get_fact(self, tenant_id: TenantId, fact_id: UUID) -> Fact | None:
        """Retrieves a Fact with all its Assertions and EvidenceSpans."""
        ...

    async def get_live_facts(self, tenant_id: TenantId) -> list[Fact]:
        """Returns all facts that currently have at least one active assertion."""
        ...

    async def delete_assertion(self, tenant_id: TenantId, assertion_id: UUID) -> None:
        """Deletes an assertion and its evidence spans, affecting the fact's assertion count."""
        ...


# Alias for consistency with port naming
AssertionStorePort = AssertionStore
