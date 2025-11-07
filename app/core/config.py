"""
Application configuration management using Pydantic Settings.
Loads configuration from environment variables and .env file.
"""

from functools import lru_cache
from typing import List

from pydantic import Field, PostgresDsn, RedisDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with validation and type safety."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Database Configuration
    database_url: PostgresDsn = Field(
        ...,
        description="PostgreSQL connection URL",
    )
    database_pool_size: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Database connection pool size",
    )
    database_max_overflow: int = Field(
        default=20,
        ge=0,
        le=100,
        description="Maximum overflow connections",
    )

    # Redis Configuration
    redis_url: RedisDsn = Field(
        ...,
        description="Redis connection URL",
    )
    redis_cache_ttl: int = Field(
        default=3600,
        ge=60,
        description="Redis cache TTL in seconds",
    )

    # Groq API Configuration
    groq_api_key: str = Field(
        ...,
        description="Groq API key for LLM access",
    )
    groq_model_name: str = Field(
        default="mixtral-8x7b-32768",
        description="Groq model identifier",
    )
    groq_temperature: float = Field(
        default=0.1,
        ge=0.0,
        le=2.0,
        description="LLM temperature for generation",
    )
    groq_max_tokens: int = Field(
        default=2048,
        ge=100,
        le=32768,
        description="Maximum tokens for LLM response",
    )

    # LLM Pipeline Configuration
    max_retry_attempts: int = Field(
        default=2,
        ge=0,
        le=5,
        description="Maximum retry attempts for LLM generation",
    )
    sql_generation_timeout: int = Field(
        default=30,
        ge=5,
        le=120,
        description="SQL generation timeout in seconds",
    )
    evaluation_timeout: int = Field(
        default=15,
        ge=5,
        le=60,
        description="Evaluation timeout in seconds",
    )

    # Security Configuration
    read_only_mode: bool = Field(
        default=True,
        description="Enforce read-only SQL execution",
    )
    allowed_sql_commands: List[str] = Field(
        default=["SELECT", "WITH", "EXPLAIN"],
        description="Whitelist of allowed SQL commands",
    )

    # Logging Configuration
    log_level: str = Field(
        default="INFO",
        description="Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)",
    )
    log_format: str = Field(
        default="json",
        description="Log output format (json or text)",
    )

    # API Configuration
    api_v1_prefix: str = Field(
        default="/api/v1",
        description="API v1 route prefix",
    )
    api_title: str = Field(
        default="LLM Analytical Intelligence API",
        description="API title",
    )
    api_version: str = Field(
        default="0.1.0",
        description="API version",
    )

    # Performance Configuration
    schema_cache_enabled: bool = Field(
        default=True,
        description="Enable schema caching in Redis",
    )
    schema_cache_ttl: int = Field(
        default=86400,
        ge=3600,
        description="Schema cache TTL in seconds (default: 24 hours)",
    )
    sample_rows_limit: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Number of sample rows to fetch per table",
    )

    # Environment
    environment: str = Field(
        default="development",
        description="Deployment environment (development, staging, production)",
    )

    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.environment.lower() == "production"

    @property
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.environment.lower() == "development"


@lru_cache
def get_settings() -> Settings:
    """
    Get cached application settings.
    Uses lru_cache to ensure settings are loaded only once.

    Returns:
        Settings: Application settings instance
    """
    return Settings()  # type: ignore[call-arg]
