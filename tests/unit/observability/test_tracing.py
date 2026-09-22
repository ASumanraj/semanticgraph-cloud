"""Tests for OpenTelemetry tracing and gen_ai.* instrumentation (T-209).

Acceptance criteria verified:
- tenant_id is a resource or span attribute on every span.
- The stable gen_ai.* core is instrumented: operation, provider, model, input and output tokens.
- Document text never reaches telemetry — ids and hashes only.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from semanticgraph.domain.models.entities import TenantId
from semanticgraph.observability.context import with_tenant
from semanticgraph.observability.logging import DocumentTextInTelemetryError
from semanticgraph.observability.tracing import (
    get_in_memory_spans,
    get_tracer,
    reset_in_memory_spans,
    trace_gen_ai_call,
)


@pytest.fixture(autouse=True)
def clean_spans():
    reset_in_memory_spans()
    yield
    reset_in_memory_spans()


def test_tenant_id_attribute_on_every_span():
    """Every span created within a tenant context carries tenant_id as an attribute."""
    tracer = get_tracer("test.tracer")
    tenant_id = TenantId(uuid4())

    with with_tenant(tenant_id), tracer.start_as_current_span("test_operation") as span:
        span.set_attribute("custom_attr", "custom_val")

    spans = get_in_memory_spans()
    assert len(spans) == 1
    recorded_span = spans[0]
    assert recorded_span.name == "test_operation"
    assert recorded_span.attributes.get("tenant_id") == str(tenant_id.value)
    assert recorded_span.attributes.get("custom_attr") == "custom_val"


def test_gen_ai_core_instrumentation():
    """The stable gen_ai.* core is instrumented:
    operation, provider, model, input and output tokens.
    """
    tenant_id = TenantId(uuid4())

    with (
        with_tenant(tenant_id),
        trace_gen_ai_call(
            operation="chat",
            provider="anthropic",
            model="claude-sonnet-5",
            scope="pipeline:extraction",
        ) as call,
    ):
        call.set_usage(
            input_tokens=1250,
            output_tokens=320,
            cache_read_tokens=400,
            cache_write_tokens=100,
        )

    spans = get_in_memory_spans()
    assert len(spans) == 1
    span = spans[0]

    # OpenTelemetry semantic conventions for GenAI:
    # Span name: {gen_ai.operation.name} {gen_ai.request.model}
    assert span.name == "chat claude-sonnet-5"

    attrs = span.attributes
    assert attrs.get("tenant_id") == str(tenant_id.value)
    assert attrs.get("gen_ai.system") == "anthropic"
    assert attrs.get("gen_ai.request.model") == "claude-sonnet-5"
    assert attrs.get("gen_ai.operation.name") == "chat"
    assert attrs.get("gen_ai.usage.input_tokens") == 1250
    assert attrs.get("gen_ai.usage.output_tokens") == 320
    assert attrs.get("gen_ai.usage.cache_read_tokens") == 400
    assert attrs.get("gen_ai.usage.cache_write_tokens") == 100
    assert attrs.get("scope") == "pipeline:extraction"


def test_document_text_never_reaches_spans():
    """Document text must never enter span attributes or events."""
    tracer = get_tracer("test.hygiene.tracer")
    tenant_id = TenantId(uuid4())

    with with_tenant(tenant_id), tracer.start_as_current_span("extraction_span") as span:
        # Setting forbidden keys raises DocumentTextInTelemetryError
        forbidden_keys = ["document_text", "raw_content", "text", "content", "prompt"]
        for key in forbidden_keys:
            with pytest.raises(
                DocumentTextInTelemetryError, match="Document text must never enter telemetry"
            ):
                span.set_attribute(key, "Raw document or prompt text")

        # Setting long strings (> 500 chars) raises DocumentTextInTelemetryError
        long_val = "x" * 501
        with pytest.raises(
            DocumentTextInTelemetryError, match="Document text must never enter telemetry"
        ):
            span.set_attribute("description", long_val)

        # Allowed attributes: IDs, hashes, token counts, models
        doc_id = str(uuid4())
        span.set_attribute("document_id", doc_id)
        span.set_attribute("document_hash", "sha256:fedcba9876543210")
