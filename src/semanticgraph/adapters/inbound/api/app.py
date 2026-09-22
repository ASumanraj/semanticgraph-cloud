"""
FastAPI Application Entrypoint.

Per hexagonal-architecture skill: this is the composition root wiring point.
Per error-handling skill: global exception handlers translate domain errors
to standard API error envelopes.
Per fastapi skill: uses lifespan, includes routers, no ORJSONResponse.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from semanticgraph.domain.exceptions import DomainException
from semanticgraph.domain.provenance.locator import QuoteNotFoundError

logger = logging.getLogger("semanticgraph")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Build the container once, from configuration, and hang it on app.state."""
    from semanticgraph.composition.container import adapter_profile, default_container
    from semanticgraph.control.usage.models import verify_routable_models_priced
    from semanticgraph.observability.logging import configure_logging

    configure_logging()
    container = getattr(app.state, "container", None) or default_container()
    app.state.container = container
    verify_routable_models_priced(container.model_routing)
    logger.info(
        "Hosted model dependencies: %s", sorted(container.model_routing.get_hosted_models())
    )
    logger.info("SemanticGraph Cloud started (adapter profile: %s)", adapter_profile())
    yield
    logger.info("SemanticGraph Cloud shutting down")


def create_app() -> FastAPI:
    app = FastAPI(
        title="SemanticGraph Cloud API",
        description="Multi-tenant Managed GraphRAG Platform",
        version="0.1.0",
        lifespan=lifespan,
    )

    @app.middleware("http")
    async def tenant_context_middleware(request: Request, call_next):
        from uuid import UUID

        from semanticgraph.domain.models.entities import TenantId
        from semanticgraph.observability.context import with_tenant

        tenant_header = request.headers.get("x-tenant-id")
        tenant_id = None
        if tenant_header:
            try:
                tenant_id = TenantId(value=UUID(tenant_header))
            except (ValueError, TypeError):
                tenant_id = None

        with with_tenant(tenant_id):
            return await call_next(request)

    # --- Global Exception Handlers (error-handling skill) ---

    @app.exception_handler(QuoteNotFoundError)
    async def quote_not_found_handler(request: Request, exc: QuoteNotFoundError) -> JSONResponse:
        """Reject fabricated quotes that cannot be located in the chunk text (T-110)."""
        return JSONResponse(
            status_code=422,
            content={"error": {"code": "FABRICATED_QUOTE", "message": str(exc)}},
        )

    @app.exception_handler(DomainException)
    async def domain_error_handler(request: Request, exc: DomainException) -> JSONResponse:
        """Translate domain errors to standard API error envelope."""
        status_map = {
            "TENANT_NOT_FOUND": 404,
            "ONTOLOGY_VIOLATION": 422,
            "RESOLUTION_CONFLICT": 409,
            "GRAPH_INGESTION_ERROR": 500,
            "DOCUMENT_NOT_FOUND": 404,
            "FACT_NOT_FOUND": 404,
        }
        return JSONResponse(
            status_code=status_map.get(exc.code, 500),
            content={"error": {"code": exc.code, "message": exc.message}},
        )

    @app.exception_handler(Exception)
    async def generic_error_handler(request: Request, exc: Exception) -> JSONResponse:
        """Never expose stack traces to clients (security-review skill)."""
        logger.exception("Unexpected error", exc_info=exc)
        return JSONResponse(
            status_code=500,
            content={
                "error": {"code": "INTERNAL_ERROR", "message": "An unexpected error occurred"}
            },
        )

    # --- Include Routers ---
    from semanticgraph.adapters.inbound.api.v1.documents import router as documents_router
    from semanticgraph.adapters.inbound.api.v1.facts import router as facts_router

    app.include_router(documents_router)
    app.include_router(facts_router)

    @app.get("/health")
    def health_check() -> dict[str, str]:
        return {"status": "healthy"}

    return app


app = create_app()
