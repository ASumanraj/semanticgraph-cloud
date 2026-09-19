"""
Inbound Adapter: FastAPI Dependencies.

Extracts tenant context from HTTP headers and provides typed DI.
Per fastapi skill: uses Annotated + Depends, no ellipsis, no RootModel.
Per AGENTS.md: every route is scoped to tenant_id.
"""
from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header, HTTPException, status

from semanticgraph.domain.models.entities import TenantId


def get_tenant_id(
    x_tenant_id: Annotated[
        str,
        Header(description="Strict multi-tenant isolation boundary"),
    ],
) -> TenantId:
    """
    Parse and validate the tenant header.
    Per security-review skill: never trust client-supplied IDs without validation.
    """
    try:
        return TenantId(value=UUID(x_tenant_id))
    except (ValueError, AttributeError):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": {"code": "INVALID_TENANT_ID", "message": "X-Tenant-ID must be a valid UUID"}},
        )


CurrentTenantDep = Annotated[TenantId, Depends(get_tenant_id)]
