"""Integration tests for GET /dashboard."""

import hashlib
from datetime import UTC, datetime

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from bilancio.storage.models import Account, Transaction


def _dt(year: int, month: int, day: int) -> datetime:
    return datetime(year, month, day, 12, 0, 0, tzinfo=UTC)


def _hash(seed: str) -> str:
    return hashlib.sha256(seed.encode()).hexdigest()


async def _make_account(db: AsyncSession, user_id: int) -> Account:
    account = Account(
        user_id=user_id,
        name="Checking",
        bank="TestBank",
        currency="EUR",
        created_at=datetime.now(UTC),
    )
    db.add(account)
    await db.commit()
    await db.refresh(account)
    return account


async def _make_tx(
    db: AsyncSession,
    user_id: int,
    account_id: int,
    seed: str,
    *,
    amount: float,
    value_date: datetime,
    category: str | None = "Groceries",
) -> Transaction:
    tx = Transaction(
        user_id=user_id,
        account_id=account_id,
        value_date=value_date,
        amount=amount,
        currency="EUR",
        description_raw=f"Desc {seed}",
        merchant_clean="Merchant",
        category=category,
        is_transfer=False,
        is_recurring=False,
        imported_at=datetime.now(UTC),
        hash=_hash(seed),
    )
    db.add(tx)
    await db.commit()
    await db.refresh(tx)
    return tx


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


async def test_dashboard_requires_auth(auth_client: AsyncClient) -> None:
    response = await auth_client.get("/dashboard")
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


async def test_dashboard_invalid_month_returns_422(
    auth_client: AsyncClient, authed: tuple
) -> None:
    _, headers = authed
    response = await auth_client.get("/dashboard?month=2026-13", headers=headers)
    assert response.status_code == 422


async def test_dashboard_invalid_month_format_returns_422(
    auth_client: AsyncClient, authed: tuple
) -> None:
    _, headers = authed
    response = await auth_client.get("/dashboard?month=March-2026", headers=headers)
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Empty month
# ---------------------------------------------------------------------------


async def test_dashboard_empty_month_returns_zeros(
    auth_client: AsyncClient, authed: tuple
) -> None:
    _, headers = authed
    response = await auth_client.get("/dashboard?month=2026-03", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["month"] == "2026-03"
    assert body["total_in"] == 0.0
    assert body["total_out"] == 0.0
    assert body["net"] == 0.0
    assert body["category_breakdown"] == []
    assert body["top_merchants"] == []
    assert body["needs_review_count"] == 0


# ---------------------------------------------------------------------------
# Default month (no param)
# ---------------------------------------------------------------------------


async def test_dashboard_returns_current_month_by_default(
    auth_client: AsyncClient, authed: tuple
) -> None:
    _, headers = authed
    response = await auth_client.get("/dashboard", headers=headers)
    assert response.status_code == 200
    body = response.json()
    now = datetime.now(UTC)
    assert body["month"] == f"{now.year}-{now.month:02d}"


# ---------------------------------------------------------------------------
# Aggregates
# ---------------------------------------------------------------------------


async def test_dashboard_totals_correct(
    auth_client: AsyncClient, authed: tuple, db: AsyncSession
) -> None:
    user, headers = authed
    acc = await _make_account(db, user.id)
    await _make_tx(db, user.id, acc.id, "da_in", amount=1000.0, value_date=_dt(2026, 3, 1), category="Salary")
    await _make_tx(db, user.id, acc.id, "da_out", amount=-250.0, value_date=_dt(2026, 3, 15))

    response = await auth_client.get("/dashboard?month=2026-03", headers=headers)
    body = response.json()
    assert body["total_in"] == 1000.0
    assert body["total_out"] == -250.0
    assert body["net"] == 750.0


async def test_dashboard_needs_review_count(
    auth_client: AsyncClient, authed: tuple, db: AsyncSession
) -> None:
    user, headers = authed
    acc = await _make_account(db, user.id)
    await _make_tx(db, user.id, acc.id, "dnr_a", amount=-10.0, value_date=_dt(2026, 3, 5), category=None)
    await _make_tx(db, user.id, acc.id, "dnr_b", amount=-20.0, value_date=_dt(2026, 3, 6), category="Food")

    response = await auth_client.get("/dashboard?month=2026-03", headers=headers)
    assert response.json()["needs_review_count"] == 1
