"""Integration tests for /accounts API routes."""

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from bilancio.storage.models import User


# ---------------------------------------------------------------------------
# GET /accounts
# ---------------------------------------------------------------------------


async def test_list_accounts_requires_auth(auth_client: AsyncClient) -> None:
    response = await auth_client.get("/accounts")
    assert response.status_code == 401


async def test_list_accounts_empty(
    auth_client: AsyncClient, authed: tuple, db: AsyncSession
) -> None:
    _, headers = authed
    response = await auth_client.get("/accounts", headers=headers)
    assert response.status_code == 200
    assert response.json() == []


async def test_list_accounts_returns_created(
    auth_client: AsyncClient, authed: tuple
) -> None:
    user, headers = authed
    await auth_client.post(
        "/accounts",
        json={"name": "Checking", "bank": "Mediobanca Premier"},
        headers=headers,
    )

    response = await auth_client.get("/accounts", headers=headers)
    data = response.json()
    assert len(data) == 1
    assert data[0]["name"] == "Checking"
    assert data[0]["bank"] == "Mediobanca Premier"


async def test_list_accounts_only_returns_own(
    auth_client: AsyncClient, authed: tuple, db: AsyncSession
) -> None:
    """Accounts belonging to another user must not appear."""
    from datetime import datetime, timezone
    from bilancio.storage.models import Account

    user, headers = authed
    # Create account for user (our own)
    await auth_client.post(
        "/accounts", json={"name": "Mine", "bank": "B"}, headers=headers
    )
    # Create account for stranger directly in DB (different user_id)
    stranger_id = user.id + 1000
    db.add(
        Account(
            user_id=stranger_id,
            name="Stranger",
            bank="B",
            currency="EUR",
            created_at=datetime.now(timezone.utc),
        )
    )
    await db.commit()

    response = await auth_client.get("/accounts", headers=headers)
    names = [a["name"] for a in response.json()]
    assert "Stranger" not in names
    assert "Mine" in names


# ---------------------------------------------------------------------------
# POST /accounts
# ---------------------------------------------------------------------------


async def test_create_account_returns_201(
    auth_client: AsyncClient, authed: tuple
) -> None:
    _, headers = authed
    response = await auth_client.post(
        "/accounts",
        json={"name": "Checking", "bank": "Mediobanca Premier", "currency": "EUR"},
        headers=headers,
    )
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Checking"
    assert body["bank"] == "Mediobanca Premier"
    assert body["id"] is not None


async def test_create_account_missing_name_returns_422(
    auth_client: AsyncClient, authed: tuple
) -> None:
    _, headers = authed
    response = await auth_client.post(
        "/accounts", json={"bank": "B"}, headers=headers
    )
    assert response.status_code == 422


async def test_create_account_requires_auth(auth_client: AsyncClient) -> None:
    response = await auth_client.post("/accounts", json={"name": "A", "bank": "B"})
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# GET /accounts/{id}
# ---------------------------------------------------------------------------


async def test_get_account(auth_client: AsyncClient, authed: tuple) -> None:
    _, headers = authed
    created = (
        await auth_client.post(
            "/accounts", json={"name": "A", "bank": "B"}, headers=headers
        )
    ).json()

    response = await auth_client.get(f"/accounts/{created['id']}", headers=headers)
    assert response.status_code == 200
    assert response.json()["id"] == created["id"]


async def test_get_account_not_found(auth_client: AsyncClient, authed: tuple) -> None:
    _, headers = authed
    response = await auth_client.get("/accounts/999999", headers=headers)
    assert response.status_code == 404


async def test_get_account_not_owned_returns_404(
    auth_client: AsyncClient, authed: tuple, db: AsyncSession
) -> None:
    from datetime import datetime, timezone
    from bilancio.storage.models import Account

    user, headers = authed
    stranger_id = user.id + 2000
    stranger_account = Account(
        user_id=stranger_id, name="NotMine", bank="B",
        currency="EUR", created_at=datetime.now(timezone.utc),
    )
    db.add(stranger_account)
    await db.commit()
    await db.refresh(stranger_account)

    response = await auth_client.get(f"/accounts/{stranger_account.id}", headers=headers)
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /accounts/{id}
# ---------------------------------------------------------------------------


async def test_delete_account_returns_204(
    auth_client: AsyncClient, authed: tuple
) -> None:
    _, headers = authed
    created = (
        await auth_client.post(
            "/accounts", json={"name": "A", "bank": "B"}, headers=headers
        )
    ).json()

    response = await auth_client.delete(f"/accounts/{created['id']}", headers=headers)
    assert response.status_code == 204


async def test_delete_account_not_found_returns_404(
    auth_client: AsyncClient, authed: tuple
) -> None:
    _, headers = authed
    response = await auth_client.delete("/accounts/999999", headers=headers)
    assert response.status_code == 404


async def test_deleted_account_no_longer_listed(
    auth_client: AsyncClient, authed: tuple
) -> None:
    _, headers = authed
    created = (
        await auth_client.post(
            "/accounts", json={"name": "A", "bank": "B"}, headers=headers
        )
    ).json()
    await auth_client.delete(f"/accounts/{created['id']}", headers=headers)

    response = await auth_client.get("/accounts", headers=headers)
    ids = [a["id"] for a in response.json()]
    assert created["id"] not in ids
