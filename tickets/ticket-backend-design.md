## Question

How should the FastAPI backend be correctly and standardly architected to ensure multi-tenant isolation, leveraging the `fastapi` skill (Annotated DI, SQLModel, strict Pydantic V2)? What is the exact directory structure and dependency injection pattern we will use to lock down `tenant_id`?

**Labels**: `wayfinder:research`, `closed`

### Resolution

Based on the official `fastapi` skill guidelines and repository constraints (`AGENTS.md`), here is the standardized Phase 1 backend architecture:

#### 1. Dependency Injection Pattern
We will enforce multi-tenant isolation utilizing `Annotated` dependencies, applied directly at the APIRouter level (or per-endpoint) to ensure strict `tenant_id` filtering. 

```python
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

def get_current_user() -> User:
    # Logic to extract user from token
    pass

CurrentUserDep = Annotated[User, Depends(get_current_user)]

def get_current_tenant(current_user: CurrentUserDep) -> Tenant:
    # Logic to verify and return the tenant context for the user. 
    # Super Admins bypass strict silo filtering if accessing platform metrics.
    pass

CurrentTenantDep = Annotated[Tenant, Depends(get_current_tenant)]

def get_db_session() -> Session:
    # Yield SQLModel session
    pass

SessionDep = Annotated[Session, Depends(get_db_session)]

# Apply tenant dependency at the router level for blanket multi-tenant isolation
router = APIRouter(
    prefix="/entities",
    tags=["entities"],
    dependencies=[Depends(get_current_tenant)]
)

@router.get("/")
def list_entities(tenant: CurrentTenantDep, session: SessionDep) -> list[Entity]:
    # Every DB query explicitly filters by tenant.id
    return session.exec(select(Entity).where(Entity.tenant_id == tenant.id)).all()
```

#### 2. Directory Structure
```text
backend/
├── main.py                # App entrypoint (FastAPI init, global exception handlers)
├── api/
│   ├── dependencies.py    # `Annotated` DI definitions (CurrentUserDep, CurrentTenantDep)
│   └── routers/           # Separated by domain, router-level dependencies applied here
├── core/
│   ├── config.py          # Pydantic BaseSettings
│   └── security.py        # Token validation, auth logic
├── models/                # Strictly SQLModel & Pydantic V2
│   ├── sql.py             # SQLModel table definitions (all with `tenant_id` fields)
│   └── schemas.py         # Pydantic schemas for I/O (no RootModel or ellipsis)
├── services/
│   ├── graph.py           # Core graph operations passing `tenant_id`
│   └── worker.py          # Celery tasks (heavy GraphRAG extraction & Disambiguation)
```

#### 3. Core Architectural Rules
1. **Strict Annotations:** Use `Annotated` for all dependencies, `Path`, `Query`, and `Body`.
2. **Return Types over Custom Responses:** Use native Python return types and standard `FastAPI` serialization over deprecated `ORJSONResponse`.
3. **No Ellipsis/RootModel:** Default required parameters normally; do not use `...` or `RootModel`.
4. **Tenant Isolation:** Enforced natively via router dependencies. All DB operations/SQLModel queries filter via `tenant_id`. Heavy tasks are routed to Celery asynchronously.
