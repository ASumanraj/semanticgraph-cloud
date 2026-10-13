"""Inbound Adapter: System Status Route (v1).

Exposes GET /api/v1/system for active profile and extractor inspection (T-228).
Per T-228:
- No tenant header required, no secrets leaked.
- Returns:
  {
    "profile": "inmemory"|"postgres",
    "persistent": bool,
    "extractor": {
      "kind": "placeholder"|"model",
      "model_id": str|null,
      "terms": "evaluation-only"|null
    }
  }
- kind is placeholder exactly when the deterministic gateway is in use.
- model_id is read from the gateway in use, never from a config string.
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field

from semanticgraph.composition.container import ContainerDep

router = APIRouter(prefix="/api/v1", tags=["system"])


class ExtractorStatusResponse(BaseModel):
    kind: Literal["placeholder", "model"] = Field(
        description="Whether the extractor is a deterministic placeholder or a real model"
    )
    model_id: str | None = Field(
        default=None,
        description="Model ID read from the active gateway, or null for placeholder",
    )
    terms: Literal["evaluation-only"] | str | None = Field(
        default=None,
        description="Terms of use if evaluation-only, else null",
    )


class SystemStatusResponse(BaseModel):
    profile: Literal["inmemory", "postgres"] = Field(
        description="Active adapter profile: inmemory or postgres"
    )
    persistent: bool = Field(
        description="Whether persistence is durable (True for postgres, False for inmemory)"
    )
    extractor: ExtractorStatusResponse


@router.get("/system", response_model=SystemStatusResponse)
def get_system_status(container: ContainerDep) -> SystemStatusResponse:
    """Returns the active adapter profile, durability, and extractor description."""
    info = container.describe_system()
    return SystemStatusResponse(**info)
