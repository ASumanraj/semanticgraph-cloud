from contextlib import asynccontextmanager
from typing import Annotated, Sequence

from fastapi import Depends, FastAPI, HTTPException, Header
from sqlmodel import Field, Session, SQLModel, create_engine, select

# --- SQLModel Definitions ---
class Tenant(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str

class Ontology(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id")
    name: str
    description: str | None = None

# --- Database Setup ---
sqlite_file_name = "database.db"
sqlite_url = f"sqlite:///{sqlite_file_name}"
connect_args = {"check_same_thread": False}
engine = create_engine(sqlite_url, echo=False, connect_args=connect_args)

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)

@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    yield

# --- FastAPI App ---
app = FastAPI(lifespan=lifespan)

# --- Dependencies ---
def get_session():
    with Session(engine) as session:
        yield session

SessionDep = Annotated[Session, Depends(get_session)]

def get_tenant_id(x_tenant_id: Annotated[int, Header(description="The Tenant ID")]) -> int:
    return x_tenant_id

TenantIdDep = Annotated[int, Depends(get_tenant_id)]

# --- Routes ---
@app.post("/tenants/")
def create_tenant(tenant: Tenant, session: SessionDep) -> Tenant:
    session.add(tenant)
    session.commit()
    session.refresh(tenant)
    return tenant

@app.post("/ontologies/")
def create_ontology(
    ontology: Ontology,
    session: SessionDep,
    tenant_id: TenantIdDep
) -> Ontology:
    if ontology.tenant_id != tenant_id:
        raise HTTPException(status_code=403, detail="Not authorized for this tenant")
    
    session.add(ontology)
    session.commit()
    session.refresh(ontology)
    return ontology

@app.get("/ontologies/")
def list_ontologies(session: SessionDep, tenant_id: TenantIdDep) -> Sequence[Ontology]:
    statement = select(Ontology).where(Ontology.tenant_id == tenant_id)
    results = session.exec(statement).all()
    return results
