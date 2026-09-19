"""
Architecture fitness tests.

These fail the build when the hexagon leaks. They are the one rule that keeps
the boundary honest as the codebase grows, because nothing else notices a bad
import until it has spread.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

PACKAGE_ROOT = Path(__file__).resolve().parents[3] / "src" / "semanticgraph"

# domain/ and application/ describe the business. They may not know how it is
# delivered, stored, queued or called.
FORBIDDEN_IN_INNER_LAYERS = {
    "fastapi",
    "starlette",
    "sqlmodel",
    "sqlalchemy",
    "celery",
    "redis",
    "temporalio",
    "anthropic",
    "boto3",
    "neo4j",
    "psycopg",
    "pgvector",
}

INNER_LAYERS = ("domain", "application")


def _module_files(*relative: str) -> list[Path]:
    roots = [PACKAGE_ROOT.joinpath(r) for r in relative] or [PACKAGE_ROOT]
    return [p for root in roots for p in root.rglob("*.py")]


def _imported_roots(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            roots.add(node.module.split(".")[0])
    return roots


@pytest.mark.parametrize("path", _module_files(*INNER_LAYERS), ids=str)
def test_inner_layers_import_no_infrastructure(path: Path) -> None:
    leaked = _imported_roots(path) & FORBIDDEN_IN_INNER_LAYERS
    assert not leaked, (
        f"{path.relative_to(PACKAGE_ROOT)} imports {sorted(leaked)}. "
        "domain/ and application/ define the business and its ports; "
        "put the dependency behind a port and implement it in adapters/outbound/."
    )


@pytest.mark.parametrize("path", _module_files(), ids=str)
def test_application_code_never_imports_the_test_suite(path: Path) -> None:
    assert "tests" not in _imported_roots(path), (
        f"{path.relative_to(PACKAGE_ROOT)} imports the test suite. "
        "Shipping code cannot depend on tests; move the fake into "
        "adapters/outbound/inmemory/ and select it through configuration."
    )
