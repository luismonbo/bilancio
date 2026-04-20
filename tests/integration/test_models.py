"""Integration tests: verify the ORM models map correctly to the schema."""

from datetime import UTC, datetime

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from bilancio.storage.models import (
    Account,
    AuditLog,
    CategorizationRule,
    Category,
    Transaction,
    User,
)


def _now() -> datetime:
    return datetime.now(UTC)


async def test_create_user(db: AsyncSession) -> None:
    user = User(email="u1@example.com", display_name="Test User", created_at=_now())
    db.add(user)
    await db.commit()
    await db.refresh(user)

    assert user.id is not None
    assert user.email == "u1@example.com"
    assert user.disabled_at is None


async def test_user_email_unique(db: AsyncSession) -> None:
    db.add(User(email="dup@example.com", display_name="A", created_at=_now()))
    await db.commit()

    db.add(User(email="dup@example.com", display_name="B", created_at=_now()))
    with pytest.raises(IntegrityError):
        await db.commit()
    await db.rollback()


async def test_create_account_linked_to_user(db: AsyncSession) -> None:
    user = User(email="acc@example.com", display_name="Acc", created_at=_now())
    db.add(user)
    await db.commit()

    account = Account(
        user_id=user.id,
        name="Mediobanca Premier",
        bank="Mediobanca Premier",
        currency="EUR",
        created_at=_now(),
    )
    db.add(account)
    await db.commit()
    await db.refresh(account)

    assert account.id is not None
    assert account.user_id == user.id


async def test_transaction_hash_unique_per_account(db: AsyncSession) -> None:
    user = User(email="tx@example.com", display_name="Tx", created_at=_now())
    db.add(user)
    await db.commit()

    account = Account(
        user_id=user.id, name="TX Acc", bank="Test", currency="EUR", created_at=_now()
    )
    db.add(account)
    await db.commit()

    tx1 = Transaction(
        user_id=user.id,
        account_id=account.id,
        value_date=_now(),
        amount=-50.00,
        currency="EUR",
        hash="deadbeef",
        imported_at=_now(),
    )
    db.add(tx1)
    await db.commit()

    tx2 = Transaction(
        user_id=user.id,
        account_id=account.id,
        value_date=_now(),
        amount=-99.00,
        currency="EUR",
        hash="deadbeef",  # same hash → must be rejected
        imported_at=_now(),
    )
    db.add(tx2)
    with pytest.raises(IntegrityError):
        await db.commit()
    await db.rollback()


async def test_same_hash_allowed_across_accounts(db: AsyncSession) -> None:
    """The (account_id, hash) uniqueness is per-account, not global."""
    user = User(email="multi@example.com", display_name="Multi", created_at=_now())
    db.add(user)
    await db.commit()

    acc_a = Account(
        user_id=user.id, name="A", bank="Test", currency="EUR", created_at=_now()
    )
    acc_b = Account(
        user_id=user.id, name="B", bank="Test", currency="EUR", created_at=_now()
    )
    db.add_all([acc_a, acc_b])
    await db.commit()

    db.add(
        Transaction(
            user_id=user.id,
            account_id=acc_a.id,
            value_date=_now(),
            amount=-1,
            currency="EUR",
            hash="shared",
            imported_at=_now(),
        )
    )
    db.add(
        Transaction(
            user_id=user.id,
            account_id=acc_b.id,
            value_date=_now(),
            amount=-1,
            currency="EUR",
            hash="shared",
            imported_at=_now(),
        )
    )
    await db.commit()  # must not raise


async def test_categorization_rule(db: AsyncSession) -> None:
    user = User(email="rule@example.com", display_name="Rule", created_at=_now())
    db.add(user)
    await db.commit()

    rule = CategorizationRule(
        user_id=user.id,
        pattern="Esselunga",
        pattern_type="contains",
        category="Groceries",
        priority=10,
        enabled=True,
        created_at=_now(),
    )
    db.add(rule)
    await db.commit()
    await db.refresh(rule)

    assert rule.id is not None
    assert rule.pattern_type == "contains"


async def test_category_hierarchy(db: AsyncSession) -> None:
    user = User(email="cat@example.com", display_name="Cat", created_at=_now())
    db.add(user)
    await db.commit()

    parent = Category(user_id=user.id, name="Food", color="#ff0000")
    db.add(parent)
    await db.commit()

    child = Category(
        user_id=user.id, name="Restaurants", parent_id=parent.id, color="#ff8888"
    )
    db.add(child)
    await db.commit()
    await db.refresh(child)

    assert child.parent_id == parent.id


async def test_audit_log(db: AsyncSession) -> None:
    user = User(email="audit@example.com", display_name="Audit", created_at=_now())
    db.add(user)
    await db.commit()

    log = AuditLog(
        timestamp=_now(),
        actor_user_id=user.id,
        action="create",
        entity_type="account",
        entity_id=1,
        before_state=None,
        after_state={"name": "Mediobanca Premier"},
    )
    db.add(log)
    await db.commit()
    await db.refresh(log)

    assert log.id is not None
    assert log.after_state == {"name": "Mediobanca Premier"}
