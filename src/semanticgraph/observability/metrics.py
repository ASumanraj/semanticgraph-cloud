"""OpenTelemetry Metrics with Tenant Attribution and GenAI Instrumentation (T-209).

Upholds:
- `tenant_id` is an attribute on every metric measurement.
- Stable `gen_ai.*` metrics: operation, provider, model, token counts, and operation duration.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from semanticgraph.observability.context import get_current_tenant_id


@dataclass
class MetricRecord:
    """Captured metric observation with dimensional attributes."""

    name: str
    value: float | int
    attributes: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))


_IN_MEMORY_METRICS: list[MetricRecord] = []


def get_in_memory_metric_records() -> list[MetricRecord]:
    """Returns all metrics recorded in the in-memory telemetry buffer."""
    return list(_IN_MEMORY_METRICS)


def reset_in_memory_metrics() -> None:
    """Clears the in-memory telemetry metric buffer."""
    _IN_MEMORY_METRICS.clear()


def record_metric(
    name: str,
    value: float | int,
    attributes: dict[str, Any] | None = None,
) -> None:
    """Records a metric measurement ensuring tenant_id attribute is injected."""
    attrs = dict(attributes or {})
    tenant_id = get_current_tenant_id()
    if tenant_id is not None and "tenant_id" not in attrs:
        attrs["tenant_id"] = str(tenant_id.value)

    _IN_MEMORY_METRICS.append(
        MetricRecord(
            name=name,
            value=value,
            attributes=attrs,
        )
    )


def record_llm_metrics(
    operation: str,
    provider: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    cache_read_tokens: int = 0,
    cache_write_tokens: int = 0,
    duration_seconds: float | None = None,
    extra_attributes: dict[str, Any] | None = None,
) -> None:
    """Instruments stable gen_ai.* metric conventions with tenant attribution.

    Metrics emitted:
    - `gen_ai.client.token.usage`: Token counts broken down by token type
    - `gen_ai.client.operation.duration`: Operation latency in seconds (if provided)
    """
    base_attrs: dict[str, Any] = {
        "gen_ai.system": provider,
        "gen_ai.request.model": model,
        "gen_ai.operation.name": operation,
    }
    if extra_attributes:
        base_attrs.update(extra_attributes)

    # 1. Input tokens
    record_metric(
        name="gen_ai.client.token.usage",
        value=input_tokens,
        attributes={**base_attrs, "gen_ai.token.type": "input"},
    )

    # 2. Output tokens
    record_metric(
        name="gen_ai.client.token.usage",
        value=output_tokens,
        attributes={**base_attrs, "gen_ai.token.type": "output"},
    )

    # 3. Cache read tokens
    if cache_read_tokens:
        record_metric(
            name="gen_ai.client.token.usage",
            value=cache_read_tokens,
            attributes={**base_attrs, "gen_ai.token.type": "cache_read"},
        )

    # 4. Cache write tokens
    if cache_write_tokens:
        record_metric(
            name="gen_ai.client.token.usage",
            value=cache_write_tokens,
            attributes={**base_attrs, "gen_ai.token.type": "cache_write"},
        )

    # 5. Latency duration
    if duration_seconds is not None:
        record_metric(
            name="gen_ai.client.operation.duration",
            value=duration_seconds,
            attributes=base_attrs,
        )
