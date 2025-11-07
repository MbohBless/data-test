"""
Pytest Configuration and Fixtures

Shared fixtures for all tests.
"""

import asyncio
from typing import AsyncGenerator, Generator

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """
    Create event loop for async tests.

    Yields:
        Event loop instance
    """
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def client() -> TestClient:
    """
    Create FastAPI test client.

    Returns:
        TestClient: Test client for API requests
    """
    return TestClient(app)


@pytest_asyncio.fixture
async def async_client() -> AsyncGenerator[TestClient, None]:
    """
    Create async FastAPI test client.

    Yields:
        TestClient: Async test client
    """
    # TODO: Implement async test client with proper lifecycle
    # For now, use sync client
    yield TestClient(app)


# Mock fixtures for dependencies


@pytest.fixture
def mock_database_url() -> str:
    """
    Mock database URL for testing.

    Returns:
        str: Test database URL
    """
    return "postgresql://test:test@localhost:5432/test"


@pytest.fixture
def mock_redis_url() -> str:
    """
    Mock Redis URL for testing.

    Returns:
        str: Test Redis URL
    """
    return "redis://localhost:6379/1"


@pytest.fixture
def mock_groq_api_key() -> str:
    """
    Mock Groq API key for testing.

    Returns:
        str: Test API key
    """
    return "test-api-key"


# Sample data fixtures


@pytest.fixture
def sample_schema() -> dict:
    """
    Sample database schema for testing.

    Returns:
        dict: Schema summary
    """
    return {
        "tables": [
            {
                "name": "orders",
                "columns": [
                    {"name": "id", "type": "integer"},
                    {"name": "amount", "type": "numeric"},
                    {"name": "date", "type": "timestamp"},
                ],
                "row_count": 100,
            }
        ],
        "total_tables": 1,
        "database_name": "test_db",
    }


@pytest.fixture
def sample_analyze_request() -> dict:
    """
    Sample analysis request for testing.

    Returns:
        dict: Request payload
    """
    return {
        "request": "Show total revenue per month",
        "include_raw_data": True,
    }


@pytest.fixture
def sample_sql_result() -> dict:
    """
    Sample SQL generation result for testing.

    Returns:
        dict: SQL result
    """
    return {
        "sql": "SELECT date_trunc('month', date) AS month, SUM(amount) AS revenue FROM orders GROUP BY 1",
        "plan": ["Aggregate monthly revenue from orders table"],
        "reasoning": "Using date_trunc to group by month",
        "confidence": 0.95,
    }
