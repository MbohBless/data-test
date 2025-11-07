"""
Pydantic Models for API Request/Response Schemas

Defines all data models for:
- API requests (user queries)
- API responses (insights, data)
- Internal data structures
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


# Request Models


class AnalyzeRequest(BaseModel):
    """
    Request model for analysis endpoint.

    User submits a natural language query for analysis.
    """

    request: str = Field(
        ...,
        min_length=5,
        max_length=500,
        description="Natural language analytical request",
        examples=["Show total revenue per month"],
    )

    context: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Optional additional context for the query",
    )

    force_refresh_schema: bool = Field(
        default=False,
        description="Force refresh of database schema cache",
    )

    include_raw_data: bool = Field(
        default=True,
        description="Include raw query results in response",
    )

    @field_validator("request")
    @classmethod
    def validate_request(cls, v: str) -> str:
        """Validate that request is not empty or just whitespace."""
        if not v.strip():
            raise ValueError("Request cannot be empty or whitespace")
        return v.strip()


# Response Models


class InsightResponse(BaseModel):
    """
    Response model for analysis endpoint.

    Contains generated insights, data, and metadata.
    """

    insight: str = Field(
        ...,
        description="Natural language summary of findings",
    )

    key_findings: List[str] = Field(
        default_factory=list,
        description="List of key findings from analysis",
    )

    data: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        description="Raw query results (if include_raw_data=True)",
    )

    visualization_type: Optional[str] = Field(
        default=None,
        description="Suggested visualization type",
        examples=["line_chart", "bar_chart", "pie_chart", "table"],
    )

    narrative: Optional[str] = Field(
        default=None,
        description="Detailed narrative explanation",
    )

    sql: str = Field(
        ...,
        description="Generated SQL query",
    )

    execution_time_ms: float = Field(
        ...,
        description="Query execution time in milliseconds",
    )

    row_count: int = Field(
        ...,
        description="Number of rows returned",
    )

    evaluation: Dict[str, Any] = Field(
        ...,
        description="Evaluation result from LLM",
    )

    attempts: int = Field(
        default=1,
        ge=1,
        description="Number of generation attempts",
    )

    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="Timestamp of analysis",
    )


class SchemaResponse(BaseModel):
    """
    Response model for schema endpoint.

    Returns database schema summary.
    """

    tables: List[Dict[str, Any]] = Field(
        ...,
        description="List of table metadata",
    )

    total_tables: int = Field(
        ...,
        description="Total number of tables",
    )

    database_name: str = Field(
        ...,
        description="Name of the database",
    )

    fetched_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="When schema was fetched",
    )

    cached: bool = Field(
        default=False,
        description="Whether schema was loaded from cache",
    )


class ErrorResponse(BaseModel):
    """
    Error response model.

    Returned when request fails.
    """

    error: str = Field(
        ...,
        description="Error message",
    )

    error_type: str = Field(
        ...,
        description="Type of error (validation, execution, timeout, etc.)",
    )

    details: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Additional error details",
    )

    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="When error occurred",
    )


# Internal Models


class SQLGenerationResult(BaseModel):
    """
    Result of SQL generation step.

    Used internally in pipeline.
    """

    sql: str = Field(
        ...,
        description="Generated SQL query",
    )

    plan: List[str] = Field(
        default_factory=list,
        description="Step-by-step analysis plan",
    )

    reasoning: str = Field(
        ...,
        description="LLM reasoning for query structure",
    )

    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence score",
    )


class SQLVerificationResult(BaseModel):
    """
    Result of SQL verification step.

    Used internally in pipeline.
    """

    is_valid: bool = Field(
        ...,
        description="Whether SQL is valid",
    )

    issues: List[str] = Field(
        default_factory=list,
        description="List of identified issues",
    )

    reasoning: str = Field(
        ...,
        description="Verification reasoning",
    )

    suggested_fix: Optional[str] = Field(
        default=None,
        description="Suggested SQL correction (if issues found)",
    )


class ExecutionResult(BaseModel):
    """
    Result of SQL execution.

    Used internally in executor.
    """

    rows: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Query result rows",
    )

    row_count: int = Field(
        ...,
        ge=0,
        description="Number of rows returned",
    )

    columns: List[str] = Field(
        default_factory=list,
        description="Column names",
    )

    summary: Dict[str, Any] = Field(
        default_factory=dict,
        description="Statistical summary",
    )

    execution_time_ms: float = Field(
        ...,
        description="Execution time in milliseconds",
    )


class EvaluationResult(BaseModel):
    """
    Result of query evaluation.

    Used internally in evaluator.
    """

    is_correct: bool = Field(
        ...,
        description="Whether query correctly answers request",
    )

    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence score",
    )

    reasoning: str = Field(
        ...,
        description="Evaluation reasoning",
    )

    needs_regeneration: bool = Field(
        ...,
        description="Whether SQL should be regenerated",
    )

    issues: List[str] = Field(
        default_factory=list,
        description="Identified issues",
    )


class HealthResponse(BaseModel):
    """
    Health check response.

    Used for monitoring and readiness checks.
    """

    status: str = Field(
        ...,
        description="Health status (healthy, degraded, unhealthy)",
    )

    version: str = Field(
        ...,
        description="API version",
    )

    database: bool = Field(
        ...,
        description="Database connection status",
    )

    cache: bool = Field(
        ...,
        description="Cache connection status",
    )

    llm: bool = Field(
        ...,
        description="LLM service status",
    )

    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="Health check timestamp",
    )
