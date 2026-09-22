"""OpenTelemetry Tracing with Tenant Attribution and GenAI Instrumentation (T-209).

Upholds:
- `tenant_id` is an attribute on every span.
- Stable `gen_ai.*` core is instrumented: operation, provider, model, input/output tokens.
- Document text never reaches telemetry — IDs and cryptographic hashes only.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from semanticgraph.observability.context import get_current_tenant_id
from semanticgraph.observability.logging import assert_telemetry_hygiene


@dataclass
class SpanRecord:
    """Captured trace span representation for telemetry export and inspection."""

    name: str
    attributes: dict[str, Any] = field(default_factory=dict)
    status: str = "OK"
    start_time: datetime = field(default_factory=lambda: datetime.now(UTC))
    end_time: datetime | None = None


_IN_MEMORY_SPANS: list[SpanRecord] = []


def get_in_memory_spans() -> list[SpanRecord]:
    """Returns all spans recorded in the in-memory telemetry buffer."""
    return list(_IN_MEMORY_SPANS)


def reset_in_memory_spans() -> None:
    """Clears the in-memory telemetry span buffer."""
    _IN_MEMORY_SPANS.clear()


class InMemorySpanExporter:
    """Exporter interface accessing in-memory telemetry spans."""

    @staticmethod
    def get_finished_spans() -> list[SpanRecord]:
        return get_in_memory_spans()

    @staticmethod
    def clear() -> None:
        reset_in_memory_spans()


class RecordingSpan:
    """Trace span that automatically captures tenant attribution and enforces hygiene."""

    def __init__(self, name: str, attributes: dict[str, Any] | None = None) -> None:
        self.name = name
        self.attributes: dict[str, Any] = {}
        self.start_time = datetime.now(UTC)
        self.end_time: datetime | None = None
        self.status = "OK"

        # 1. Automatically inject tenant_id from active context
        tenant_id = get_current_tenant_id()
        if tenant_id is not None:
            self.attributes["tenant_id"] = str(tenant_id.value)

        # 2. Inject initial attributes with hygiene verification
        if attributes:
            for k, v in attributes.items():
                self.set_attribute(k, v)

    def set_attribute(self, key: str, value: Any) -> None:
        """Sets an attribute on the span after verifying telemetry hygiene."""
        assert_telemetry_hygiene(value, key)
        self.attributes[key] = value

    def set_status(self, status: str) -> None:
        self.status = status

    def end(self) -> None:
        self.end_time = datetime.now(UTC)
        _IN_MEMORY_SPANS.append(
            SpanRecord(
                name=self.name,
                attributes=dict(self.attributes),
                status=self.status,
                start_time=self.start_time,
                end_time=self.end_time,
            )
        )

    def __enter__(self) -> RecordingSpan:
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if exc_type is not None:
            self.status = "ERROR"
            self.attributes["error.type"] = exc_type.__name__
        self.end()


class TenantTracer:
    """Tracer producing spans with automatic tenant attribution and hygiene checks."""

    def __init__(self, name: str) -> None:
        self.name = name

    @contextmanager
    def start_as_current_span(
        self,
        name: str,
        attributes: dict[str, Any] | None = None,
    ) -> Iterator[RecordingSpan]:
        span = RecordingSpan(name=name, attributes=attributes)
        with span:
            yield span


def get_tracer(name: str) -> TenantTracer:
    """Returns a tracer for the given instrumentation name."""
    return TenantTracer(name)


class GenAICallRecorder:
    """Helper for populating stable gen_ai.* attributes on a span."""

    def __init__(self, span: RecordingSpan) -> None:
        self._span = span

    def set_usage(
        self,
        input_tokens: int,
        output_tokens: int,
        cache_read_tokens: int = 0,
        cache_write_tokens: int = 0,
    ) -> None:
        """Instruments stable gen_ai.usage.* attributes."""
        self._span.set_attribute("gen_ai.usage.input_tokens", input_tokens)
        self._span.set_attribute("gen_ai.usage.output_tokens", output_tokens)
        if cache_read_tokens:
            self._span.set_attribute("gen_ai.usage.cache_read_tokens", cache_read_tokens)
        if cache_write_tokens:
            self._span.set_attribute("gen_ai.usage.cache_write_tokens", cache_write_tokens)


@contextmanager
def trace_gen_ai_call(
    operation: str,
    provider: str,
    model: str,
    scope: str | None = None,
) -> Iterator[GenAICallRecorder]:
    """Instruments a gen_ai.* call with OpenTelemetry semantic conventions.

    Span name format: {gen_ai.operation.name} {gen_ai.request.model}
    Span attributes include:
    - tenant_id
    - gen_ai.system
    - gen_ai.request.model
    - gen_ai.operation.name
    - gen_ai.usage.input_tokens
    - gen_ai.usage.output_tokens
    """
    span_name = f"{operation} {model}"
    tracer = get_tracer("semanticgraph.gen_ai")
    initial_attrs: dict[str, Any] = {
        "gen_ai.system": provider,
        "gen_ai.request.model": model,
        "gen_ai.operation.name": operation,
    }
    if scope:
        initial_attrs["scope"] = scope

    with tracer.start_as_current_span(span_name, attributes=initial_attrs) as span:
        yield GenAICallRecorder(span)
