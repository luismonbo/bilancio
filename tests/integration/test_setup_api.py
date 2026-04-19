"""Integration tests for POST /setup."""

from httpx import AsyncClient


async def test_setup_missing_email_returns_422(auth_client: AsyncClient) -> None:
    response = await auth_client.post("/setup", json={"display_name": "Alice"})
    assert response.status_code == 422


async def test_setup_missing_display_name_returns_422(auth_client: AsyncClient) -> None:
    response = await auth_client.post("/setup", json={"email": "alice@example.com"})
    assert response.status_code == 422


async def test_setup_when_users_exist_returns_409(auth_client: AsyncClient) -> None:
    """Our session-scoped DB already has users from other tests → 409."""
    response = await auth_client.post(
        "/setup",
        json={"email": "new@example.com", "display_name": "New User"},
    )
    assert response.status_code == 409
    assert "configured" in response.json()["detail"].lower()
