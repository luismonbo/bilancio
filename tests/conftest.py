"""Top-level fixtures shared across unit and integration tests."""

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture
async def client() -> AsyncClient:  # type: ignore[misc]
    """HTTP client wired to the FastAPI app. No DB override — unit tests only."""
    from bilancio.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c
