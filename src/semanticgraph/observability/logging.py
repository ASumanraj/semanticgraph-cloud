"""Logging with Tenant Attribution and Telemetry Hygiene (T-209).

Upholds:
- `tenant_id` on every log line.
- Document text never reaches telemetry — IDs and cryptographic hashes only.
- Strict enforcement against raw document text in log messages and extra attributes.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any

from semanticgraph.observability.context import get_current_tenant_id

FORBIDDEN_TELEMETRY_KEYS: frozenset[str] = frozenset(
    {"document_text", "raw_content", "text", "content", "document_body", "prompt"}
)
MAX_SAFE_ATTR_LENGTH: int = 500


class DocumentTextInTelemetryError(ValueError):
    """Raised when raw document text or prompts are passed into telemetry.

    Observability retention is a disclosed GDPR exposure. Telemetry carries
    identifiers and cryptographic hashes only.
    """


def assert_telemetry_hygiene(data: Any, key_name: str = "") -> None:
    """Recursively validates that data does not contain forbidden keys or raw document content."""
    if key_name.lower() in FORBIDDEN_TELEMETRY_KEYS:
        raise DocumentTextInTelemetryError(
            f"Document text must never enter telemetry. Key '{key_name}' is forbidden; "
            f"record identifiers and SHA-256 hashes only."
        )

    if isinstance(data, dict):
        for k, v in data.items():
            assert_telemetry_hygiene(v, str(k))
    elif isinstance(data, (list, tuple, set)):
        for item in data:
            assert_telemetry_hygiene(item, key_name)
    elif isinstance(data, str) and len(data) > MAX_SAFE_ATTR_LENGTH:
        raise DocumentTextInTelemetryError(
            f"Document text must never enter telemetry. String attribute '{key_name}' exceeds "
            f"{MAX_SAFE_ATTR_LENGTH} characters; record identifiers and SHA-256 hashes only."
        )


class TenantLogFilter(logging.Filter):
    """Logging filter that injects tenant_id from active context into every LogRecord."""

    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "message"):
            record.message = record.getMessage()
        tenant_id = get_current_tenant_id()
        if not hasattr(record, "tenant_id") or not record.tenant_id:
            record.tenant_id = str(tenant_id.value) if tenant_id is not None else ""

        # Validate telemetry hygiene on primary rendered message
        rendered_msg = record.getMessage()
        assert_telemetry_hygiene(rendered_msg, "message")

        # Validate telemetry hygiene on extra attributes
        for k, v in record.__dict__.items():
            if k in (
                "args",
                "asctime",
                "created",
                "exc_info",
                "exc_text",
                "filename",
                "funcName",
                "levelname",
                "levelno",
                "lineno",
                "module",
                "msecs",
                "message",
                "msg",
                "name",
                "pathname",
                "process",
                "processName",
                "relativeCreated",
                "stack_info",
                "thread",
                "threadName",
                "tenant_id",
            ):
                continue
            assert_telemetry_hygiene(v, k)

        return True


class TenantStructuredFormatter(logging.Formatter):
    """JSON structured formatter ensuring tenant_id and metadata are emitted cleanly."""

    def format(self, record: logging.LogRecord) -> str:
        tenant_id = getattr(record, "tenant_id", None) or ""
        msg = record.getMessage()

        entry: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": msg,
            "tenant_id": tenant_id,
        }

        # Include custom extra fields
        for k, v in record.__dict__.items():
            if k in (
                "args",
                "asctime",
                "created",
                "exc_info",
                "exc_text",
                "filename",
                "funcName",
                "levelname",
                "levelno",
                "lineno",
                "module",
                "msecs",
                "message",
                "msg",
                "name",
                "pathname",
                "process",
                "processName",
                "relativeCreated",
                "stack_info",
                "thread",
                "threadName",
                "tenant_id",
            ):
                continue
            entry[k] = v

        return json.dumps(entry)


class HygieneLogger(logging.LoggerAdapter):
    """Logger adapter that enforces telemetry hygiene on log calls before emission."""

    def log(self, level: int, msg: Any, *args: Any, **kwargs: Any) -> None:
        extra = kwargs.get("extra")
        if extra:
            assert_telemetry_hygiene(extra)
        if isinstance(msg, str) and len(msg) > MAX_SAFE_ATTR_LENGTH:
            assert_telemetry_hygiene(msg, "message")
        super().log(level, msg, *args, **kwargs)

    def process(self, msg: Any, kwargs: Any) -> tuple[Any, Any]:
        extra = kwargs.get("extra")
        if extra:
            assert_telemetry_hygiene(extra)
        return msg, kwargs


def get_logger(name: str) -> HygieneLogger:
    """Returns a logger equipped with tenant logging filter and hygiene checks."""
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    if not any(isinstance(f, TenantLogFilter) for f in logger.filters):
        logger.addFilter(TenantLogFilter())
    return HygieneLogger(logger, {})


def configure_logging(level: int = logging.INFO) -> None:
    """Configures root logging with TenantLogFilter and structured formatting."""
    root = logging.getLogger()
    root.setLevel(level)

    tenant_filter = TenantLogFilter()
    formatter = TenantStructuredFormatter()

    has_tenant_filter = any(isinstance(f, TenantLogFilter) for f in root.filters)
    if not has_tenant_filter:
        root.addFilter(tenant_filter)

    for h in root.handlers:
        if not any(isinstance(f, TenantLogFilter) for f in h.filters):
            h.addFilter(tenant_filter)
        if not type(h).__name__.startswith("LogCapture"):
            h.setFormatter(formatter)
