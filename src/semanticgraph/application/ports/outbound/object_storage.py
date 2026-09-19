"""
Outbound Port: Object Storage.

Abstracts blob storage (S3, GCS, MinIO) behind a presigned-upload interface.

Tenant scoping is part of the interface, not a caller convention: every key is
written under the tenant's prefix, which is what makes per-tenant credential
vending and crypto-shredding possible later (ENTERPRISE_PLAN.md Stage 6).
"""

from __future__ import annotations

from typing import Protocol

from semanticgraph.domain.models.entities import TenantId


class ObjectStoragePort(Protocol):
    """Deep interface: hides bucket layout, key derivation, signing and expiry."""

    async def generate_upload_url(self, tenant_id: TenantId, filename: str) -> str: ...
