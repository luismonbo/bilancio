"""Integration tests for AccountService."""

from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bilancio.services.account_service import AccountService
from bilancio.storage.models import AuditLog, User


def _now() -> datetime:
    return datetime.now(UTC)


async def _make_user(db: AsyncSession, email: str) -> User:
    user = User(email=email, display_name="Test", created_at=_now())
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


# ---------------------------------------------------------------------------
# create
# ---------------------------------------------------------------------------


async def test_create_account(db: AsyncSession) -> None:
    user = await _make_user(db, "acc_create@example.com")
    svc = AccountService(db)

    account = await svc.create(
        user_id=user.id, name="Checking", bank="Mediobanca Premier"
    )

    assert account.id is not None
    assert account.name == "Checking"
    assert account.bank == "Mediobanca Premier"
    assert account.currency == "EUR"
    assert account.user_id == user.id


async def test_create_account_default_currency_eur(db: AsyncSession) -> None:
    user = await _make_user(db, "acc_cur@example.com")
    svc = AccountService(db)

    account = await svc.create(user_id=user.id, name="A", bank="B")

    assert account.currency == "EUR"


async def test_create_account_custom_currency(db: AsyncSession) -> None:
    user = await _make_user(db, "acc_usd@example.com")
    svc = AccountService(db)

    account = await svc.create(user_id=user.id, name="A", bank="B", currency="USD")

    assert account.currency == "USD"


async def test_create_account_writes_audit_log(db: AsyncSession) -> None:
    user = await _make_user(db, "acc_audit_c@example.com")
    svc = AccountService(db)
    await svc.create(user_id=user.id, name="A", bank="B")

    logs = (
        (await db.execute(select(AuditLog).where(AuditLog.actor_user_id == user.id)))
        .scalars()
        .all()
    )
    assert any(log.action == "create" and log.entity_type == "account" for log in logs)


# ---------------------------------------------------------------------------
# list
# ---------------------------------------------------------------------------


async def test_list_returns_only_user_accounts(db: AsyncSession) -> None:
    user_a = await _make_user(db, "acc_list_a@example.com")
    user_b = await _make_user(db, "acc_list_b@example.com")
    svc = AccountService(db)

    await svc.create(user_id=user_a.id, name="A1", bank="B")
    await svc.create(user_id=user_b.id, name="B1", bank="B")

    accounts = await svc.list_accounts(user_id=user_a.id)
    assert all(a.user_id == user_a.id for a in accounts)
    assert len(accounts) == 1


# ---------------------------------------------------------------------------
# get
# ---------------------------------------------------------------------------


async def test_get_account(db: AsyncSession) -> None:
    user = await _make_user(db, "acc_get@example.com")
    svc = AccountService(db)
    created = await svc.create(user_id=user.id, name="A", bank="B")

    fetched = await svc.get(account_id=created.id, user_id=user.id)
    assert fetched.id == created.id


async def test_get_account_not_owned_raises(db: AsyncSession) -> None:
    user_a = await _make_user(db, "acc_own_a@example.com")
    user_b = await _make_user(db, "acc_own_b@example.com")
    svc = AccountService(db)
    account = await svc.create(user_id=user_a.id, name="A", bank="B")

    with pytest.raises(ValueError, match="not found"):
        await svc.get(account_id=account.id, user_id=user_b.id)


# ---------------------------------------------------------------------------
# delete
# ---------------------------------------------------------------------------


async def test_delete_account(db: AsyncSession) -> None:
    user = await _make_user(db, "acc_del@example.com")
    svc = AccountService(db)
    account = await svc.create(user_id=user.id, name="A", bank="B")

    await svc.delete(account_id=account.id, user_id=user.id)

    accounts = await svc.list_accounts(user_id=user.id)
    assert all(a.id != account.id for a in accounts)


async def test_delete_account_not_owned_raises(db: AsyncSession) -> None:
    user_a = await _make_user(db, "acc_del_a@example.com")
    user_b = await _make_user(db, "acc_del_b@example.com")
    svc = AccountService(db)
    account = await svc.create(user_id=user_a.id, name="A", bank="B")

    with pytest.raises(ValueError, match="not found"):
        await svc.delete(account_id=account.id, user_id=user_b.id)


async def test_delete_account_writes_audit_log(db: AsyncSession) -> None:
    user = await _make_user(db, "acc_audit_d@example.com")
    svc = AccountService(db)
    account = await svc.create(user_id=user.id, name="A", bank="B")
    await svc.delete(account_id=account.id, user_id=user.id)

    logs = (
        (await db.execute(select(AuditLog).where(AuditLog.actor_user_id == user.id)))
        .scalars()
        .all()
    )
    assert any(log.action == "delete" and log.entity_type == "account" for log in logs)
