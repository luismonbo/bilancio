"""Unit tests for GET /health — no DB required."""

from httpx import AsyncClient


async def test_health_returns_ok(client: AsyncClient) -> None:
    response = await client.get("/health")
    assert response.status_code == 200


async def test_health_response_shape(client: AsyncClient) -> None:
    response = await client.get("/health")
    data = response.json()
    assert data["status"] == "ok"
    assert "version" in data
    assert isinstance(data["version"], str)


async def test_health_no_auth_required(client: AsyncClient) -> None:
    """Health check must be reachable without a Bearer token."""
    response = await client.get("/health")
    assert response.status_code == 200
