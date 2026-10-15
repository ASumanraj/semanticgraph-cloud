"""Tests that the API and worker connected role enforces RLS (T-228 Item 1).

Verifies:
1. docker-compose.real.yml configures the non-owner role `semanticgraph_app`
   for both api and worker, with no superuser or BYPASSRLS privileges.
2. The role does NOT own the tenant tables.
3. Queries executed as `semanticgraph_app` with no tenant context set return zero rows.
4. Fails loudly if the connected role is a superuser or has rolbypassrls=True.
"""

from pathlib import Path
from urllib.parse import urlparse

import psycopg
import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]


def get_compose_db_urls() -> tuple[str, str, str]:
    compose_path = REPO_ROOT / "docker-compose.real.yml"
    with open(compose_path, encoding="utf-8") as f:
        compose = yaml.safe_load(f)

    api = compose["services"]["api"]
    worker = compose["services"]["worker"]

    api_env = dict(e.split("=", 1) for e in api.get("environment", []) if "=" in e)
    worker_env = dict(e.split("=", 1) for e in worker.get("environment", []) if "=" in e)

    return (
        api_env.get("DATABASE_URL", ""),
        worker_env.get("DATABASE_URL", ""),
        api_env.get("ADMIN_DATABASE_URL", ""),
    )


def test_compose_config_uses_non_owner_role():
    """Verify compose config points api and worker to semanticgraph_app, not superuser."""
    api_db_url, worker_db_url, admin_db_url = get_compose_db_urls()

    assert api_db_url, "api DATABASE_URL must be set"
    assert worker_db_url, "worker DATABASE_URL must be set"
    assert admin_db_url, "api ADMIN_DATABASE_URL must be set"

    api_user = urlparse(api_db_url).username
    worker_user = urlparse(worker_db_url).username
    admin_user = urlparse(admin_db_url).username

    assert api_user == "semanticgraph_app", f"api role must be semanticgraph_app, got '{api_user}'"
    assert worker_user == "semanticgraph_app", (
        f"worker role must be semanticgraph_app, got '{worker_user}'"
    )
    assert admin_user == "user", f"admin role must be 'user', got '{admin_user}'"
    assert api_user != admin_user, "API role must NOT be the admin superuser role"


def assert_role_satisfies_rls(cur, role_name: str) -> None:
    """Verifies that a role exists, is NOT a superuser, and does NOT bypass RLS."""
    cur.execute(
        "SELECT rolname, rolsuper, rolbypassrls FROM pg_roles WHERE rolname = %s",
        (role_name,),
    )
    row = cur.fetchone()
    assert row is not None, f"Role '{role_name}' does not exist in PostgreSQL"
    rolname, rolsuper, rolbypassrls = row
    assert not rolsuper, f"Connected role '{rolname}' is a superuser (rolsuper=True)"
    assert not rolbypassrls, f"Connected role '{rolname}' bypasses RLS (rolbypassrls=True)"


@pytest.mark.asyncio
async def test_api_connected_role_not_superuser_and_lacks_bypassrls():
    """Verify that semanticgraph_app role is not superuser and has rolbypassrls=False."""
    api_db_url, _, _ = get_compose_db_urls()
    api_user = urlparse(api_db_url).username or "semanticgraph_app"

    db_candidates = [
        "postgresql://user:password@localhost:5433/semanticgraph",
        "postgresql://user:password@localhost:5432/semanticgraph",
    ]
    admin_conn = None
    for cand in db_candidates:
        try:
            admin_conn = psycopg.connect(cand, autocommit=True)
            break
        except Exception:
            continue

    if admin_conn is None:
        pytest.skip("No running PostgreSQL available to check live pg_roles privileges")

    with admin_conn, admin_conn.cursor() as cur:
        # 1. API role passes RLS enforcement check
        assert_role_satisfies_rls(cur, api_user)

        # 2. Explicit proof that this check FAILS if a superuser/bypassrls role was connected
        with pytest.raises(AssertionError, match="super|bypass"):
            assert_role_satisfies_rls(cur, "user")

        # 3. Check table ownership: API role must not own the tables
        cur.execute(
            """
            SELECT c.relname, r.rolname as owner
            FROM pg_class c
            JOIN pg_roles r ON r.oid = c.relowner
            WHERE c.relname IN ('documents', 'semantic_chunks', 'entities', 'edges')
            """
        )
        for tbl_name, owner in cur.fetchall():
            assert owner != api_user, f"API role '{api_user}' must not own table '{tbl_name}'"


@pytest.mark.asyncio
async def test_semanticgraph_app_queries_return_zero_without_tenant():
    """Verify queries as semanticgraph_app return zero rows without tenant context set."""
    app_candidates = [
        "postgresql://semanticgraph_app:semanticgraph_app@localhost:5433/semanticgraph",
        "postgresql://semanticgraph_app:semanticgraph_app@localhost:5432/semanticgraph",
    ]
    app_conn = None
    for cand in app_candidates:
        try:
            app_conn = psycopg.connect(cand, autocommit=True)
            break
        except Exception:
            continue

    if app_conn is None:
        pytest.skip("No running PostgreSQL available with semanticgraph_app credentials")

    with app_conn, app_conn.cursor() as cur:
        cur.execute("SELECT current_user;")
        assert cur.fetchone()[0] == "semanticgraph_app"

        # Without app.current_tenant_id, all RLS-protected tables must evaluate to 0 rows
        for table in ("documents", "semantic_chunks", "entities", "edges"):
            cur.execute(f"SELECT count(*) FROM {table};")
            count = cur.fetchone()[0]
            assert count == 0, (
                f"RLS isolation breach: table '{table}' returned {count} rows "
                f"as semanticgraph_app without tenant context!"
            )
