"""Integration tests for ImportService — uses in-memory SQLite DB.

Pipeline:  detect → parse → dedup → categorize → store → audit
"""

import hashlib
from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bilancio.parsers.base import BankParser, ParsedTransaction
from bilancio.services.import_service import ImportService, ImportSummary
from bilancio.storage.models import Account, AuditLog, CategorizationRule, Transaction, User


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _make_hash(seed: str) -> str:
    return hashlib.sha256(seed.encode()).hexdigest()


def _ptx(
    account_id: int = 1,
    description_raw: str = "Test transaction",
    merchant_clean: str | None = "TestMerchant",
    amount: float = -10.0,
    seed: str | None = None,
) -> ParsedTransaction:
    """Build a ParsedTransaction with a deterministic hash based on seed."""
    seed = seed or description_raw
    return ParsedTransaction(
        account_id=account_id,
        booking_date=None,
        value_date=_now(),
        amount=amount,
        currency="EUR",
        transaction_type="Pagam. POS",
        description_raw=description_raw,
        merchant_clean=merchant_clean,
        source_file="test.xlsx",
        source_row=1,
        hash=_make_hash(seed),
    )


class _FakeParser:
    """Minimal BankParser implementation for tests — returns predetermined transactions."""

    bank_name = "TestBank"

    def __init__(
        self,
        transactions: list[ParsedTransaction],
        detects: bool = True,
    ) -> None:
        self._transactions = transactions
        self._detects = detects

    def detect(self, file_path: Path) -> bool:
        return self._detects

    def parse(self, file_path: Path, account_id: int) -> list[ParsedTransaction]:
        return self._transactions


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


_FAKE_PATH = Path("fake_file.xlsx")


# ---------------------------------------------------------------------------
# Parser detection
# ---------------------------------------------------------------------------


async def test_no_parser_for_file_raises(db: AsyncSession) -> None:
    user = await _make_user(db, "imp_noparser@example.com")
    account = await _make_account(db, user.id)
    never_detects = _FakeParser([], detects=False)
    svc = ImportService(db, parsers=[never_detects])

    with pytest.raises(ValueError, match="No parser found"):
        await svc.import_file(
            file_path=_FAKE_PATH,
            account_id=account.id,
            user_id=user.id,
        )


async def test_parser_protocol_satisfied() -> None:
    """_FakeParser must satisfy the BankParser protocol."""
    assert isinstance(_FakeParser([]), BankParser)


# ---------------------------------------------------------------------------
# Basic import
# ---------------------------------------------------------------------------


async def test_import_creates_transactions(db: AsyncSession) -> None:
    user = await _make_user(db, "basic@example.com")
    account = await _make_account(db, user.id)
    txns = [_ptx(account.id, seed="tx1"), _ptx(account.id, seed="tx2")]
    svc = ImportService(db, parsers=[_FakeParser(txns)])

    await svc.import_file(file_path=_FAKE_PATH, account_id=account.id, user_id=user.id)

    rows = (
        await db.execute(
            select(Transaction).where(Transaction.account_id == account.id)
        )
    ).scalars().all()
    assert len(rows) == 2


async def test_import_returns_import_summary(db: AsyncSession) -> None:
    user = await _make_user(db, "summary@example.com")
    account = await _make_account(db, user.id)
    txns = [_ptx(account.id, seed="s1"), _ptx(account.id, seed="s2")]
    svc = ImportService(db, parsers=[_FakeParser(txns)])

    result = await svc.import_file(
        file_path=_FAKE_PATH, account_id=account.id, user_id=user.id
    )

    assert isinstance(result, ImportSummary)
    assert result.added == 2
    assert result.skipped == 0
    assert result.needs_review == 2  # no rules loaded


async def test_import_empty_file_returns_zero_summary(db: AsyncSession) -> None:
    user = await _make_user(db, "empty@example.com")
    account = await _make_account(db, user.id)
    svc = ImportService(db, parsers=[_FakeParser([])])

    result = await svc.import_file(
        file_path=_FAKE_PATH, account_id=account.id, user_id=user.id
    )

    assert result == ImportSummary(added=0, skipped=0, needs_review=0)


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------


async def test_import_idempotent(db: AsyncSession) -> None:
    """Reimporting the same file a second time must skip all rows."""
    user = await _make_user(db, "idemp@example.com")
    account = await _make_account(db, user.id)
    txns = [_ptx(account.id, seed="i1"), _ptx(account.id, seed="i2")]
    svc = ImportService(db, parsers=[_FakeParser(txns)])

    first = await svc.import_file(
        file_path=_FAKE_PATH, account_id=account.id, user_id=user.id
    )
    second = await svc.import_file(
        file_path=_FAKE_PATH, account_id=account.id, user_id=user.id
    )

    assert first.added == 2
    assert second.added == 0
    assert second.skipped == 2


async def test_import_partial_dedup(db: AsyncSession) -> None:
    """New rows are added; existing rows are skipped."""
    user = await _make_user(db, "partial@example.com")
    account = await _make_account(db, user.id)

    batch1 = [_ptx(account.id, seed="p1"), _ptx(account.id, seed="p2")]
    svc = ImportService(db, parsers=[_FakeParser(batch1)])
    await svc.import_file(file_path=_FAKE_PATH, account_id=account.id, user_id=user.id)

    # Second import: p1 and p2 are duplicates; p3 is new
    batch2 = [_ptx(account.id, seed="p1"), _ptx(account.id, seed="p2"), _ptx(account.id, seed="p3")]
    svc2 = ImportService(db, parsers=[_FakeParser(batch2)])
    result = await svc2.import_file(
        file_path=_FAKE_PATH, account_id=account.id, user_id=user.id
    )

    assert result.added == 1
    assert result.skipped == 2


# ---------------------------------------------------------------------------
# Categorisation
# ---------------------------------------------------------------------------


async def test_import_applies_matching_rule(db: AsyncSession) -> None:
    """When a rule matches, category and subcategory are stored on the transaction."""
    user = await _make_user(db, "rule_match@example.com")
    account = await _make_account(db, user.id)

    rule = CategorizationRule(
        user_id=user.id,
        pattern="ESSELUNGA",
        pattern_type="contains",
        category="Groceries",
        subcategory="Supermarket",
        priority=10,
        enabled=True,
        created_at=_now(),
    )
    db.add(rule)
    await db.commit()

    txns = [_ptx(account.id, merchant_clean="ESSELUNGA MILAN", seed="ess1")]
    svc = ImportService(db, parsers=[_FakeParser(txns)])
    await svc.import_file(file_path=_FAKE_PATH, account_id=account.id, user_id=user.id)

    row = (
        await db.execute(
            select(Transaction).where(Transaction.account_id == account.id)
        )
    ).scalar_one()
    assert row.category == "Groceries"
    assert row.subcategory == "Supermarket"


async def test_import_no_rule_match_increments_needs_review(db: AsyncSession) -> None:
    user = await _make_user(db, "no_rule@example.com")
    account = await _make_account(db, user.id)
    txns = [_ptx(account.id, merchant_clean="UNKNOWN MERCHANT", seed="unk1")]
    svc = ImportService(db, parsers=[_FakeParser(txns)])

    result = await svc.import_file(
        file_path=_FAKE_PATH, account_id=account.id, user_id=user.id
    )

    assert result.needs_review == 1


async def test_import_no_rule_match_leaves_category_null(db: AsyncSession) -> None:
    user = await _make_user(db, "null_cat@example.com")
    account = await _make_account(db, user.id)
    txns = [_ptx(account.id, seed="nc1")]
    svc = ImportService(db, parsers=[_FakeParser(txns)])
    await svc.import_file(file_path=_FAKE_PATH, account_id=account.id, user_id=user.id)

    row = (
        await db.execute(
            select(Transaction).where(Transaction.account_id == account.id)
        )
    ).scalar_one()
    assert row.category is None
    assert row.subcategory is None


async def test_import_prefers_merchant_clean_over_description_raw(db: AsyncSession) -> None:
    """Rules must be applied against merchant_clean when present."""
    user = await _make_user(db, "merchant_pref@example.com")
    account = await _make_account(db, user.id)

    rule = CategorizationRule(
        user_id=user.id,
        pattern="ILIAD",
        pattern_type="contains",
        category="Utilities",
        subcategory=None,
        priority=5,
        enabled=True,
        created_at=_now(),
    )
    db.add(rule)
    await db.commit()

    # description_raw does NOT contain "ILIAD"; merchant_clean does
    txn = _ptx(
        account.id,
        description_raw="Addebito SDD - some long description without the keyword",
        merchant_clean="ILIAD",
        seed="mp1",
    )
    svc = ImportService(db, parsers=[_FakeParser([txn])])
    result = await svc.import_file(
        file_path=_FAKE_PATH, account_id=account.id, user_id=user.id
    )

    assert result.needs_review == 0
    row = (
        await db.execute(
            select(Transaction).where(Transaction.account_id == account.id)
        )
    ).scalar_one()
    assert row.category == "Utilities"


async def test_import_falls_back_to_description_raw_when_no_merchant(
    db: AsyncSession,
) -> None:
    """When merchant_clean is None, rules are applied against description_raw."""
    user = await _make_user(db, "desc_fallback@example.com")
    account = await _make_account(db, user.id)

    rule = CategorizationRule(
        user_id=user.id,
        pattern="Stipendio",
        pattern_type="contains",
        category="Income",
        subcategory=None,
        priority=5,
        enabled=True,
        created_at=_now(),
    )
    db.add(rule)
    await db.commit()

    txn = _ptx(
        account.id,
        description_raw="Stipendio - RIF:12345ORD. ACME S.R.L. ACCREDITO",
        merchant_clean=None,
        seed="df1",
    )
    svc = ImportService(db, parsers=[_FakeParser([txn])])
    result = await svc.import_file(
        file_path=_FAKE_PATH, account_id=account.id, user_id=user.id
    )

    assert result.needs_review == 0
    row = (
        await db.execute(
            select(Transaction).where(Transaction.account_id == account.id)
        )
    ).scalar_one()
    assert row.category == "Income"


# ---------------------------------------------------------------------------
# Audit log
# ---------------------------------------------------------------------------


async def test_import_writes_audit_log(db: AsyncSession) -> None:
    user = await _make_user(db, "imp_audit@example.com")
    account = await _make_account(db, user.id)
    svc = ImportService(db, parsers=[_FakeParser([_ptx(account.id, seed="al1")])])

    await svc.import_file(file_path=_FAKE_PATH, account_id=account.id, user_id=user.id)

    logs = (
        await db.execute(
            select(AuditLog).where(AuditLog.actor_user_id == user.id)
        )
    ).scalars().all()
    assert any(log.action == "import" and log.entity_type == "account" for log in logs)


async def test_import_audit_log_contains_summary(db: AsyncSession) -> None:
    user = await _make_user(db, "audit_summary@example.com")
    account = await _make_account(db, user.id)
    txns = [_ptx(account.id, seed="as1"), _ptx(account.id, seed="as2")]
    svc = ImportService(db, parsers=[_FakeParser(txns)])

    await svc.import_file(file_path=_FAKE_PATH, account_id=account.id, user_id=user.id)

    log = (
        await db.execute(
            select(AuditLog)
            .where(AuditLog.actor_user_id == user.id)
            .where(AuditLog.action == "import")
        )
    ).scalar_one()
    assert log.after_state is not None
    assert log.after_state["added"] == 2
    assert log.after_state["skipped"] == 0
    assert log.after_state["parser"] == "TestBank"


# ---------------------------------------------------------------------------
# user_id isolation
# ---------------------------------------------------------------------------


async def test_import_sets_user_id_on_transactions(db: AsyncSession) -> None:
    user = await _make_user(db, "uid@example.com")
    account = await _make_account(db, user.id)
    txns = [_ptx(account.id, seed="uid1"), _ptx(account.id, seed="uid2")]
    svc = ImportService(db, parsers=[_FakeParser(txns)])

    await svc.import_file(file_path=_FAKE_PATH, account_id=account.id, user_id=user.id)

    rows = (
        await db.execute(
            select(Transaction).where(Transaction.account_id == account.id)
        )
    ).scalars().all()
    assert all(r.user_id == user.id for r in rows)
