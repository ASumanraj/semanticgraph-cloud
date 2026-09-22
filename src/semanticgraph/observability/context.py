"""Tenant Context and Worker Boundary Propagation (T-209).

Manages active tenant context across synchronous and asynchronous call chains,
and propagates tenant attribution across process and broker boundaries (e.g. Celery).
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar, Token
from typing import Any
from uuid import UUID

from semanticgraph.domain.models.entities import TenantId

TENANT_ID_HEADER: str = "x-tenant-id"

_CURRENT_TENANT_ID: ContextVar[TenantId | None] = ContextVar("current_tenant_id", default=None)


def get_current_tenant_id() -> TenantId | None:
    """Returns the active tenant ID in the current execution context, if any."""
    return _CURRENT_TENANT_ID.get()


def set_current_tenant_id(tenant: TenantId | str | UUID | None) -> Token[TenantId | None]:
    """Sets the active tenant ID in the current context and returns a token to reset it."""
    parsed: TenantId | None = None
    if tenant is not None:
        if isinstance(tenant, TenantId):
            parsed = tenant
        elif isinstance(tenant, UUID):
            parsed = TenantId(value=tenant)
        elif isinstance(tenant, str):
            parsed = TenantId(value=UUID(tenant))
        else:
            raise TypeError(f"Expected TenantId, UUID or str, got {type(tenant).__name__}")
    return _CURRENT_TENANT_ID.set(parsed)


def reset_tenant_context(token: Token[TenantId | None]) -> None:
    """Resets the tenant context to its previous state using the provided token."""
    _CURRENT_TENANT_ID.reset(token)


@contextmanager
def with_tenant(tenant: TenantId | str | UUID | None) -> Iterator[TenantId | None]:
    """Context manager setting active tenant for the duration of the block."""
    token = set_current_tenant_id(tenant)
    try:
        yield get_current_tenant_id()
    finally:
        reset_tenant_context(token)


def inject_tenant_context(
    headers: dict[str, Any],
    tenant_id: TenantId | str | UUID | None = None,
) -> dict[str, Any]:
    """Injects tenant ID into a headers dictionary (e.g. Celery or HTTP headers)."""
    effective_tenant = tenant_id if tenant_id is not None else get_current_tenant_id()
    if effective_tenant is not None:
        val = effective_tenant.value if isinstance(effective_tenant, TenantId) else effective_tenant
        headers[TENANT_ID_HEADER] = str(val)
    return headers


def extract_tenant_context(headers: dict[str, Any] | None) -> TenantId | None:
    """Extracts TenantId from headers dictionary, or returns None if absent/invalid."""
    if not headers:
        return None

    # Case-insensitive header lookup
    val = None
    for k, v in headers.items():
        if k.lower() == TENANT_ID_HEADER:
            val = v
            break

    if not val:
        return None

    try:
        return TenantId(value=UUID(str(val)))
    except (ValueError, TypeError, AttributeError):
        return None
