"""Shared API test fixtures."""

from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient

from cloudwise.main import app


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    """Provide an in-process async API client."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as test_client:
        yield test_client
