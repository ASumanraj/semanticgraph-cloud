"""Signature comparison test for outbound ports and their Postgres implementations.

Acceptance requirement (T-110):
A test compares each port with its Postgres implementation by signature — method names,
parameter order and async-ness — not with isinstance, which on a runtime-checkable Protocol
only proves the names exist.
"""

from __future__ import annotations

import inspect

import pytest

from semanticgraph.adapters.outbound.postgres.deletion_repository import (
    PostgresDeletionRepository,
)
from semanticgraph.adapters.outbound.postgres.document_repository import (
    PostgresDocumentRepository,
)
from semanticgraph.adapters.outbound.postgres.ontology_repository import (
    PostgresOntologyRepository,
)
from semanticgraph.adapters.outbound.postgres.provenance_repository import (
    PostgresProvenanceRepository,
)
from semanticgraph.adapters.outbound.postgres.resolution_repository import (
    PostgresResolutionRepository,
)
from semanticgraph.adapters.outbound.postgres.temporal_repository import (
    PostgresTemporalFactRepository,
)
from semanticgraph.application.ports.outbound.assertion_store import AssertionStore
from semanticgraph.application.ports.outbound.deletion_repository import DeletionRepositoryPort
from semanticgraph.application.ports.outbound.document_repository import DocumentRepositoryPort
from semanticgraph.application.ports.outbound.ontology_store import OntologyStore
from semanticgraph.application.ports.outbound.resolution_decision_store import (
    ResolutionDecisionStore,
)
from semanticgraph.application.ports.outbound.temporal_store import TemporalFactStore

PORT_IMPL_PAIRS = [
    (AssertionStore, PostgresProvenanceRepository),
    (ResolutionDecisionStore, PostgresResolutionRepository),
    (TemporalFactStore, PostgresTemporalFactRepository),
    (OntologyStore, PostgresOntologyRepository),
    (DeletionRepositoryPort, PostgresDeletionRepository),
    (DocumentRepositoryPort, PostgresDocumentRepository),
]


def _get_protocol_methods(proto: type) -> list[str]:
    """Return all non-dunder callable attributes defined on the Protocol or its bases."""
    methods = []
    for name in dir(proto):
        if name.startswith("_"):
            continue
        attr = getattr(proto, name)
        if callable(attr):
            methods.append(name)
    return sorted(methods)


@pytest.mark.parametrize("port,impl", PORT_IMPL_PAIRS, ids=lambda x: getattr(x, "__name__", str(x)))
def test_port_signatures_match_postgres_implementation(port: type, impl: type) -> None:
    """Every method on the port exists on the Postgres implementation with identical signature."""
    port_methods = _get_protocol_methods(port)
    assert port_methods, f"Port {port.__name__} has no public methods"

    for method_name in port_methods:
        # 1. Method exists on implementation
        assert hasattr(impl, method_name), (
            f"Implementation {impl.__name__} missing method {method_name!r} "
            f"from port {port.__name__}"
        )

        port_fn = getattr(port, method_name)
        impl_fn = getattr(impl, method_name)

        # 2. Both must have the same async-ness
        port_async = inspect.iscoroutinefunction(port_fn)
        impl_async = inspect.iscoroutinefunction(impl_fn)
        assert port_async == impl_async, (
            f"Async-ness mismatch for {port.__name__}.{method_name} vs "
            f"{impl.__name__}.{method_name}: port is {port_async}, impl is {impl_async}"
        )

        # 3. Parameter names and order must match (excluding 'self')
        port_sig = inspect.signature(port_fn)
        impl_sig = inspect.signature(impl_fn)

        port_params = [p for p in port_sig.parameters if p != "self"]
        impl_params = [p for p in impl_sig.parameters if p != "self"]

        assert port_params == impl_params, (
            f"Parameter mismatch for {port.__name__}.{method_name}: "
            f"port has {port_params}, impl has {impl_params}"
        )
