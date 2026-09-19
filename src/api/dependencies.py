from typing import Annotated, Generator
from fastapi import Header, Depends, HTTPException, status
from sqlmodel import Session, create_engine, select
from uuid import UUID

from src.models.sql import Tenant

# Replace with actual config later
DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

def get_db_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session

SessionDep = Annotated[Session, Depends(get_db_session)]

def get_current_tenant(
    x_tenant_id: Annotated[UUID, Header(description="Strict Multi-tenant isolation boundary")],
    session: SessionDep
) -> Tenant:
    tenant = session.exec(select(Tenant).where(Tenant.id == x_tenant_id)).first()
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found"
        )
    return tenant

CurrentTenantDep = Annotated[Tenant, Depends(get_current_tenant)]
