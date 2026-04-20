"""Integration tests for DashboardService."""

import hashlib
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from bilancio.services.dashboard_service import DashboardService
from bilancio.storage.models import Account, Transaction, User


def _now() -> datetime:
    return datetime.now(UTC)


def _dt(year: int, month: int, day: int) -> datetime:
    return datetime(year, month, day, 12, 0, 0, tzinfo=UTC)


def _hash(seed: str) -> str:
    return hashlib.sha256(seed.encode()).hexdigest()


async def _make_user(db: AsyncSession, email: str) -> User:
    user = User(email=email, display_name="Test", created_at=_now())
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def _make_account(db: AsyncSession, user_id: int) -> Account:
    account = Account(
        user_id=user_id, name="Checking", bank="TestBank",
        currency="EUR", created_at=_now(),
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
    merchant_clean: str | None = "TestMerchant",
    is_transfer: bool = False,
) -> Transaction:
    tx = Transaction(
        user_id=user_id,
        account_id=account_id,
        value_date=value_date,
        amount=amount,
        currency="EUR",
        description_raw=f"Desc {seed}",
        merchant_clean=merchant_clean,
        category=category,
        is_transfer=is_transfer,
        is_recurring=False,
        imported_at=_now(),
        hash=_hash(seed),
    )
    db.add(tx)
    await db.commit()
    await db.refresh(tx)
    return tx


MONTH = "2026-03"
IN_MONTH = _dt(2026, 3, 15)
OUT_OF_MONTH = _dt(2026, 4, 1)


# ---------------------------------------------------------------------------
# empty month
# ---------------------------------------------------------------------------


async def test_empty_month_returns_zeros(db: AsyncSession) -> None:
    user = await _make_user(db, "dash_empty@example.com")
    svc = DashboardService(db)
    summary = await svc.get_summary(user_id=user.id, month=MONTH)

    assert summary.total_in == 0.0
    assert summary.total_out == 0.0
    assert summary.net == 0.0
    assert summary.category_breakdown == []
    assert summary.top_merchants == []
    assert summary.needs_review_count == 0


# ---------------------------------------------------------------------------
# totals
# ---------------------------------------------------------------------------


async def test_total_in_and_out_computed_correctly(db: AsyncSession) -> None:
    user = await _make_user(db, "dash_totals@example.com")
    acc = await _make_account(db, user.id)
    await _make_tx(db, user.id, acc.id, "dt1", amount=1000.0, value_date=IN_MONTH, category="Salary")
    await _make_tx(db, user.id, acc.id, "dt2", amount=-200.0, value_date=IN_MONTH)
    await _make_tx(db, user.id, acc.id, "dt3", amount=-50.0, value_date=IN_MONTH)

    svc = DashboardService(db)
    s = await svc.get_summary(user_id=user.id, month=MONTH)

    assert s.total_in == 1000.0
    assert s.total_out == -250.0
    assert s.net == 750.0


async def test_transactions_outside_month_excluded(db: AsyncSession) -> None:
    user = await _make_user(db, "dash_outside@example.com")
    acc = await _make_account(db, user.id)
    await _make_tx(db, user.id, acc.id, "do1", amount=-100.0, value_date=IN_MONTH)
    await _make_tx(db, user.id, acc.id, "do2", amount=-999.0, value_date=OUT_OF_MONTH)

    svc = DashboardService(db)
    s = await svc.get_summary(user_id=user.id, month=MONTH)

    assert s.total_out == -100.0


# ---------------------------------------------------------------------------
# transfers excluded
# ---------------------------------------------------------------------------


async def test_transfers_excluded_from_all_aggregates(db: AsyncSession) -> None:
    user = await _make_user(db, "dash_transfer@example.com")
    acc = await _make_account(db, user.id)
    await _make_tx(db, user.id, acc.id, "dtr1", amount=-300.0, value_date=IN_MONTH, is_transfer=True)
    await _make_tx(db, user.id, acc.id, "dtr2", amount=-100.0, value_date=IN_MONTH, is_transfer=False)

    svc = DashboardService(db)
    s = await svc.get_summary(user_id=user.id, month=MONTH)

    assert s.total_out == -100.0
    assert s.needs_review_count == 0  # both have category set by default


# ---------------------------------------------------------------------------
# category breakdown
# ---------------------------------------------------------------------------


async def test_category_breakdown_sorted_by_spend(db: AsyncSession) -> None:
    user = await _make_user(db, "dash_cat@example.com")
    acc = await _make_account(db, user.id)
    await _make_tx(db, user.id, acc.id, "dc1", amount=-10.0, value_date=IN_MONTH, category="Dining")
    await _make_tx(db, user.id, acc.id, "dc2", amount=-50.0, value_date=IN_MONTH, category="Rent")
    await _make_tx(db, user.id, acc.id, "dc3", amount=-20.0, value_date=IN_MONTH, category="Dining")

    svc = DashboardService(db)
    s = await svc.get_summary(user_id=user.id, month=MONTH)

    cats = [c.category for c in s.category_breakdown]
    assert cats[0] == "Rent"    # -50 > -30 abs → Rent first
    assert cats[1] == "Dining"


async def test_category_breakdown_pct_sums_to_100(db: AsyncSession) -> None:
    user = await _make_user(db, "dash_pct@example.com")
    acc = await _make_account(db, user.id)
    await _make_tx(db, user.id, acc.id, "dp1", amount=-75.0, value_date=IN_MONTH, category="A")
    await _make_tx(db, user.id, acc.id, "dp2", amount=-25.0, value_date=IN_MONTH, category="B")

    svc = DashboardService(db)
    s = await svc.get_summary(user_id=user.id, month=MONTH)

    total_pct = sum(c.pct for c in s.category_breakdown)
    assert abs(total_pct - 100.0) < 0.5  # rounding tolerance


async def test_uncategorised_grouped_under_uncategorised(db: AsyncSession) -> None:
    user = await _make_user(db, "dash_uncat@example.com")
    acc = await _make_account(db, user.id)
    await _make_tx(db, user.id, acc.id, "du1", amount=-40.0, value_date=IN_MONTH, category=None)
    await _make_tx(db, user.id, acc.id, "du2", amount=-60.0, value_date=IN_MONTH, category=None)

    svc = DashboardService(db)
    s = await svc.get_summary(user_id=user.id, month=MONTH)

    assert len(s.category_breakdown) == 1
    assert s.category_breakdown[0].category == "Uncategorised"
    assert s.category_breakdown[0].amount == -100.0


# ---------------------------------------------------------------------------
# top merchants
# ---------------------------------------------------------------------------


async def test_top_merchants_limited_to_10(db: AsyncSession) -> None:
    user = await _make_user(db, "dash_merch@example.com")
    acc = await _make_account(db, user.id)
    for i in range(15):
        await _make_tx(
            db, user.id, acc.id, f"dm{i}",
            amount=-float(i + 1),
            value_date=IN_MONTH,
            merchant_clean=f"Merchant{i}",
        )

    svc = DashboardService(db)
    s = await svc.get_summary(user_id=user.id, month=MONTH)

    assert len(s.top_merchants) == 10


async def test_top_merchants_sorted_by_spend(db: AsyncSession) -> None:
    user = await _make_user(db, "dash_merch_sort@example.com")
    acc = await _make_account(db, user.id)
    await _make_tx(db, user.id, acc.id, "dms1", amount=-5.0, value_date=IN_MONTH, merchant_clean="Small")
    await _make_tx(db, user.id, acc.id, "dms2", amount=-200.0, value_date=IN_MONTH, merchant_clean="Big")

    svc = DashboardService(db)
    s = await svc.get_summary(user_id=user.id, month=MONTH)

    assert s.top_merchants[0].merchant == "Big"


async def test_top_merchants_aggregates_multiple_txs(db: AsyncSession) -> None:
    user = await _make_user(db, "dash_merch_agg@example.com")
    acc = await _make_account(db, user.id)
    await _make_tx(db, user.id, acc.id, "dma1", amount=-30.0, value_date=IN_MONTH, merchant_clean="Supermarket")
    await _make_tx(db, user.id, acc.id, "dma2", amount=-20.0, value_date=IN_MONTH, merchant_clean="Supermarket")

    svc = DashboardService(db)
    s = await svc.get_summary(user_id=user.id, month=MONTH)

    assert s.top_merchants[0].amount == -50.0
    assert s.top_merchants[0].count == 2


# ---------------------------------------------------------------------------
# needs_review_count
# ---------------------------------------------------------------------------


async def test_needs_review_count_correct(db: AsyncSession) -> None:
    user = await _make_user(db, "dash_nrc@example.com")
    acc = await _make_account(db, user.id)
    await _make_tx(db, user.id, acc.id, "dnr1", amount=-10.0, value_date=IN_MONTH, category=None)
    await _make_tx(db, user.id, acc.id, "dnr2", amount=-10.0, value_date=IN_MONTH, category=None)
    await _make_tx(db, user.id, acc.id, "dnr3", amount=-10.0, value_date=IN_MONTH, category="Food")

    svc = DashboardService(db)
    s = await svc.get_summary(user_id=user.id, month=MONTH)

    assert s.needs_review_count == 2


# ---------------------------------------------------------------------------
# cross-user isolation
# ---------------------------------------------------------------------------


async def test_cross_user_isolation(db: AsyncSession) -> None:
    user_a = await _make_user(db, "dash_iso_a@example.com")
    user_b = await _make_user(db, "dash_iso_b@example.com")
    acc_a = await _make_account(db, user_a.id)
    acc_b = await _make_account(db, user_b.id)
    await _make_tx(db, user_a.id, acc_a.id, "di_a", amount=-500.0, value_date=IN_MONTH)
    await _make_tx(db, user_b.id, acc_b.id, "di_b", amount=-999.0, value_date=IN_MONTH)

    svc = DashboardService(db)
    s = await svc.get_summary(user_id=user_a.id, month=MONTH)

    assert s.total_out == -500.0
