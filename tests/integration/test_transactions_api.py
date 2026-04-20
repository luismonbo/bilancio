"""Integration tests for /transactions API routes."""

import hashlib
from datetime import UTC, datetime

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from bilancio.storage.models import Account, Transaction


def _now() -> datetime:
    return datetime.now(UTC)


def _make_hash(seed: str) -> str:
    return hashlib.sha256(seed.encode()).hexdigest()


async def _create_account(
    auth_client: AsyncClient, headers: dict, name: str = "Checking"
) -> dict:
    return (
        await auth_client.post(
            "/accounts", json={"name": name, "bank": "B"}, headers=headers
        )
    ).json()


async def _seed_transaction(
    db: AsyncSession,
    user_id: int,
    account_id: int,
    seed: str,
    category: str | None = None,
) -> Transaction:
    tx = Transaction(
        user_id=user_id,
        account_id=account_id,
        value_date=_now(),
        amount=-25.0,
        currency="EUR",
        description_raw=f"Desc {seed}",
        merchant_clean=f"Merchant {seed}",
        category=category,
        is_transfer=False,
        is_recurring=False,
        imported_at=_now(),
        hash=_make_hash(seed),
    )
    db.add(tx)
    await db.commit()
    await db.refresh(tx)
    return tx


# ---------------------------------------------------------------------------
# GET /transactions
# ---------------------------------------------------------------------------


async def test_list_transactions_requires_auth(auth_client: AsyncClient) -> None:
    response = await auth_client.get("/transactions")
    assert response.status_code == 401


async def test_list_transactions_empty(auth_client: AsyncClient, authed: tuple) -> None:
    _, headers = authed
    response = await auth_client.get("/transactions", headers=headers)
    assert response.status_code == 200
    assert response.json() == []


async def test_list_transactions_returns_rows(
    auth_client: AsyncClient, authed: tuple, db: AsyncSession
) -> None:
    user, headers = authed
    account = await _create_account(auth_client, headers)
    await _seed_transaction(db, user.id, account["id"], "txapi_list1")

    response = await auth_client.get("/transactions", headers=headers)
    assert len(response.json()) == 1


async def test_list_transactions_filter_by_account(
    auth_client: AsyncClient, authed: tuple, db: AsyncSession
) -> None:
    user, headers = authed
    acc1 = await _create_account(auth_client, headers, "Acc1")
    acc2 = await _create_account(auth_client, headers, "Acc2")
    await _seed_transaction(db, user.id, acc1["id"], "txapi_fa1")
    await _seed_transaction(db, user.id, acc2["id"], "txapi_fa2")

    response = await auth_client.get(
        f"/transactions?account_id={acc1['id']}", headers=headers
    )
    data = response.json()
    assert len(data) == 1
    assert data[0]["account_id"] == acc1["id"]


async def test_list_transactions_filter_needs_review(
    auth_client: AsyncClient, authed: tuple, db: AsyncSession
) -> None:
    user, headers = authed
    account = await _create_account(auth_client, headers)
    await _seed_transaction(db, user.id, account["id"], "txapi_nr1", category="Food")
    await _seed_transaction(db, user.id, account["id"], "txapi_nr2", category=None)

    response = await auth_client.get("/transactions?needs_review=true", headers=headers)
    data = response.json()
    assert len(data) == 1
    assert data[0]["category"] is None


async def test_list_transactions_only_own(
    auth_client: AsyncClient, authed: tuple, db: AsyncSession
) -> None:
    user, headers = authed
    account = await _create_account(auth_client, headers)
    await _seed_transaction(db, user.id, account["id"], "txapi_own1")

    # Stranger transaction — different user_id
    stranger_id = user.id + 3000
    db.add(
        Account(
            user_id=stranger_id, name="S", bank="B", currency="EUR", created_at=_now()
        )
    )
    await db.flush()
    stranger_acc = (
        await db.execute(
            __import__("sqlalchemy")
            .select(Account)
            .where(Account.user_id == stranger_id)
        )
    ).scalar_one()
    await _seed_transaction(db, stranger_id, stranger_acc.id, "txapi_stranger")

    response = await auth_client.get("/transactions", headers=headers)
    assert all(t["user_id"] == user.id for t in response.json())


# ---------------------------------------------------------------------------
# GET /transactions/{id}
# ---------------------------------------------------------------------------


async def test_get_transaction(
    auth_client: AsyncClient, authed: tuple, db: AsyncSession
) -> None:
    user, headers = authed
    account = await _create_account(auth_client, headers)
    tx = await _seed_transaction(db, user.id, account["id"], "txapi_get1")

    response = await auth_client.get(f"/transactions/{tx.id}", headers=headers)
    assert response.status_code == 200
    assert response.json()["id"] == tx.id


async def test_get_transaction_not_found(
    auth_client: AsyncClient, authed: tuple
) -> None:
    _, headers = authed
    response = await auth_client.get("/transactions/999999", headers=headers)
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# PATCH /transactions/{id}
# ---------------------------------------------------------------------------


async def test_patch_transaction_category(
    auth_client: AsyncClient, authed: tuple, db: AsyncSession
) -> None:
    user, headers = authed
    account = await _create_account(auth_client, headers)
    tx = await _seed_transaction(db, user.id, account["id"], "txapi_patch1")

    response = await auth_client.patch(
        f"/transactions/{tx.id}",
        json={"category": "Groceries", "subcategory": "Supermarket"},
        headers=headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["category"] == "Groceries"
    assert body["subcategory"] == "Supermarket"


async def test_patch_transaction_is_transfer(
    auth_client: AsyncClient, authed: tuple, db: AsyncSession
) -> None:
    user, headers = authed
    account = await _create_account(auth_client, headers)
    tx = await _seed_transaction(db, user.id, account["id"], "txapi_patch2")

    response = await auth_client.patch(
        f"/transactions/{tx.id}", json={"is_transfer": True}, headers=headers
    )
    assert response.status_code == 200
    assert response.json()["is_transfer"] is True


async def test_patch_transaction_not_found(
    auth_client: AsyncClient, authed: tuple
) -> None:
    _, headers = authed
    response = await auth_client.patch(
        "/transactions/999999", json={"category": "X"}, headers=headers
    )
    assert response.status_code == 404


async def test_patch_transaction_requires_auth(auth_client: AsyncClient) -> None:
    response = await auth_client.patch("/transactions/1", json={"category": "X"})
    assert response.status_code == 401
