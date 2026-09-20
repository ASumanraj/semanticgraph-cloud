"""
Tests for Docker Compose and container configuration.

Per ENTERPRISE_PLAN.md Stage 1:
- docker-compose.yml must run the real API and worker (no sleep mock)
- api.Dockerfile must install from pyproject.toml (not deleted requirements.txt)
- api and worker services must configure SEMANTICGRAPH_ADAPTERS and service dependencies
"""

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_compose_services_run_real_commands():
    compose_path = REPO_ROOT / "docker-compose.yml"
    assert compose_path.exists(), "docker-compose.yml must exist at repo root"

    with open(compose_path, encoding="utf-8") as f:
        compose = yaml.safe_load(f)

    services = compose.get("services", {})
    assert "api" in services, "api service must be defined in compose"
    assert "worker" in services, "worker service must be defined in compose"

    api_cmd = services["api"].get("command", "")
    assert "sleep" not in api_cmd, "api command must not be a sleep mock"
    assert "uvicorn" in api_cmd, "api command must invoke uvicorn"
    assert "semanticgraph.adapters.inbound.api.app:app" in api_cmd

    worker_cmd = services["worker"].get("command", "")
    assert "sleep" not in worker_cmd, "worker command must not be a sleep mock"
    assert "celery" in worker_cmd, "worker command must invoke celery"
    assert "semanticgraph.adapters.inbound.workers.celery_app" in worker_cmd


def test_compose_wires_environment_and_dependencies():
    compose_path = REPO_ROOT / "docker-compose.yml"
    with open(compose_path, encoding="utf-8") as f:
        compose = yaml.safe_load(f)

    services = compose.get("services", {})
    api = services["api"]
    worker = services["worker"]

    api_env = api.get("environment", [])
    worker_env = worker.get("environment", [])

    # If environment is a list or dict, convert to dict for assertion
    if isinstance(api_env, list):
        api_env = dict(e.split("=", 1) for e in api_env if "=" in e)
    if isinstance(worker_env, list):
        worker_env = dict(e.split("=", 1) for e in worker_env if "=" in e)

    assert "SEMANTICGRAPH_ADAPTERS" in api_env
    assert "SEMANTICGRAPH_ADAPTERS" in worker_env
    assert "REDIS_URL" in worker_env

    # Dependencies
    api_deps = api.get("depends_on", {})
    worker_deps = worker.get("depends_on", {})
    assert "postgres" in api_deps
    assert "redis" in api_deps
    assert "redis" in worker_deps


def test_api_dockerfile_uses_pyproject_toml():
    dockerfile_path = REPO_ROOT / "api.Dockerfile"
    assert dockerfile_path.exists(), "api.Dockerfile must exist"

    content = dockerfile_path.read_text(encoding="utf-8")
    assert "requirements.txt" not in content, (
        "requirements.txt was replaced by pyproject.toml in Stage 0; "
        "api.Dockerfile must not reference requirements.txt"
    )
    assert "pyproject.toml" in content, "api.Dockerfile must copy pyproject.toml"
    assert "pip install" in content
