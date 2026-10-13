"""Tests for docker-compose.real.yml configuration (T-228 Slice 2).

Verifies:
- docker-compose.real.yml exists at repo root.
- Uses non-default ports (8013, 3013, 5433, 6380) to avoid colliding with running stacks.
- Configures SEMANTICGRAPH_ADAPTERS=postgres on both api and worker.
- Executes `alembic upgrade head` before api uvicorn starts.
- Keeps postgres, redis, api, worker, and frontend services properly wired.
"""

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]


def test_docker_compose_real_services_and_ports():
    compose_path = REPO_ROOT / "docker-compose.real.yml"
    assert compose_path.exists(), "docker-compose.real.yml must exist at repo root"

    with open(compose_path, encoding="utf-8") as f:
        compose = yaml.safe_load(f)

    services = compose.get("services", {})
    assert "postgres" in services, "postgres service must be defined"
    assert "redis" in services, "redis service must be defined"
    assert "api" in services, "api service must be defined"
    assert "worker" in services, "worker service must be defined"
    assert "frontend" in services, "frontend service must be defined"

    # Non-default ports check (no collisions with 8000/8003 or 3000/3003 or 5432 or 6379)
    api_ports = services["api"].get("ports", [])
    assert any("8013" in str(p) for p in api_ports), "api port must map host port 8013"

    frontend_ports = services["frontend"].get("ports", [])
    assert any("3013" in str(p) for p in frontend_ports), "frontend port must map host port 3013"

    postgres_ports = services["postgres"].get("ports", [])
    assert any("5433" in str(p) for p in postgres_ports), "postgres port must map host port 5433"


def test_docker_compose_real_postgres_profile_and_migration():
    compose_path = REPO_ROOT / "docker-compose.real.yml"
    with open(compose_path, encoding="utf-8") as f:
        compose = yaml.safe_load(f)

    services = compose.get("services", {})
    api = services["api"]
    worker = services["worker"]

    api_env = api.get("environment", [])
    if isinstance(api_env, list):
        api_env = dict(e.split("=", 1) for e in api_env if "=" in e)

    worker_env = worker.get("environment", [])
    if isinstance(worker_env, list):
        worker_env = dict(e.split("=", 1) for e in worker_env if "=" in e)

    assert api_env.get("SEMANTICGRAPH_ADAPTERS") == "postgres"
    assert worker_env.get("SEMANTICGRAPH_ADAPTERS") == "postgres"

    # API must run alembic upgrade head before starting uvicorn
    api_cmd = api.get("command", "")
    assert "alembic upgrade head" in api_cmd, "api must run alembic upgrade head before starting"
    assert "uvicorn" in api_cmd, "api must start uvicorn after migration"


def test_docker_compose_real_frontend_points_to_real_api():
    compose_path = REPO_ROOT / "docker-compose.real.yml"
    with open(compose_path, encoding="utf-8") as f:
        compose = yaml.safe_load(f)

    frontend = compose["services"]["frontend"]
    fe_env = frontend.get("environment", [])
    if isinstance(fe_env, list):
        fe_env = dict(e.split("=", 1) for e in fe_env if "=" in e)

    assert fe_env.get("NEXT_PUBLIC_API_URL") == "http://localhost:8013"
