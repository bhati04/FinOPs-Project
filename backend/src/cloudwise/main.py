"""FastAPI application factory."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from cloudwise.api.router import api_router
from cloudwise.core.config import get_settings
from cloudwise.core.database import dispose_engine
from cloudwise.core.logging import configure_logging
from cloudwise.core.middleware import CorrelationIdMiddleware, RequestSizeLimitMiddleware
from cloudwise.core.redis import close_redis


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Initialize process-level resources and close clients on shutdown."""
    settings = get_settings()
    configure_logging(settings.log_level)
    logger = structlog.get_logger(__name__)
    logger.info("application_started", environment=settings.environment)
    yield
    await close_redis()
    await dispose_engine()
    logger.info("application_stopped")


def create_app() -> FastAPI:
    """Build the application without opening external connections."""
    settings = get_settings()
    app = FastAPI(
        title="CloudWise FinOps API",
        summary="Secure multi-account AWS cost and governance API",
        version="0.1.0",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(origin).rstrip("/") for origin in settings.cors_origins],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "Idempotency-Key", "X-CSRF-Token"],
        expose_headers=["X-Correlation-ID"],
    )
    app.add_middleware(RequestSizeLimitMiddleware, max_bytes=settings.api_request_max_bytes)
    app.add_middleware(CorrelationIdMiddleware)
    app.include_router(api_router, prefix="/api/v1")
    return app


app = create_app()
