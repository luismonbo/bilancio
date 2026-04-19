"""BankParser Protocol — every parser must implement this interface.

Adding a new bank = one new file in this directory + at least one fixture test.
No bank-specific logic belongs outside its own module.
"""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Protocol, runtime_checkable


@dataclass
class ParsedTransaction:
    """Bank-parser output. User-agnostic — ImportService assigns user_id."""

    account_id: int
    booking_date: datetime | None
    value_date: datetime
    # Signed: negative = outflow, positive = inflow
    amount: float
    currency: str
    transaction_type: str | None
    description_raw: str
    merchant_clean: str | None
    source_file: str
    source_row: int
    # SHA-256 hex of (value_date, amount, description_raw) — stable across re-uploads
    hash: str


@runtime_checkable
class BankParser(Protocol):
    bank_name: str

    def detect(self, file_path: Path) -> bool:
        """Return True if this parser can handle the given file."""
        ...

    def parse(self, file_path: Path, account_id: int) -> list[ParsedTransaction]:
        """Parse the file and return a list of transactions (not yet saved to DB)."""
        ...
