from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool
import pytest

from backend.main import app, get_session

# Setup in-memory database for testing
sqlite_url = "sqlite://"
engine = create_engine(
    sqlite_url, connect_args={"check_same_thread": False}, poolclass=StaticPool
)

def override_get_session():
    with Session(engine) as session:
        yield session

app.dependency_overrides[get_session] = override_get_session

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_db():
    SQLModel.metadata.create_all(engine)
    yield
    SQLModel.metadata.drop_all(engine)

def test_create_tenant():
    response = client.post("/tenants/", json={"name": "Test Tenant"})
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Test Tenant"
    assert "id" in data

def test_tenant_isolation():
    # Create tenant
    response = client.post("/tenants/", json={"name": "Tenant A"})
    tenant_id = response.json()["id"]

    # Create ontology for tenant
    response = client.post(
        "/ontologies/",
        json={"name": "Ontology A", "tenant_id": tenant_id},
        headers={"x-tenant-id": str(tenant_id)}
    )
    assert response.status_code == 200
    
    # List ontologies for tenant
    response = client.get("/ontologies/", headers={"x-tenant-id": str(tenant_id)})
    assert response.status_code == 200
    assert len(response.json()) == 1

    # Unauthorized access (wrong tenant_id)
    response = client.get("/ontologies/", headers={"x-tenant-id": "999"})
    assert response.status_code == 200
    assert len(response.json()) == 0  # Should be empty or 403. Our implementation returns empty list for wrong tenant_id on get, or 403 on post.

def test_create_ontology_wrong_tenant():
    response = client.post(
        "/ontologies/",
        json={"name": "Ontology B", "tenant_id": 1},
        headers={"x-tenant-id": "2"}
    )
    assert response.status_code == 403
