import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, select
import uuid

from src.api.main import app
from src.models.sql import Tenant, Entity

# In-memory database for testing
sqlite_url = "sqlite://"
engine = create_engine(sqlite_url, connect_args={"check_same_thread": False})

def get_session_override():
    with Session(engine) as session:
        yield session

@pytest.fixture(name="client")
def client_fixture():
    SQLModel.metadata.create_all(engine)
    
    # Create test data
    with Session(engine) as session:
        tenant_a_id = uuid.uuid4()
        tenant_b_id = uuid.uuid4()
        
        tenant_a = Tenant(id=tenant_a_id, name="Tenant A")
        tenant_b = Tenant(id=tenant_b_id, name="Tenant B")
        
        session.add(tenant_a)
        session.add(tenant_b)
        
        # Add some entities
        entity_a = Entity(id=uuid.uuid4(), name="Entity A", tenant_id=tenant_a_id)
        entity_b = Entity(id=uuid.uuid4(), name="Entity B", tenant_id=tenant_b_id)
        
        session.add(entity_a)
        session.add(entity_b)
        session.commit()

    # Override dependencies
    from src.api.dependencies import get_db_session
    app.dependency_overrides[get_db_session] = get_session_override
    
    yield TestClient(app)
    
    app.dependency_overrides.clear()
    SQLModel.metadata.drop_all(engine)

def test_tenant_isolation_enforced(client: TestClient):
    # Try without tenant header -> 422 Unprocessable Entity (Missing header)
    response = client.get("/api/v1/entities")
    assert response.status_code == 422
    
    # Try with Tenant A header -> should return only Entity A
    with Session(engine) as session:
        tenant_a = session.exec(select(Tenant).where(Tenant.name == "Tenant A")).first()
    
    response_a = client.get("/api/v1/entities", headers={"X-Tenant-ID": str(tenant_a.id)})
    assert response_a.status_code == 200
    data_a = response_a.json()
    assert len(data_a) == 1
    assert data_a[0]["name"] == "Entity A"
