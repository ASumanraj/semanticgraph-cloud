"""Tests for the telemetry hygiene lint rule (T-209).

Acceptance criteria verified:
- Document text never reaches telemetry — ids and hashes only.
- A lint or review rule enforces that, before the codebase has 200 log statements.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from semanticgraph.observability.lint import (
    check_codebase_telemetry_hygiene,
    lint_source_string,
)


def test_lint_detects_forbidden_variable_logging():
    """Linter detects logging variables named text, content, prompt, etc."""
    bad_code = """
import logging
logger = logging.getLogger(__name__)

def process(doc):
    logger.info("Processing document text: %s", doc.text)
    logger.debug("Raw content: %s", raw_content)
    logger.warning("Prompt: %s", prompt)
"""
    violations = lint_source_string(bad_code, filename="example.py")
    assert len(violations) >= 3
    messages = [v.message for v in violations]
    assert any("doc.text" in m or "text" in m for m in messages)
    assert any("raw_content" in m for m in messages)
    assert any("prompt" in m for m in messages)


def test_lint_detects_forbidden_extra_keys():
    """Linter detects passing document text keys in extra dict."""
    bad_code = """
import logging
logger = logging.getLogger(__name__)

def process(doc):
    logger.info("Processing", extra={"document_text": "abc", "content": "xyz"})
"""
    violations = lint_source_string(bad_code, filename="example.py")
    assert len(violations) >= 2


def test_lint_detects_forbidden_span_attributes():
    """Linter detects setting forbidden attributes on spans."""
    bad_code = """
from semanticgraph.observability.tracing import get_tracer
tracer = get_tracer("my_tracer")

def run(doc):
    with tracer.start_as_current_span("my_span") as span:
        span.set_attribute("text", doc.text)
        span.set_attribute("prompt", "What is...")
"""
    violations = lint_source_string(bad_code, filename="example.py")
    assert len(violations) >= 2


def test_lint_allows_safe_telemetry():
    """Linter permits IDs, hashes, token counts, statuses, and counts."""
    good_code = """
import logging
logger = logging.getLogger(__name__)

def process(doc):
    logger.info("Processing document id=%s, hash=%s, count=%d", doc.id, doc.content_hash, 42)
    logger.info("Ingestion completed", extra={"document_id": str(doc.id), "status": "resolved"})
"""
    violations = lint_source_string(good_code, filename="example.py")
    assert len(violations) == 0


def test_codebase_telemetry_hygiene():
    """Enforces telemetry hygiene across all Python files in src/semanticgraph."""
    src_dir = Path("src/semanticgraph").resolve()
    violations = check_codebase_telemetry_hygiene(src_dir)
    if violations:
        formatted = "\n".join(
            f"{v.filename}:{v.lineno}:{v.col_offset}: {v.message}" for v in violations
        )
        pytest.fail(f"Telemetry hygiene violations found in codebase:\n{formatted}")
