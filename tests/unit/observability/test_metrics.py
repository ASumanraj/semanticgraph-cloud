"""Tests for metrics with tenant attribution and gen_ai.* token usage (T-209).

Acceptance criteria verified:
- tenant_id is an attribute on every metric measurement.
- Stable gen_ai.* metrics: operation, provider, model, input and output tokens.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from semanticgraph.domain.models.entities import TenantId
from semanticgraph.observability.context import with_tenant
from semanticgraph.observability.metrics import (
    get_in_memory_metric_records,
    record_llm_metrics,
    reset_in_memory_metrics,
)


@pytest.fixture(autouse=True)
def clean_metrics():
    reset_in_memory_metrics()
    yield
    reset_in_memory_metrics()


def test_tenant_id_attribute_on_every_metric():
    """All metrics carry tenant_id alongside gen_ai.* dimensions."""
    tenant_id = TenantId(uuid4())

    with with_tenant(tenant_id):
        record_llm_metrics(
            operation="extraction",
            provider="anthropic",
            model="claude-sonnet-5",
            input_tokens=1000,
            output_tokens=250,
            cache_read_tokens=150,
            cache_write_tokens=50,
            duration_seconds=1.23,
        )

    records = get_in_memory_metric_records()
    assert len(records) >= 2  # token usage measurements and latency measurement

    # Check token metrics
    token_records = [r for r in records if r.name == "gen_ai.client.token.usage"]
    assert len(token_records) >= 2  # at least input and output

    input_rec = next(r for r in token_records if r.attributes.get("gen_ai.token.type") == "input")
    assert input_rec.value == 1000
    assert input_rec.attributes.get("tenant_id") == str(tenant_id.value)
    assert input_rec.attributes.get("gen_ai.system") == "anthropic"
    assert input_rec.attributes.get("gen_ai.request.model") == "claude-sonnet-5"
    assert input_rec.attributes.get("gen_ai.operation.name") == "extraction"

    output_rec = next(r for r in token_records if r.attributes.get("gen_ai.token.type") == "output")
    assert output_rec.value == 250
    assert output_rec.attributes.get("tenant_id") == str(tenant_id.value)

    # Check latency metric
    duration_records = [r for r in records if r.name == "gen_ai.client.operation.duration"]
    assert len(duration_records) == 1
    dur_rec = duration_records[0]
    assert dur_rec.value == 1.23
    assert dur_rec.attributes.get("tenant_id") == str(tenant_id.value)
    assert dur_rec.attributes.get("gen_ai.system") == "anthropic"
