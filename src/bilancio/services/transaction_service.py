"""TransactionService — query and manual-update operations on transactions.

Imports are handled by ImportService. This service covers post-import
operations: filtering the list, fetching a single row, and manual edits
(e.g. re-categorising, marking as transfer, adding notes).

Every mutation writes a row to audit_log.
"""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bilancio.storage.models import AuditLog, Transaction


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _transaction_snapshot(tx: Transaction) -> dict:
    return {
        "category": tx.category,
        "subcategory": tx.subcategory,
        "is_transfer": tx.is_transfer,
        "is_recurring": tx.is_recurring,
        "user_notes": tx.user_notes,
    }


class TransactionService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    async def list_transactions(
        self,
        user_id: int,
        *,
        account_id: int | None = None,
        category: str | None = None,
        needs_review: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Transaction]:
        """Return transactions for the user with optional filters.

        needs_review=True returns only rows where category IS NULL.
        Results are ordered by value_date descending (most recent first).
        """
        stmt = (
            select(Transaction)
            .where(Transaction.user_id == user_id)
            .order_by(Transaction.value_date.desc())
            .limit(limit)
            .offset(offset)
        )
        if account_id is not None:
            stmt = stmt.where(Transaction.account_id == account_id)
        if category is not None:
            stmt = stmt.where(Transaction.category == category)
        if needs_review:
            stmt = stmt.where(Transaction.category.is_(None))

        result = await self._db.execute(stmt)
        return list(result.scalars().all())

    async def get(self, *, transaction_id: int, user_id: int) -> Transaction:
        """Return a single transaction. Raises ValueError if not found or not owned."""
        result = await self._db.execute(
            select(Transaction)
            .where(Transaction.id == transaction_id)
            .where(Transaction.user_id == user_id)
        )
        tx = result.scalar_one_or_none()
        if tx is None:
            raise ValueError(f"Transaction {transaction_id} not found")
        return tx

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    async def update(
        self,
        *,
        transaction_id: int,
        user_id: int,
        category: str | None = None,
        subcategory: str | None = None,
        is_transfer: bool | None = None,
        is_recurring: bool | None = None,
        user_notes: str | None = None,
    ) -> Transaction:
        """Manually update mutable fields on a transaction."""
        tx = await self.get(transaction_id=transaction_id, user_id=user_id)
        before = _transaction_snapshot(tx)

        if category is not None:
            tx.category = category
        if subcategory is not None:
            tx.subcategory = subcategory
        if is_transfer is not None:
            tx.is_transfer = is_transfer
        if is_recurring is not None:
            tx.is_recurring = is_recurring
        if user_notes is not None:
            tx.user_notes = user_notes

        self._db.add(AuditLog(
            timestamp=_now(),
            actor_user_id=user_id,
            action="update",
            entity_type="transaction",
            entity_id=tx.id,
            before_state=before,
            after_state=_transaction_snapshot(tx),
        ))
        await self._db.commit()
        await self._db.refresh(tx)
        return tx
