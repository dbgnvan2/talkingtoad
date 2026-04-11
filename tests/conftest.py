"""
Shared pytest fixtures for TalkingToad test suite.
"""

import os

import pytest
from httpx import ASGITransport, AsyncClient

# Disable rate limiting and set a known auth token for all tests
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")
os.environ.setdefault("AUTH_TOKEN", "test-token")


@pytest.fixture
async def store():
    """Standalone in-memory SQLiteJobStore — used by test_job_store.py directly."""
    from api.services.job_store import SQLiteJobStore

    async with SQLiteJobStore(db_path=":memory:") as s:
        yield s


@pytest.fixture
async def test_store():
    """In-memory store injected into the FastAPI app for API integration tests."""
    from api.services.job_store import SQLiteJobStore

    async with SQLiteJobStore(db_path=":memory:") as s:
        yield s


@pytest.fixture
async def api_client(test_store):
    """Async HTTP test client wired to the FastAPI app with an isolated in-memory store."""
    from api.main import app
    from api.routers.crawl import get_store

    app.dependency_overrides[get_store] = lambda: test_store

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client

    app.dependency_overrides.clear()


@pytest.fixture
def auth_headers() -> dict:
    """Authorization header using the test token."""
    return {"Authorization": "Bearer test-token"}
