"""Accounts API — CRUD for bank accounts."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from bilancio.auth.dependencies import get_current_user
from bilancio.services.account_service import AccountService
from bilancio.storage.database import get_db
from bilancio.storage.models import User

router = APIRouter(prefix="/accounts", tags=["accounts"])


# ------------------------------------------------------------------
# Pydantic schemas
# ------------------------------------------------------------------


class AccountCreate(BaseModel):
    name: str
    bank: str
    currency: str = "EUR"


class AccountRead(BaseModel):
    id: int
    user_id: int
    name: str
    bank: str
    currency: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ------------------------------------------------------------------
# Routes
# ------------------------------------------------------------------


@router.get("", response_model=list[AccountRead])
async def list_accounts(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[AccountRead]:
    svc = AccountService(db)
    return await svc.list_accounts(user_id=current_user.id)  # type: ignore[return-value]


@router.post("", response_model=AccountRead, status_code=status.HTTP_201_CREATED)
async def create_account(
    payload: AccountCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AccountRead:
    svc = AccountService(db)
    account = await svc.create(
        user_id=current_user.id,
        name=payload.name,
        bank=payload.bank,
        currency=payload.currency,
    )
    return AccountRead.model_validate(account)


@router.get("/{account_id}", response_model=AccountRead)
async def get_account(
    account_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AccountRead:
    svc = AccountService(db)
    try:
        account = await svc.get(account_id=account_id, user_id=current_user.id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Account not found"
        ) from None
    return AccountRead.model_validate(account)


@router.delete("/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_account(
    account_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    svc = AccountService(db)
    try:
        await svc.delete(account_id=account_id, user_id=current_user.id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Account not found"
        ) from None
