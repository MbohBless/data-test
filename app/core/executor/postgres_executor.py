"""
PostgreSQL Executor Module

Safely executes SQL queries against PostgreSQL database.
Enforces read-only operations and security constraints.

MCP-Ready Interface:
- Compatible with MCP Executor pattern
- Supports async execution
- Provides structured result format
"""

import re
from typing import Any, Dict, List, Optional

import asyncpg
import pandas as pd
import structlog

from app.core.config import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()


class SQLValidationError(Exception):
    """Raised when SQL query fails validation checks."""

    pass


class PostgresExecutor:
    """
    Executes SQL queries against PostgreSQL with safety constraints.

    Security Features:
    - Read-only mode enforcement
    - SQL injection prevention
    - Command whitelist validation
    - Query timeout enforcement
    - Connection pooling
    """

    def __init__(self, connection_pool: asyncpg.Pool) -> None:
        """
        Initialize PostgresExecutor with connection pool.

        Args:
            connection_pool: asyncpg connection pool
        """
        self.pool = connection_pool
        self._allowed_commands = set(
            cmd.upper() for cmd in settings.allowed_sql_commands
        )

    async def execute_read_only(
        self,
        sql: str,
        timeout: int = 30,
    ) -> Dict[str, Any]:
        """
        Execute a read-only SQL query and return structured results.

        This is the primary execution method for LLM-generated queries.

        Args:
            sql: SQL query to execute
            timeout: Query timeout in seconds

        Returns:
            Dict containing:
                - rows: List of result rows as dicts
                - row_count: Number of rows returned
                - columns: List of column names
                - summary: Statistical summary of results
                - execution_time: Query execution time in ms

        Raises:
            SQLValidationError: If query fails validation
            asyncpg.PostgresError: If query execution fails

        MCP-Compatible: Returns format expected by MCP executor interface
        """
        logger.info("Executing SQL query", sql_preview=sql[:100])

        # Validate query before execution
        self._validate_sql(sql)

        async with self.pool.acquire() as conn:
            try:
                # Set read-only transaction
                if settings.read_only_mode:
                    await conn.execute("SET TRANSACTION READ ONLY")

                # Execute with timeout
                start_time = pd.Timestamp.now()
                rows = await conn.fetch(sql, timeout=timeout)
                execution_time = (pd.Timestamp.now() - start_time).total_seconds() * 1000

                # Convert to list of dicts
                results = [dict(row) for row in rows]

                # Generate summary
                summary = await self.get_summary(results) if results else {}

                logger.info(
                    "Query executed successfully",
                    row_count=len(results),
                    execution_time_ms=execution_time,
                )

                return {
                    "rows": results,
                    "row_count": len(results),
                    "columns": list(rows[0].keys()) if rows else [],
                    "summary": summary,
                    "execution_time_ms": execution_time,
                }

            except asyncpg.QueryCanceledError:
                logger.error("Query timeout exceeded", timeout=timeout)
                raise
            except asyncpg.PostgresError as e:
                logger.error("Query execution failed", error=str(e))
                raise

    async def execute_explain(
        self,
        sql: str,
    ) -> Dict[str, Any]:
        """
        Execute EXPLAIN on a query to get execution plan.

        Useful for query optimization and verification.

        Args:
            sql: SQL query to explain

        Returns:
            Dict containing execution plan details
        """
        logger.info("Executing EXPLAIN", sql_preview=sql[:100])

        explain_query = f"EXPLAIN (FORMAT JSON, ANALYZE FALSE) {sql}"

        async with self.pool.acquire() as conn:
            result = await conn.fetchval(explain_query)
            return {"plan": result}

    async def get_summary(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Generate statistical summary of query results.

        Provides context for LLM evaluation and insight generation.

        Args:
            results: List of result rows as dicts

        Returns:
            Dict containing:
                - numeric_columns: Stats for numeric columns (mean, max, min, etc.)
                - categorical_columns: Unique counts for text columns
                - null_counts: NULL value counts per column
                - total_rows: Total row count

        MCP-Compatible: Structured format for result summarization
        """
        if not results:
            return {}

        try:
            df = pd.DataFrame(results)

            summary: Dict[str, Any] = {
                "total_rows": len(df),
                "columns": list(df.columns),
                "numeric_columns": {},
                "categorical_columns": {},
                "null_counts": {},
            }

            # Numeric column statistics
            numeric_cols = df.select_dtypes(include=["number"]).columns
            for col in numeric_cols:
                summary["numeric_columns"][col] = {
                    "mean": float(df[col].mean()),
                    "median": float(df[col].median()),
                    "min": float(df[col].min()),
                    "max": float(df[col].max()),
                    "std": float(df[col].std()),
                }

            # Categorical column statistics
            categorical_cols = df.select_dtypes(include=["object", "string"]).columns
            for col in categorical_cols:
                summary["categorical_columns"][col] = {
                    "unique_count": int(df[col].nunique()),
                    "most_common": str(df[col].mode()[0]) if not df[col].mode().empty else None,
                }

            # NULL counts
            summary["null_counts"] = {
                col: int(count) for col, count in df.isnull().sum().items() if count > 0
            }

            return summary

        except Exception as e:
            logger.error("Failed to generate summary", error=str(e))
            return {"error": str(e)}

    async def test_connection(self) -> bool:
        """
        Test database connection.

        Returns:
            True if connection successful
        """
        try:
            async with self.pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            logger.info("Database connection test successful")
            return True
        except Exception as e:
            logger.error("Database connection test failed", error=str(e))
            return False

    # Validation methods

    def _validate_sql(self, sql: str) -> None:
        """
        Validate SQL query for safety and compliance.

        Checks:
        - Only allowed commands (SELECT, WITH, EXPLAIN)
        - No destructive operations (DROP, DELETE, TRUNCATE, etc.)
        - No privilege escalation attempts
        - Basic SQL injection patterns

        Args:
            sql: SQL query to validate

        Raises:
            SQLValidationError: If validation fails
        """
        sql_upper = sql.strip().upper()

        # Check if query starts with allowed command
        if not any(sql_upper.startswith(cmd) for cmd in self._allowed_commands):
            raise SQLValidationError(
                f"Query must start with one of: {', '.join(self._allowed_commands)}"
            )

        # Check for dangerous commands
        dangerous_patterns = [
            r"\bDROP\b",
            r"\bDELETE\b",
            r"\bTRUNCATE\b",
            r"\bINSERT\b",
            r"\bUPDATE\b",
            r"\bALTER\b",
            r"\bCREATE\b",
            r"\bGRANT\b",
            r"\bREVOKE\b",
            r"\bEXECUTE\b",
            r"\bCALL\b",
        ]

        for pattern in dangerous_patterns:
            if re.search(pattern, sql_upper):
                raise SQLValidationError(
                    f"Forbidden SQL command detected: {pattern}"
                )

        # Check for common SQL injection patterns
        injection_patterns = [
            r";\s*DROP",
            r";\s*DELETE",
            r"--\s*$",
            r"/\*.*\*/",
        ]

        for pattern in injection_patterns:
            if re.search(pattern, sql, re.IGNORECASE):
                logger.warning("Potential SQL injection pattern detected", pattern=pattern)
                raise SQLValidationError(
                    "Query contains suspicious patterns"
                )

        logger.debug("SQL validation passed")

    def _sanitize_table_name(self, table_name: str) -> str:
        """
        Sanitize table name to prevent SQL injection.

        Args:
            table_name: Raw table name

        Returns:
            Sanitized table name

        Raises:
            SQLValidationError: If table name is invalid
        """
        # Allow only alphanumeric, underscore, and dot (for schema.table)
        if not re.match(r"^[a-zA-Z0-9_\.]+$", table_name):
            raise SQLValidationError(
                f"Invalid table name: {table_name}"
            )
        return table_name


async def create_connection_pool(
    database_url: str,
    min_size: int = 5,
    max_size: int = 20,
) -> asyncpg.Pool:
    """
    Create asyncpg connection pool.

    Args:
        database_url: PostgreSQL connection URL
        min_size: Minimum pool size
        max_size: Maximum pool size

    Returns:
        asyncpg.Pool: Connection pool instance

    Usage:
        pool = await create_connection_pool(settings.database_url)
        executor = PostgresExecutor(pool)
    """
    logger.info("Creating database connection pool", min_size=min_size, max_size=max_size)

    try:
        pool = await asyncpg.create_pool(
            database_url,
            min_size=min_size,
            max_size=max_size,
            command_timeout=60,
        )
        logger.info("Connection pool created successfully")
        return pool
    except Exception as e:
        logger.error("Failed to create connection pool", error=str(e))
        raise
