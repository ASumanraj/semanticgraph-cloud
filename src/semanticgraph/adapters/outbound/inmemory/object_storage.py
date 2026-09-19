"""In-memory ObjectStoragePort implementation."""

from __future__ import annotations

from semanticgraph.domain.models.entities import TenantId


class InMemoryObjectStorage:
    """Satisfies ObjectStoragePort, mirroring the tenant-prefixed key layout the
    real adapter must use."""

    def __init__(self, base_url: str = "https://storage.invalid") -> None:
        self._base_url = base_url
        self.issued: list[tuple[TenantId, str]] = []

    async def generate_upload_url(self, tenant_id: TenantId, filename: str) -> str:
        self.issued.append((tenant_id, filename))
        return f"{self._base_url}/{tenant_id.value}/{filename}"
