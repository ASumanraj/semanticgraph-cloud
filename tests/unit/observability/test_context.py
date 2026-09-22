"""Tests for tenant context and worker header propagation (T-209).

Acceptance criteria verified:
- Tenant context is managed reliably across async and sync scopes.
- Tenant context crosses the worker boundary explicitly via headers.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from semanticgraph.domain.models.entities import TenantId
from semanticgraph.observability.context import (
    TENANT_ID_HEADER,
    extract_tenant_context,
    get_current_tenant_id,
    inject_tenant_context,
    reset_tenant_context,
    set_current_tenant_id,
    with_tenant,
)


def test_tenant_context_set_and_get():
    """Setting tenant context makes it available via get_current_tenant_id."""
    assert get_current_tenant_id() is None

    tenant_id = TenantId(uuid4())
    token = set_current_tenant_id(tenant_id)
    try:
        assert get_current_tenant_id() == tenant_id
    finally:
        reset_tenant_context(token)

    assert get_current_tenant_id() is None


def test_with_tenant_context_manager():
    """with_tenant context manager scopes tenant context cleanly."""
    tenant_a = TenantId(uuid4())
    tenant_b = TenantId(uuid4())

    assert get_current_tenant_id() is None

    with with_tenant(tenant_a):
        assert get_current_tenant_id() == tenant_a

        with with_tenant(tenant_b):
            assert get_current_tenant_id() == tenant_b

        assert get_current_tenant_id() == tenant_a

    assert get_current_tenant_id() is None


@pytest.mark.asyncio
async def test_async_tenant_context_propagation():
    """Tenant context propagates across async coroutines."""
    tenant_id = TenantId(uuid4())

    async def inner_task() -> TenantId | None:
        return get_current_tenant_id()

    with with_tenant(tenant_id):
        result = await inner_task()
        assert result == tenant_id

    assert get_current_tenant_id() is None


def test_worker_boundary_header_injection_and_extraction():
    """Tenant context crosses the worker boundary explicitly via headers."""
    tenant_id = TenantId(uuid4())

    # 1. Injection from explicit argument
    headers: dict[str, str] = {}
    inject_tenant_context(headers, tenant_id=tenant_id)
    assert headers[TENANT_ID_HEADER] == str(tenant_id.value)

    # 2. Extraction from headers
    extracted = extract_tenant_context(headers)
    assert extracted == tenant_id

    # 3. Injection from active context when tenant_id is omitted
    headers_auto: dict[str, str] = {}
    with with_tenant(tenant_id):
        inject_tenant_context(headers_auto)
    assert headers_auto[TENANT_ID_HEADER] == str(tenant_id.value)

    # 4. Missing or invalid header extraction returns None
    assert extract_tenant_context({}) is None
    assert extract_tenant_context({"other_header": "value"}) is None
    assert extract_tenant_context({TENANT_ID_HEADER: "invalid-uuid"}) is None
