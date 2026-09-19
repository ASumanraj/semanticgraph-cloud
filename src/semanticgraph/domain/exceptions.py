"""
Domain Exceptions for SemanticGraph Cloud.

These are pure domain errors with no framework coupling.
Adapters translate these into HTTP status codes or task retries.
"""


class DomainException(Exception):
    """Base exception for all domain errors."""
    def __init__(self, message: str, code: str = "DOMAIN_ERROR"):
        self.message = message
        self.code = code
        super().__init__(self.message)


class TenantNotFoundError(DomainException):
    """Raised when a Tenant cannot be located."""
    def __init__(self, tenant_id: str):
        super().__init__(
            message=f"Tenant '{tenant_id}' not found",
            code="TENANT_NOT_FOUND"
        )


class OntologyViolationError(DomainException):
    """Raised when an extracted Entity or Edge type is not in the Ontology."""
    def __init__(self, invalid_type: str, allowed_types: list[str]):
        super().__init__(
            message=f"Type '{invalid_type}' not in Ontology. Allowed: {allowed_types}",
            code="ONTOLOGY_VIOLATION"
        )


class ResolutionConflictError(DomainException):
    """Raised when Resolution encounters an irreconcilable merge conflict."""
    def __init__(self, entity_ids: list[str]):
        super().__init__(
            message=f"Cannot resolve entities: {entity_ids}",
            code="RESOLUTION_CONFLICT"
        )


class GraphIngestionError(DomainException):
    """Raised when a graph write operation fails."""
    def __init__(self, detail: str):
        super().__init__(
            message=f"Graph ingestion failed: {detail}",
            code="GRAPH_INGESTION_ERROR"
        )
