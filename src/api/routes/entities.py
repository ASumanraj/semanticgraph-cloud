from typing import List
from fastapi import APIRouter
from sqlmodel import select
from src.api.dependencies import CurrentTenantDep, SessionDep
from src.models.sql import Entity

router = APIRouter(
    prefix="/api/v1/entities",
    tags=["Entities"],
    # Apply at router level
)

@router.get("/")
def get_entities(tenant: CurrentTenantDep, session: SessionDep) -> List[Entity]:
    return session.exec(select(Entity).where(Entity.tenant_id == tenant.id)).all()
