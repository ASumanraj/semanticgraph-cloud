"""Observability package: OpenTelemetry with tenant attribution (T-209)."""

from semanticgraph.observability.context import (
    TENANT_ID_HEADER,
    extract_tenant_context,
    get_current_tenant_id,
    inject_tenant_context,
    reset_tenant_context,
    set_current_tenant_id,
    with_tenant,
)
from semanticgraph.observability.instrumentation import InstrumentedLLMGateway
from semanticgraph.observability.lint import (
    TelemetryHygieneViolation,
    check_codebase_telemetry_hygiene,
    lint_source_string,
)
from semanticgraph.observability.logging import (
    DocumentTextInTelemetryError,
    TenantLogFilter,
    TenantStructuredFormatter,
    configure_logging,
    get_logger,
)
from semanticgraph.observability.metrics import (
    MetricRecord,
    get_in_memory_metric_records,
    record_llm_metrics,
    record_metric,
    reset_in_memory_metrics,
)
from semanticgraph.observability.tracing import (
    InMemorySpanExporter,
    RecordingSpan,
    SpanRecord,
    get_in_memory_spans,
    get_tracer,
    reset_in_memory_spans,
    trace_gen_ai_call,
)

__all__ = [
    "TENANT_ID_HEADER",
    "DocumentTextInTelemetryError",
    "InMemorySpanExporter",
    "InstrumentedLLMGateway",
    "MetricRecord",
    "RecordingSpan",
    "SpanRecord",
    "TelemetryHygieneViolation",
    "TenantLogFilter",
    "TenantStructuredFormatter",
    "check_codebase_telemetry_hygiene",
    "configure_logging",
    "extract_tenant_context",
    "get_current_tenant_id",
    "get_in_memory_metric_records",
    "get_in_memory_spans",
    "get_logger",
    "get_tracer",
    "inject_tenant_context",
    "lint_source_string",
    "record_llm_metrics",
    "record_metric",
    "reset_in_memory_metrics",
    "reset_in_memory_spans",
    "reset_tenant_context",
    "set_current_tenant_id",
    "trace_gen_ai_call",
    "with_tenant",
]
