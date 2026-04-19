"""ImportService — bank-file import pipeline.

Pipeline per file:
  1. Auto-detect the correct parser from the registry.
  2. Parse all transactions from the file (parser is pure / stateless).
  3. Load the user's enabled categorization rules.
  4. For each ParsedTransaction:
       a. Skip if (account_id, hash) already exists in the DB.
       b. Run the rules engine against merchant_clean (or description_raw).
       c. Persist a Transaction row with the matched category (or None).
  5. Write one AuditLog row summarising the import.
  6. Return ImportSummary(added, skipped, needs_review).

Only ImportService and API routes may call this service's write methods.
Every import writes an audit_log row — no exceptions.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bilancio.categorizer.rules_engine import apply_rules
from bilancio.parsers.base import BankParser
from bilancio.storage.models import AuditLog, CategorizationRule, Transaction


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class ImportSummary:
    """Counts returned after a successful import run."""

    added: int
    skipped: int       # duplicate (account_id, hash) already present
    needs_review: int  # added but no categorization rule matched


class ImportService:
    def __init__(
        self,
        db: AsyncSession,
        parsers: list[BankParser] | None = None,
    ) -> None:
        self._db = db
        if parsers is not None:
            self._parsers: list[BankParser] = parsers
        else:
            from bilancio.parsers.registry import default_parsers
            self._parsers = default_parsers()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def import_file(
        self,
        *,
        file_path: Path,
        account_id: int,
        user_id: int,
    ) -> ImportSummary:
        """Run the full import pipeline for one bank export file.

        Raises ValueError if no registered parser recognises the file.
        Commits a single transaction covering all new rows + the audit entry.
        """
        parser = self._detect_parser(file_path)
        if parser is None:
            raise ValueError(
                f"No parser found for file: {file_path.name!r}. "
                "Register a new BankParser in bilancio.parsers.registry."
            )

        parsed = parser.parse(file_path, account_id)
        rules = await self._load_rules(user_id)

        added = 0
        skipped = 0
        needs_review = 0
        now = _now()

        for ptx in parsed:
            if await self._is_duplicate(account_id, ptx.hash):
                skipped += 1
                continue

            text = ptx.merchant_clean or ptx.description_raw or ""
            match = apply_rules(text, rules)

            if match is None:
                needs_review += 1

            self._db.add(
                Transaction(
                    user_id=user_id,
                    account_id=account_id,
                    booking_date=ptx.booking_date,
                    value_date=ptx.value_date,
                    amount=ptx.amount,
                    currency=ptx.currency,
                    transaction_type=ptx.transaction_type,
                    description_raw=ptx.description_raw,
                    merchant_clean=ptx.merchant_clean,
                    category=match.category if match else None,
                    subcategory=match.subcategory if match else None,
                    is_transfer=False,
                    is_recurring=False,
                    source_file=ptx.source_file,
                    source_row=ptx.source_row,
                    imported_at=now,
                    hash=ptx.hash,
                )
            )
            added += 1

        # Flush to populate IDs before writing the audit entry.
        await self._db.flush()

        self._db.add(
            AuditLog(
                timestamp=now,
                actor_user_id=user_id,
                action="import",
                entity_type="account",
                entity_id=account_id,
                before_state=None,
                after_state={
                    "file": str(file_path),
                    "parser": parser.bank_name,
                    "added": added,
                    "skipped": skipped,
                    "needs_review": needs_review,
                },
            )
        )
        await self._db.commit()

        return ImportSummary(added=added, skipped=skipped, needs_review=needs_review)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _detect_parser(self, file_path: Path) -> BankParser | None:
        for parser in self._parsers:
            if parser.detect(file_path):
                return parser
        return None

    async def _load_rules(self, user_id: int) -> list[CategorizationRule]:
        result = await self._db.execute(
            select(CategorizationRule)
            .where(CategorizationRule.user_id == user_id)
            .where(CategorizationRule.enabled.is_(True))
        )
        return list(result.scalars().all())

    async def _is_duplicate(self, account_id: int, hash_: str) -> bool:
        result = await self._db.execute(
            select(Transaction.id)
            .where(Transaction.account_id == account_id)
            .where(Transaction.hash == hash_)
        )
        return result.scalar_one_or_none() is not None
