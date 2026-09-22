"""Shared fixtures for E2E tests."""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path
from urllib.parse import urlparse, urlunparse

import psycopg
import pytest
from alembic import command
from alembic.config import Config
from testcontainers.postgres import PostgresContainer

APP_ROLE = "semanticgraph_app"
APP_PASSWORD = "semanticgraph_app"


@pytest.fixture(scope="session")
def postgres_container() -> Generator[PostgresContainer, None, None]:
    """Single session-wide Postgres container for all E2E tests."""
    with PostgresContainer("postgres:16-alpine") as postgres:
        yield postgres


@pytest.fixture(scope="session")
def postgres_admin_url(postgres_container: PostgresContainer) -> str:
    """Runs Alembic migrations to head on the container and ensures app role password."""
    url = postgres_container.get_connection_url().replace("postgresql+psycopg2://", "postgresql://")
    ini_path = Path("alembic.ini").resolve()
    cfg = Config(str(ini_path))
    cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(cfg, "head")

    # Ensure password authentication is valid for the application role
    with psycopg.connect(url, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute(f"ALTER ROLE {APP_ROLE} WITH LOGIN PASSWORD '{APP_PASSWORD}';")

    return url


@pytest.fixture(scope="session")
def app_db_url(postgres_admin_url: str) -> str:
    """Builds the connection URL for the non-owner application role."""
    parsed = urlparse(postgres_admin_url)
    netloc = f"{APP_ROLE}:{APP_PASSWORD}@{parsed.hostname}"
    if parsed.port:
        netloc += f":{parsed.port}"
    return urlunparse(parsed._replace(netloc=netloc))
