"""Telemetry Hygiene Linter and Review Rule (T-209).

Acceptance 4 & 5:
- Document text never reaches telemetry — IDs and cryptographic hashes only.
- A lint or review rule enforces that, before the codebase has 200 log statements.

Analyzes Python Abstract Syntax Trees (AST) across the codebase to statically detect
accidental logging or tracing of raw document text, prompts, or forbidden content keys.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

FORBIDDEN_IDENTIFIERS: frozenset[str] = frozenset({"document_text", "raw_content", "document_body"})
FORBIDDEN_ATTRS: frozenset[str] = frozenset(
    {"text", "content", "raw_content", "prompt", "document_text"}
)
LOGGING_METHODS: frozenset[str] = frozenset(
    {"debug", "info", "warning", "error", "critical", "exception", "log"}
)


@dataclass(frozen=True)
class TelemetryHygieneViolation:
    """Represents a violation where raw document text or prompts are passed to telemetry."""

    filename: str
    lineno: int
    col_offset: int
    message: str


class TelemetryHygieneVisitor(ast.NodeVisitor):
    """AST Visitor that traverses syntax trees checking log and trace calls for hygiene."""

    def __init__(self, filename: str) -> None:
        self.filename = filename
        self.violations: list[TelemetryHygieneViolation] = []

    def visit_Call(self, node: ast.Call) -> None:
        # Check if call is a logging or span method
        is_log_call = False
        is_span_set_attr = False

        if isinstance(node.func, ast.Attribute):
            if node.func.attr in LOGGING_METHODS:
                is_log_call = True
            elif node.func.attr == "set_attribute":
                is_span_set_attr = True

        if is_log_call:
            self._check_log_call(node)
        elif is_span_set_attr:
            self._check_span_set_attribute(node)

        self.generic_visit(node)

    def _check_log_call(self, node: ast.Call) -> None:
        # Check positional arguments for forbidden attributes (e.g. doc.text) or forbidden variables
        for arg in node.args:
            self._inspect_expression(arg, node)

        # Check 'extra' keyword argument if present
        for kw in node.keywords:
            if kw.arg == "extra" and isinstance(kw.value, ast.Dict):
                for key_node, val_node in zip(kw.value.keys, kw.value.values, strict=False):
                    if isinstance(key_node, ast.Constant) and isinstance(key_node.value, str):
                        key_str = key_node.value.lower()
                        if key_str in FORBIDDEN_ATTRS or key_str in FORBIDDEN_IDENTIFIERS:
                            self.violations.append(
                                TelemetryHygieneViolation(
                                    filename=self.filename,
                                    lineno=node.lineno,
                                    col_offset=node.col_offset,
                                    message=(
                                        f"Forbidden key '{key_str}' passed in logging extra. "
                                        "Telemetry carries IDs and cryptographic hashes only."
                                    ),
                                )
                            )
                    self._inspect_expression(val_node, node)

    def _check_span_set_attribute(self, node: ast.Call) -> None:
        if (
            node.args
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
        ):
            attr_name = node.args[0].value.lower()
            if attr_name in FORBIDDEN_ATTRS or attr_name in FORBIDDEN_IDENTIFIERS:
                self.violations.append(
                    TelemetryHygieneViolation(
                        filename=self.filename,
                        lineno=node.lineno,
                        col_offset=node.col_offset,
                        message=(
                            f"Forbidden span attribute '{attr_name}'. "
                            "Telemetry carries IDs and cryptographic hashes only."
                        ),
                    )
                )
        if len(node.args) > 1:
            self._inspect_expression(node.args[1], node)

    def _inspect_expression(self, expr: ast.AST | None, call_node: ast.Call) -> None:
        if expr is None:
            return

        # Check attribute access like doc.text or chunk.content
        if isinstance(expr, ast.Attribute):
            if expr.attr.lower() in FORBIDDEN_ATTRS:
                self.violations.append(
                    TelemetryHygieneViolation(
                        filename=self.filename,
                        lineno=call_node.lineno,
                        col_offset=call_node.col_offset,
                        message=(
                            f"Forbidden attribute '.{expr.attr}' passed to telemetry. "
                            "Telemetry carries IDs and cryptographic hashes only."
                        ),
                    )
                )

        # Check bare variable name like raw_content or prompt
        elif isinstance(expr, ast.Name):
            if expr.id.lower() in FORBIDDEN_IDENTIFIERS or expr.id.lower() == "prompt":
                self.violations.append(
                    TelemetryHygieneViolation(
                        filename=self.filename,
                        lineno=call_node.lineno,
                        col_offset=call_node.col_offset,
                        message=(
                            f"Forbidden variable '{expr.id}' passed to telemetry. "
                            "Telemetry carries IDs and cryptographic hashes only."
                        ),
                    )
                )

        # Check f-strings
        elif isinstance(expr, ast.JoinedStr):
            for part in expr.values:
                if isinstance(part, ast.FormattedValue):
                    self._inspect_expression(part.value, call_node)


def lint_source_string(code: str, filename: str = "<string>") -> list[TelemetryHygieneViolation]:
    """Runs AST telemetry hygiene analysis on a Python source code string."""
    try:
        tree = ast.parse(code, filename=filename)
    except SyntaxError:
        return []
    visitor = TelemetryHygieneVisitor(filename)
    visitor.visit(tree)
    return visitor.violations


def check_codebase_telemetry_hygiene(
    root_dir: Path,
    exclude_dirs: tuple[str, ...] = (".venv", ".git", "__pycache__", "tests"),
) -> list[TelemetryHygieneViolation]:
    """Scans all Python files in a directory tree for telemetry hygiene violations."""
    all_violations: list[TelemetryHygieneViolation] = []

    for file_path in root_dir.rglob("*.py"):
        if any(part in file_path.parts for part in exclude_dirs):
            continue

        try:
            content = file_path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue

        violations = lint_source_string(content, filename=str(file_path))
        all_violations.extend(violations)

    return all_violations
