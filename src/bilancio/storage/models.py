"""SQLAlchemy ORM models.

Invariants (enforced here and in the service layer):
- amount is signed: negative = outflow, positive = inflow.
- (account_id, hash) is unique — imports are idempotent.
- is_transfer = True excludes the row from all spending aggregates.
- value_date is canonical for analysis; booking_date is for reconciliation.
- Every user-owned row carries user_id — no orphan data, no cross-user leakage.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    disabled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    tokens: Mapped[list["ApiToken"]] = relationship(back_populates="user", lazy="selectin")
    accounts: Mapped[list["Account"]] = relationship(back_populates="user")


class ApiToken(Base):
    __tablename__ = "api_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship(back_populates="tokens")

    __table_args__ = (Index("ix_api_tokens_user_id", "user_id"),)


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    bank: Mapped[str] = mapped_column(String(255), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="EUR")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    user: Mapped["User"] = relationship(back_populates="accounts")
    transactions: Mapped[list["Transaction"]] = relationship(back_populates="account")

    __table_args__ = (Index("ix_accounts_user_id", "user_id"),)


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    account_id: Mapped[int] = mapped_column(Integer, ForeignKey("accounts.id"), nullable=False)
    booking_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    value_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # Signed: negative = outflow, positive = inflow
    amount: Mapped[float] = mapped_column(Numeric(precision=18, scale=4), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="EUR")
    transaction_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    description_raw: Mapped[str | None] = mapped_column(Text, nullable=True)
    merchant_clean: Mapped[str | None] = mapped_column(String(500), nullable=True)
    category: Mapped[str | None] = mapped_column(String(255), nullable=True)
    subcategory: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_transfer: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_recurring: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    source_file: Mapped[str | None] = mapped_column(String(500), nullable=True)
    source_row: Mapped[int | None] = mapped_column(Integer, nullable=True)
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # SHA-256 hex digest of (account_id, value_date, amount, description_raw)
    hash: Mapped[str] = mapped_column(String(64), nullable=False)
    user_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    account: Mapped["Account"] = relationship(back_populates="transactions")

    __table_args__ = (
        UniqueConstraint("account_id", "hash", name="uq_transaction_account_hash"),
        Index("ix_transactions_user_id", "user_id"),
        Index("ix_transactions_value_date", "value_date"),
    )


class CategorizationRule(Base):
    __tablename__ = "categorization_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    # pattern_type ∈ {contains, regex, exact, starts_with} — validated at Pydantic layer
    pattern: Mapped[str] = mapped_column(String(500), nullable=False)
    pattern_type: Mapped[str] = mapped_column(String(50), nullable=False)
    category: Mapped[str] = mapped_column(String(255), nullable=False)
    subcategory: Mapped[str | None] = mapped_column(String(255), nullable=True)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # "user" | "agent" — who created the rule
    created_by: Mapped[str | None] = mapped_column(String(100), nullable=True)

    __table_args__ = (Index("ix_categorization_rules_user_id", "user_id"),)


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    parent_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("categories.id"), nullable=True
    )
    color: Mapped[str | None] = mapped_column(String(50), nullable=True)
    icon: Mapped[str | None] = mapped_column(String(100), nullable=True)

    __table_args__ = (Index("ix_categories_user_id", "user_id"),)


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    actor_user_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True
    )  # NULL = system action
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    before_state: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    after_state: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    __table_args__ = (
        Index("ix_audit_log_timestamp", "timestamp"),
        Index("ix_audit_log_actor_user_id", "actor_user_id"),
    )