"""
Analysis API Router

Endpoints:
- POST /analyze - Submit analytical query
- GET /schema - Get database schema
"""

from typing import Any, Dict

import asyncpg
import structlog
from fastapi import APIRouter, Depends, HTTPException, status

from app.core.cache import CacheManager, get_cache_manager
from app.core.config import get_settings
from app.core.evaluator import QueryEvaluator, create_evaluator
from app.core.executor.postgres_executor import PostgresExecutor, create_connection_pool
from app.core.llm_pipeline import LLMPipeline, create_llm_pipeline
from app.core.schema_manager import SchemaManager
from app.models.schemas import (
    AnalyzeRequest,
    ErrorResponse,
    InsightResponse,
    SchemaResponse,
)

logger = structlog.get_logger(__name__)
settings = get_settings()

router = APIRouter(prefix="/api/v1", tags=["analysis"])

# Global state (initialized on startup)
_db_pool: asyncpg.Pool | None = None
_cache_manager: CacheManager | None = None
_llm_pipeline: LLMPipeline | None = None
_evaluator: QueryEvaluator | None = None


async def get_db_pool() -> asyncpg.Pool:
    """
    Get database connection pool dependency.

    Returns:
        asyncpg.Pool: Database connection pool

    Raises:
        HTTPException: If pool not initialized
    """
    if _db_pool is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not initialized",
        )
    return _db_pool


async def get_executor(pool: asyncpg.Pool = Depends(get_db_pool)) -> PostgresExecutor:
    """
    Get PostgreSQL executor dependency.

    Args:
        pool: Database connection pool

    Returns:
        PostgresExecutor: Configured executor instance
    """
    return PostgresExecutor(pool)


async def get_schema_manager(
    cache: CacheManager = Depends(get_cache_manager),
) -> SchemaManager:
    """
    Get schema manager dependency.

    Args:
        cache: Cache manager instance

    Returns:
        SchemaManager: Configured schema manager
    """
    return SchemaManager(cache)


async def get_llm_pipeline_dep() -> LLMPipeline:
    """
    Get LLM pipeline dependency.

    Returns:
        LLMPipeline: Initialized pipeline

    Raises:
        HTTPException: If pipeline not initialized
    """
    if _llm_pipeline is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LLM pipeline not initialized",
        )
    return _llm_pipeline


async def get_evaluator_dep() -> QueryEvaluator:
    """
    Get query evaluator dependency.

    Returns:
        QueryEvaluator: Initialized evaluator

    Raises:
        HTTPException: If evaluator not initialized
    """
    if _evaluator is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Query evaluator not initialized",
        )
    return _evaluator


@router.post(
    "/analyze",
    response_model=InsightResponse,
    responses={
        400: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    },
    summary="Analyze data with natural language query",
    description="""
    Submit a natural language analytical query and receive insights with data.

    The system will:
    1. Generate SQL from your request
    2. Validate and execute the query
    3. Evaluate results for correctness
    4. Generate human-readable insights
    5. Suggest visualizations

    Example request:
    ```json
    {
        "request": "Show total revenue per month for the last year",
        "include_raw_data": true
    }
    ```
    """,
)
async def analyze_data(
    request: AnalyzeRequest,
    executor: PostgresExecutor = Depends(get_executor),
    schema_manager: SchemaManager = Depends(get_schema_manager),
    llm_pipeline: LLMPipeline = Depends(get_llm_pipeline_dep),
    evaluator: QueryEvaluator = Depends(get_evaluator_dep),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> InsightResponse:
    """
    Main analysis endpoint.

    Orchestrates the complete analytical workflow:
    1. Fetch schema
    2. Generate SQL
    3. Execute query
    4. Evaluate and regenerate if needed
    5. Generate insights

    Args:
        request: Analysis request
        executor: PostgreSQL executor
        schema_manager: Schema manager
        llm_pipeline: LLM pipeline
        evaluator: Query evaluator
        pool: Database connection pool

    Returns:
        InsightResponse: Analysis results with insights

    Raises:
        HTTPException: On various error conditions
    """
    logger.info("Received analysis request", request=request.request[:100])

    try:
        # Step 1: Fetch schema
        async with pool.acquire() as conn:
            schema_summary = await schema_manager.get_schema_summary(
                conn=conn,
                force_refresh=request.force_refresh_schema,
            )

        # Step 2: Generate SQL
        logger.info("Generating SQL from request")
        sql_result = await llm_pipeline.generate_sql(
            user_request=request.request,
            schema_summary=schema_summary,
            context=request.context,
        )

        # Step 3: Execute SQL
        logger.info("Executing generated SQL")
        execution_result = await executor.execute_read_only(sql_result["sql"])

        # Step 4: Evaluate and regenerate if needed
        logger.info("Evaluating query results")
        final_result = await evaluator.evaluate_and_regenerate(
            user_request=request.request,
            schema_summary=schema_summary,
            initial_sql=sql_result["sql"],
            initial_results=execution_result,
            context=request.context,
        )

        # Step 5: Generate insights
        logger.info("Generating insights from results")
        insight_result = await llm_pipeline.generate_insight(
            user_request=request.request,
            results=final_result["results"],
            summary=final_result["results"].get("summary", {}),
        )

        # Build response
        response = InsightResponse(
            insight=insight_result["insight"],
            key_findings=insight_result.get("key_findings", []),
            data=final_result["results"]["rows"] if request.include_raw_data else None,
            visualization_type=insight_result.get("visualization_type"),
            narrative=insight_result.get("narrative"),
            sql=final_result["sql"],
            execution_time_ms=final_result["results"]["execution_time_ms"],
            row_count=final_result["results"]["row_count"],
            evaluation=final_result["evaluation"],
            attempts=final_result["attempts"],
        )

        logger.info("Analysis completed successfully", attempts=final_result["attempts"])
        return response

    except Exception as e:
        logger.error("Analysis failed", error=str(e), error_type=type(e).__name__)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": str(e),
                "error_type": type(e).__name__,
            },
        )


@router.get(
    "/schema",
    response_model=SchemaResponse,
    responses={
        500: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    },
    summary="Get database schema",
    description="""
    Retrieve the database schema summary.

    Returns metadata about all tables, columns, and sample data.
    Results are cached for performance.
    """,
)
async def get_schema(
    force_refresh: bool = False,
    schema_manager: SchemaManager = Depends(get_schema_manager),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> SchemaResponse:
    """
    Get database schema endpoint.

    Args:
        force_refresh: Force refresh of schema cache
        schema_manager: Schema manager
        pool: Database connection pool

    Returns:
        SchemaResponse: Database schema summary

    Raises:
        HTTPException: If schema fetch fails
    """
    logger.info("Fetching database schema", force_refresh=force_refresh)

    try:
        async with pool.acquire() as conn:
            schema_summary = await schema_manager.get_schema_summary(
                conn=conn,
                force_refresh=force_refresh,
            )

        response = SchemaResponse(
            tables=schema_summary["tables"],
            total_tables=len(schema_summary["tables"]),
            database_name=schema_summary.get("database_name", "unknown"),
            cached=not force_refresh,
        )

        logger.info("Schema fetched successfully", table_count=response.total_tables)
        return response

    except Exception as e:
        logger.error("Schema fetch failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": str(e),
                "error_type": type(e).__name__,
            },
        )


# Startup and shutdown handlers (called from main.py)


async def initialize_router() -> None:
    """
    Initialize router dependencies on application startup.

    Creates:
    - Database connection pool
    - Cache manager
    - LLM pipeline
    - Query evaluator
    """
    global _db_pool, _cache_manager, _llm_pipeline, _evaluator

    logger.info("Initializing router dependencies")

    try:
        # Initialize database pool
        _db_pool = await create_connection_pool(
            str(settings.database_url),
            min_size=settings.database_pool_size,
            max_size=settings.database_pool_size + settings.database_max_overflow,
        )

        # Initialize cache manager
        _cache_manager = await get_cache_manager()

        # Initialize LLM pipeline
        _llm_pipeline = await create_llm_pipeline()

        # Initialize evaluator
        _evaluator = await create_evaluator(_llm_pipeline)

        logger.info("Router dependencies initialized successfully")

    except Exception as e:
        logger.error("Failed to initialize router dependencies", error=str(e))
        raise


async def shutdown_router() -> None:
    """
    Cleanup router dependencies on application shutdown.

    Closes:
    - Database connection pool
    - Cache connections
    """
    global _db_pool, _cache_manager

    logger.info("Shutting down router dependencies")

    if _db_pool:
        await _db_pool.close()
        logger.info("Database pool closed")

    if _cache_manager:
        await _cache_manager.disconnect()
        logger.info("Cache manager disconnected")
