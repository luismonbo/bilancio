"""Integration tests for TransactionService."""

import hashlib
from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bilancio.services.transaction_service import TransactionService
from bilancio.storage.models import Account, AuditLog, Transaction, User


def _now() -> datetime:
    return datetime.now(UTC)


def _make_hash(seed: str) -> str:
    return hashlib.sha256(seed.encode()).hexdigest()


async def _make_user(db: AsyncSession, email: str) -> User:
    user = User(email=email, display_name="Test", created_at=_now())
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def _make_account(db: AsyncSession, user_id: int) -> Account:
    account = Account(
        user_id=user_id,
        name="Checking",
        bank="TestBank",
        currency="EUR",
        created_at=_now(),
    )
    db.add(account)
    await db.commit()
    await db.refresh(account)
    return account


async def _make_transaction(
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
        amount=-10.0,
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
# list
# ---------------------------------------------------------------------------


async def test_list_returns_only_user_transactions(db: AsyncSession) -> None:
    user_a = await _make_user(db, "tx_list_a@example.com")
    user_b = await _make_user(db, "tx_list_b@example.com")
    account_a = await _make_account(db, user_a.id)
    account_b = await _make_account(db, user_b.id)
    await _make_transaction(db, user_a.id, account_a.id, "tla1")
    await _make_transaction(db, user_b.id, account_b.id, "tlb1")

    svc = TransactionService(db)
    rows = await svc.list_transactions(user_id=user_a.id)

    assert all(r.user_id == user_a.id for r in rows)
    assert len(rows) == 1


async def test_list_filters_by_account_id(db: AsyncSession) -> None:
    user = await _make_user(db, "tx_acc_filter@example.com")
    acc1 = await _make_account(db, user.id)
    acc2 = await _make_account(db, user.id)
    await _make_transaction(db, user.id, acc1.id, "txaf1")
    await _make_transaction(db, user.id, acc2.id, "txaf2")

    svc = TransactionService(db)
    rows = await svc.list_transactions(user_id=user.id, account_id=acc1.id)

    assert len(rows) == 1
    assert rows[0].account_id == acc1.id


async def test_list_filters_by_needs_review(db: AsyncSession) -> None:
    user = await _make_user(db, "tx_review@example.com")
    account = await _make_account(db, user.id)
    await _make_transaction(db, user.id, account.id, "txr_cat", category="Groceries")
    await _make_transaction(db, user.id, account.id, "txr_none", category=None)

    svc = TransactionService(db)
    rows = await svc.list_transactions(user_id=user.id, needs_review=True)

    assert len(rows) == 1
    assert rows[0].category is None


async def test_list_respects_limit_and_offset(db: AsyncSession) -> None:
    user = await _make_user(db, "tx_page@example.com")
    account = await _make_account(db, user.id)
    for i in range(5):
        await _make_transaction(db, user.id, account.id, f"txp{i}")

    svc = TransactionService(db)
    page1 = await svc.list_transactions(user_id=user.id, limit=2, offset=0)
    page2 = await svc.list_transactions(user_id=user.id, limit=2, offset=2)

    assert len(page1) == 2
    assert len(page2) == 2
    assert {r.id for r in page1}.isdisjoint({r.id for r in page2})


# ---------------------------------------------------------------------------
# get
# ---------------------------------------------------------------------------


async def test_get_transaction(db: AsyncSession) -> None:
    user = await _make_user(db, "tx_get@example.com")
    account = await _make_account(db, user.id)
    tx = await _make_transaction(db, user.id, account.id, "txg1")

    svc = TransactionService(db)
    fetched = await svc.get(transaction_id=tx.id, user_id=user.id)

    assert fetched.id == tx.id


async def test_get_not_owned_raises(db: AsyncSession) -> None:
    user_a = await _make_user(db, "tx_own_a@example.com")
    user_b = await _make_user(db, "tx_own_b@example.com")
    account = await _make_account(db, user_a.id)
    tx = await _make_transaction(db, user_a.id, account.id, "txown1")

    svc = TransactionService(db)
    with pytest.raises(ValueError, match="not found"):
        await svc.get(transaction_id=tx.id, user_id=user_b.id)


# ---------------------------------------------------------------------------
# update
# ---------------------------------------------------------------------------


async def test_update_category(db: AsyncSession) -> None:
    user = await _make_user(db, "tx_upd@example.com")
    account = await _make_account(db, user.id)
    tx = await _make_transaction(db, user.id, account.id, "txupd1")

    svc = TransactionService(db)
    updated = await svc.update(
        transaction_id=tx.id,
        user_id=user.id,
        category="Groceries",
        subcategory="Supermarket",
    )

    assert updated.category == "Groceries"
    assert updated.subcategory == "Supermarket"


async def test_update_is_transfer(db: AsyncSession) -> None:
    user = await _make_user(db, "tx_transfer@example.com")
    account = await _make_account(db, user.id)
    tx = await _make_transaction(db, user.id, account.id, "txtr1")

    svc = TransactionService(db)
    updated = await svc.update(transaction_id=tx.id, user_id=user.id, is_transfer=True)

    assert updated.is_transfer is True


async def test_update_user_notes(db: AsyncSession) -> None:
    user = await _make_user(db, "tx_notes@example.com")
    account = await _make_account(db, user.id)
    tx = await _make_transaction(db, user.id, account.id, "txnotes1")

    svc = TransactionService(db)
    updated = await svc.update(
        transaction_id=tx.id, user_id=user.id, user_notes="Lunch with client"
    )

    assert updated.user_notes == "Lunch with client"


async def test_update_writes_audit_log(db: AsyncSession) -> None:
    user = await _make_user(db, "tx_audit@example.com")
    account = await _make_account(db, user.id)
    tx = await _make_transaction(db, user.id, account.id, "txaudit1")

    svc = TransactionService(db)
    await svc.update(transaction_id=tx.id, user_id=user.id, category="Food")

    logs = (
        (await db.execute(select(AuditLog).where(AuditLog.actor_user_id == user.id)))
        .scalars()
        .all()
    )
    assert any(
        log.action == "update" and log.entity_type == "transaction" for log in logs
    )


async def test_update_not_owned_raises(db: AsyncSession) -> None:
    user_a = await _make_user(db, "tx_updown_a@example.com")
    user_b = await _make_user(db, "tx_updown_b@example.com")
    account = await _make_account(db, user_a.id)
    tx = await _make_transaction(db, user_a.id, account.id, "txupdown1")

    svc = TransactionService(db)
    with pytest.raises(ValueError, match="not found"):
        await svc.update(transaction_id=tx.id, user_id=user_b.id, category="X")
