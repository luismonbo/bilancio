"""AccountService — CRUD for bank accounts.

Every mutation writes a row to audit_log.
"""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bilancio.storage.models import Account, AuditLog


def _now() -> datetime:
    return datetime.now(UTC)


def _account_snapshot(account: Account) -> dict[str, Any]:
    return {
        "name": account.name,
        "bank": account.bank,
        "currency": account.currency,
    }


class AccountService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    async def list_accounts(self, user_id: int) -> list[Account]:
        """Return all accounts for a user, ordered by name."""
        result = await self._db.execute(
            select(Account).where(Account.user_id == user_id).order_by(Account.name)
        )
        return list(result.scalars().all())

    async def get(self, *, account_id: int, user_id: int) -> Account:
        """Return a single account. Raises ValueError if not found or not owned."""
        result = await self._db.execute(
            select(Account)
            .where(Account.id == account_id)
            .where(Account.user_id == user_id)
        )
        account = result.scalar_one_or_none()
        if account is None:
            raise ValueError(f"Account {account_id} not found")
        return account

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    async def create(
        self,
        *,
        user_id: int,
        name: str,
        bank: str,
        currency: str = "EUR",
    ) -> Account:
        account = Account(
            user_id=user_id,
            name=name,
            bank=bank,
            currency=currency,
            created_at=_now(),
        )
        self._db.add(account)
        await self._db.flush()

        self._db.add(
            AuditLog(
                timestamp=_now(),
                actor_user_id=user_id,
                action="create",
                entity_type="account",
                entity_id=account.id,
                before_state=None,
                after_state=_account_snapshot(account),
            )
        )
        await self._db.commit()
        await self._db.refresh(account)
        return account

    async def delete(self, *, account_id: int, user_id: int) -> None:
        account = await self.get(account_id=account_id, user_id=user_id)
        before = _account_snapshot(account)

        self._db.add(
            AuditLog(
                timestamp=_now(),
                actor_user_id=user_id,
                action="delete",
                entity_type="account",
                entity_id=account.id,
                before_state=before,
                after_state=None,
            )
        )
        await self._db.delete(account)
        await self._db.commit()
