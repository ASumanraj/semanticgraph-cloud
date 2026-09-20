"""
Integration tests for Alembic migrations.

Tests T-200 acceptance criteria:
1. `alembic upgrade head` builds the schema from empty.
2. `alembic downgrade base` reverses it completely.
3. Every table has `tenant_id`, and every composite index leads with it.
4. `create_all` is not used; tables appear via Alembic migrations.
5. An autogenerate run against head produces an empty revision (zero schema drift).
"""

from __future__ import annotations

import os
from collections.abc import Generator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect


@pytest.fixture
def alembic_config(tmp_path: Path) -> Generator[tuple[Config, str], None, None]:
    """Provides an isolated database and configured Alembic Config object."""
    db_file = tmp_path / "migration_test.db"
    url = f"sqlite:///{db_file.as_posix()}"

    ini_path = Path("alembic.ini").resolve()
    cfg = Config(str(ini_path))
    cfg.set_main_option("sqlalchemy.url", url)

    old_env = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = url

    try:
        yield cfg, url
    finally:
        if old_env is not None:
            os.environ["DATABASE_URL"] = old_env
        else:
            os.environ.pop("DATABASE_URL", None)


class TestAlembicBaselineMigrations:
    def test_upgrade_head_builds_schema_from_empty(self, alembic_config):
        cfg, url = alembic_config
        engine = create_engine(url)

        # Before upgrade: empty
        insp = inspect(engine)
        assert insp.get_table_names() == []

        # Upgrade to head
        command.upgrade(cfg, "head")

        # After upgrade: tables exist
        insp = inspect(engine)
        tables = [t for t in insp.get_table_names() if t != "alembic_version"]
        assert "documents" in tables
        assert "semantic_chunks" in tables

    def test_downgrade_base_reverses_schema(self, alembic_config):
        cfg, url = alembic_config
        engine = create_engine(url)

        command.upgrade(cfg, "head")
        insp = inspect(engine)
        tables = [t for t in insp.get_table_names() if t != "alembic_version"]
        assert len(tables) >= 2

        # Downgrade to base
        command.downgrade(cfg, "base")

        insp = inspect(engine)
        remaining = [t for t in insp.get_table_names() if t != "alembic_version"]
        assert remaining == []

    def test_every_table_has_tenant_id_and_composite_indexes_lead_with_it(self, alembic_config):
        cfg, url = alembic_config
        command.upgrade(cfg, "head")

        engine = create_engine(url)
        insp = inspect(engine)
        tables = [t for t in insp.get_table_names() if t != "alembic_version"]

        assert len(tables) >= 2
        for table_name in tables:
            columns = {col["name"]: col for col in insp.get_columns(table_name)}
            assert "tenant_id" in columns, f"Table '{table_name}' is missing tenant_id column"
            assert not columns["tenant_id"]["nullable"], (
                f"tenant_id in '{table_name}' must be NOT NULL"
            )

            # Check all composite indexes lead with tenant_id
            for idx in insp.get_indexes(table_name):
                col_names = idx["column_names"]
                if len(col_names) > 1:
                    assert col_names[0] == "tenant_id", (
                        f"Index '{idx['name']}' on '{table_name}' does not "
                        f"lead with tenant_id: {col_names}"
                    )

    def test_autogenerate_run_against_head_produces_empty_revision(self, alembic_config):
        cfg, _ = alembic_config
        command.upgrade(cfg, "head")

        # check() verifies autogenerate produces no new operations
        command.check(cfg)
