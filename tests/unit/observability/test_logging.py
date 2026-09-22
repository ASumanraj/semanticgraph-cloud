"""Tests for logging with tenant attribution and telemetry hygiene (T-209).

Acceptance criteria verified:
- tenant_id is an attribute on every log line.
- Document text never reaches telemetry — ids and hashes only.
"""

from __future__ import annotations

import io
import json
import logging
from uuid import uuid4

import pytest

from semanticgraph.domain.models.entities import TenantId
from semanticgraph.observability.context import with_tenant
from semanticgraph.observability.logging import (
    DocumentTextInTelemetryError,
    TenantLogFilter,
    TenantStructuredFormatter,
    get_logger,
)


def test_tenant_id_on_every_log_line():
    """Every log line executed within tenant context carries tenant_id."""
    log_stream = io.StringIO()
    handler = logging.StreamHandler(log_stream)
    handler.addFilter(TenantLogFilter())
    handler.setFormatter(TenantStructuredFormatter())

    logger = logging.getLogger("test.tenant.logging")
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)
    logger.propagate = False

    tenant_id = TenantId(uuid4())

    # Log outside tenant context
    logger.info("System initializing")
    line1 = log_stream.getvalue().strip().split("\n")[-1]
    parsed1 = json.loads(line1)
    assert parsed1["message"] == "System initializing"
    assert parsed1["tenant_id"] is None or parsed1["tenant_id"] == ""

    # Log inside tenant context
    with with_tenant(tenant_id):
        logger.info(
            "Processing tenant request for doc_id=%s", "123e4567-e89b-12d3-a456-426614174000"
        )

    line2 = log_stream.getvalue().strip().split("\n")[-1]
    parsed2 = json.loads(line2)
    assert parsed2["tenant_id"] == str(tenant_id.value)
    assert "123e4567-e89b-12d3-a456-426614174000" in parsed2["message"]


def test_document_text_never_reaches_logs():
    """Attempting to log raw document text raises DocumentTextInTelemetryError or is rejected."""
    tenant_id = TenantId(uuid4())
    logger = get_logger("test.hygiene")

    with with_tenant(tenant_id):
        # 1. Forbidden keys in extra kwargs
        forbidden_keys = ["document_text", "raw_content", "text", "content", "document_body"]
        for key in forbidden_keys:
            with pytest.raises(
                DocumentTextInTelemetryError, match="Document text must never enter telemetry"
            ):
                logger.info("Processing item", extra={key: "Sensitive contract text here..."})

        # 2. String values in extra kwargs exceeding maximum content threshold (>500 chars)
        long_text = "a" * 501
        with pytest.raises(
            DocumentTextInTelemetryError, match="Document text must never enter telemetry"
        ):
            logger.info("Processing item", extra={"details": long_text})

        # 3. Legitimate attributes with ID and hash succeed
        logger.info(
            "Processed chunk",
            extra={
                "document_id": str(uuid4()),
                "chunk_id": str(uuid4()),
                "content_hash": "sha256:abc1234567890",
            },
        )
