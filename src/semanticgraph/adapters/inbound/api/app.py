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

logger = logging.getLogger("semanticgraph")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Wire adapters at startup. Swap fakes for real adapters per phase."""
    # Phase 1: In-memory fakes (will be replaced with real Neo4j/LLM/Celery adapters)
    from tests.unit.use_cases.test_ingest_document import (
        FakeGraphRepository,
        FakeLLMGateway,
        FakeTaskPublisher,
    )

    from semanticgraph.composition.container import (
        set_graph_repo,
        set_llm_gateway,
        set_task_publisher,
    )

    set_graph_repo(FakeGraphRepository())
    set_llm_gateway(FakeLLMGateway())
    set_task_publisher(FakeTaskPublisher())

    logger.info("SemanticGraph Cloud started (in-memory adapters)")
    yield
    logger.info("SemanticGraph Cloud shutting down")


def create_app() -> FastAPI:
    app = FastAPI(
        title="SemanticGraph Cloud API",
        description="Multi-tenant Managed GraphRAG Platform",
        version="0.1.0",
        lifespan=lifespan,
    )

    # --- Global Exception Handlers (error-handling skill) ---

    @app.exception_handler(DomainException)
    async def domain_error_handler(request: Request, exc: DomainException) -> JSONResponse:
        """Translate domain errors to standard API error envelope."""
        status_map = {
            "TENANT_NOT_FOUND": 404,
            "ONTOLOGY_VIOLATION": 422,
            "RESOLUTION_CONFLICT": 409,
            "GRAPH_INGESTION_ERROR": 500,
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

    app.include_router(documents_router)

    @app.get("/health")
    def health_check() -> dict[str, str]:
        return {"status": "healthy"}

    return app


app = create_app()
