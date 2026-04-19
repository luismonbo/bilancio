"""Transactions API — list, fetch, and manually update transactions."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from bilancio.auth.dependencies import get_current_user
from bilancio.services.transaction_service import TransactionService
from bilancio.storage.database import get_db
from bilancio.storage.models import User

router = APIRouter(prefix="/transactions", tags=["transactions"])


# ------------------------------------------------------------------
# Pydantic schemas
# ------------------------------------------------------------------


class TransactionRead(BaseModel):
    id: int
    user_id: int
    account_id: int
    booking_date: datetime | None
    value_date: datetime
    amount: float
    currency: str
    transaction_type: str | None
    description_raw: str | None
    merchant_clean: str | None
    category: str | None
    subcategory: str | None
    is_transfer: bool
    is_recurring: bool
    source_file: str | None
    source_row: int | None
    imported_at: datetime
    user_notes: str | None

    model_config = {"from_attributes": True}


class TransactionUpdate(BaseModel):
    category: str | None = None
    subcategory: str | None = None
    is_transfer: bool | None = None
    is_recurring: bool | None = None
    user_notes: str | None = None


# ------------------------------------------------------------------
# Routes
# ------------------------------------------------------------------


@router.get("", response_model=list[TransactionRead])
async def list_transactions(
    account_id: int | None = Query(default=None),
    category: str | None = Query(default=None),
    needs_review: bool = Query(default=False),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[TransactionRead]:
    svc = TransactionService(db)
    return await svc.list_transactions(  # type: ignore[return-value]
        user_id=current_user.id,
        account_id=account_id,
        category=category,
        needs_review=needs_review,
        limit=limit,
        offset=offset,
    )


@router.get("/{transaction_id}", response_model=TransactionRead)
async def get_transaction(
    transaction_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TransactionRead:
    svc = TransactionService(db)
    try:
        tx = await svc.get(transaction_id=transaction_id, user_id=current_user.id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found")
    return TransactionRead.model_validate(tx)


@router.patch("/{transaction_id}", response_model=TransactionRead)
async def update_transaction(
    transaction_id: int,
    payload: TransactionUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TransactionRead:
    svc = TransactionService(db)
    try:
        tx = await svc.update(
            transaction_id=transaction_id,
            user_id=current_user.id,
            category=payload.category,
            subcategory=payload.subcategory,
            is_transfer=payload.is_transfer,
            is_recurring=payload.is_recurring,
            user_notes=payload.user_notes,
        )
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found")
    return TransactionRead.model_validate(tx)
