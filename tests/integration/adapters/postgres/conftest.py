"""Shared fixtures for the postgres integration test suite.

Provides ``postgres_admin_url`` — the single source of truth for how this
suite connects to Postgres.  All per-module duplicates that previously lived
in individual test files have been removed in favour of this conftest.

Behaviour
---------
By default the fixture always spins up an isolated testcontainers Postgres
so the default test run never touches or truncates the developer's compose
database.

``SEMANTICGRAPH_USE_COMPOSE_DB=1``
    Use the compose database (``DATABASE_URL`` or the hardcoded default)
    instead of testcontainers.  Useful for debugging migrations against a
    persistent volume.

``SEMANTICGRAPH_REQUIRE_POSTGRES=1``
    Make the fixture *fail* (not skip) when Postgres is unavailable.  CI
    sets this so row-level-security proofs can never silently skip.
"""

from __future__ import annotations

import os
from collections.abc import Generator

import psycopg
import pytest

DEFAULT_PG_URL = "postgresql://user:password@localhost:5432/semanticgraph"
APP_ROLE = "semanticgraph_app"
APP_PASSWORD = "semanticgraph_app"


def _get_pg_admin_url() -> str | None:
    candidate = os.environ.get("DATABASE_URL") or DEFAULT_PG_URL
    if not candidate.startswith("postgres"):
        return None
    try:
        conn = psycopg.connect(candidate, connect_timeout=2)
        conn.close()
        return candidate
    except Exception:
        return None


@pytest.fixture(scope="module")
def postgres_admin_url() -> Generator[str, None, None]:
    """Isolated Postgres URL for integration tests.

    See module docstring for the three environment-variable toggles.
    """
    require_pg = os.environ.get("SEMANTICGRAPH_REQUIRE_POSTGRES", "").strip() == "1"
    use_compose = os.environ.get("SEMANTICGRAPH_USE_COMPOSE_DB", "").strip() == "1"

    if use_compose:
        url = _get_pg_admin_url()
        if url is not None:
            yield url
            return
        msg = (
            "SEMANTICGRAPH_USE_COMPOSE_DB=1 is set but Postgres is not reachable "
            f"at {os.environ.get('DATABASE_URL') or DEFAULT_PG_URL}"
        )
        if require_pg:
            pytest.fail(msg)
        else:
            pytest.skip(msg)
        return  # unreachable; satisfies type-checker

    # Default path: always use testcontainers for an isolated, throwaway database.
    try:
        from testcontainers.postgres import PostgresContainer

        with PostgresContainer("postgres:15-alpine") as container:
            pg_url = container.get_connection_url().replace(
                "postgresql+psycopg2://", "postgresql://"
            )
            yield pg_url
            return
    except Exception as exc:
        msg = f"PostgreSQL not reachable and testcontainers failed: {exc}"
        if require_pg:
            pytest.fail(msg)
        else:
            pytest.skip(msg)
