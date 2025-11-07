"""
FastAPI Main Application

LLM-powered Analytical Intelligence API

Entrypoint for the application with:
- FastAPI app initialization
- Middleware configuration
- Router registration
- Startup/shutdown lifecycle
- Logging setup
"""

import sys
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.analyze import initialize_router, router, shutdown_router
from app.core.config import get_settings
from app.models.schemas import ErrorResponse, HealthResponse

# Initialize settings
settings = get_settings()

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
        if settings.log_format == "json"
        else structlog.dev.ConsoleRenderer(),
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan manager.

    Handles:
    - Startup: Initialize database, cache, LLM pipeline
    - Shutdown: Cleanup connections and resources

    Args:
        app: FastAPI application instance

    Yields:
        None
    """
    # Startup
    logger.info(
        "Starting application",
        version=settings.api_version,
        environment=settings.environment,
    )

    try:
        # Initialize router dependencies (DB, cache, LLM)
        await initialize_router()
        logger.info("Application startup complete")

    except Exception as e:
        logger.error("Application startup failed", error=str(e))
        sys.exit(1)

    yield

    # Shutdown
    logger.info("Shutting down application")
    try:
        await shutdown_router()
        logger.info("Application shutdown complete")
    except Exception as e:
        logger.error("Error during shutdown", error=str(e))


# Create FastAPI application
app = FastAPI(
    title=settings.api_title,
    version=settings.api_version,
    description="""
    LLM-powered Analytical Intelligence API

    Automatically analyze structured data using natural language queries.
    The system generates SQL, executes queries, and provides human-readable insights.

    ## Features

    - Natural language to SQL generation
    - Automatic query verification
    - Self-evaluation and regeneration
    - Statistical analysis and insights
    - Visualization recommendations

    ## Workflow

    1. Submit natural language query
    2. System generates optimized SQL
    3. Query executes safely (read-only)
    4. Results evaluated for correctness
    5. Insights generated with visualizations

    ## MCP-Ready Architecture

    All components designed for future Model Context Protocol integration.
    """,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.is_development else [],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add GZip compression middleware
app.add_middleware(GZipMiddleware, minimum_size=1000)


# Exception handlers


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    """
    Handle request validation errors.

    Args:
        request: FastAPI request
        exc: Validation exception

    Returns:
        JSONResponse: Error response
    """
    logger.warning(
        "Request validation failed",
        path=request.url.path,
        errors=exc.errors(),
    )

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": "Request validation failed",
            "error_type": "ValidationError",
            "details": exc.errors(),
        },
    )


@app.exception_handler(Exception)
async def general_exception_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    """
    Handle unexpected exceptions.

    Args:
        request: FastAPI request
        exc: Exception

    Returns:
        JSONResponse: Error response
    """
    logger.error(
        "Unhandled exception",
        path=request.url.path,
        error=str(exc),
        error_type=type(exc).__name__,
    )

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "Internal server error",
            "error_type": type(exc).__name__,
            "details": str(exc) if settings.is_development else None,
        },
    )


# Middleware


@app.middleware("http")
async def log_requests(request: Request, call_next):  # type: ignore[no-untyped-def]
    """
    Log all HTTP requests.

    Args:
        request: FastAPI request
        call_next: Next middleware/handler

    Returns:
        Response
    """
    logger.info(
        "Request received",
        method=request.method,
        path=request.url.path,
        client=request.client.host if request.client else None,
    )

    response = await call_next(request)

    logger.info(
        "Request completed",
        method=request.method,
        path=request.url.path,
        status_code=response.status_code,
    )

    return response


# Health check endpoints


@app.get(
    "/health",
    response_model=HealthResponse,
    tags=["health"],
    summary="Health check",
    description="Check API health and dependency status",
)
async def health_check() -> HealthResponse:
    """
    Health check endpoint.

    Verifies:
    - API is running
    - Database connection
    - Cache connection
    - LLM service availability

    Returns:
        HealthResponse: Health status
    """
    # TODO: Implement actual health checks for dependencies
    # For now, return basic health status

    return HealthResponse(
        status="healthy",
        version=settings.api_version,
        database=True,  # TODO: Check actual DB connection
        cache=True,  # TODO: Check actual cache connection
        llm=True,  # TODO: Check actual LLM availability
    )


@app.get(
    "/",
    tags=["root"],
    summary="Root endpoint",
    description="API information and welcome message",
)
async def root() -> dict[str, str]:
    """
    Root endpoint.

    Returns:
        dict: API information
    """
    return {
        "name": settings.api_title,
        "version": settings.api_version,
        "status": "running",
        "docs": "/docs",
        "health": "/health",
    }


# Register routers
app.include_router(router)

# Log application info
logger.info(
    "FastAPI application created",
    title=settings.api_title,
    version=settings.api_version,
    environment=settings.environment,
)
