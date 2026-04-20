"""Dashboard API — monthly spending aggregates."""

import re
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from bilancio.auth.dependencies import get_current_user
from bilancio.services.dashboard_service import DashboardService
from bilancio.storage.database import get_db
from bilancio.storage.models import User

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

_MONTH_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


# ------------------------------------------------------------------
# Pydantic schemas
# ------------------------------------------------------------------


class CategorySpendRead(BaseModel):
    category: str
    amount: float
    pct: float


class MerchantSpendRead(BaseModel):
    merchant: str
    amount: float
    count: int


class DashboardRead(BaseModel):
    month: str
    total_in: float
    total_out: float
    net: float
    category_breakdown: list[CategorySpendRead]
    top_merchants: list[MerchantSpendRead]
    needs_review_count: int


# ------------------------------------------------------------------
# Route
# ------------------------------------------------------------------


@router.get("", response_model=DashboardRead)
async def get_dashboard(
    month: str = Query(default="", description="YYYY-MM; defaults to current month"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DashboardRead:
    """Return spending aggregates for the given month.

    Transfers (is_transfer=true) are excluded from all figures.
    """
    if not month:
        now = datetime.now(UTC)
        month = f"{now.year}-{now.month:02d}"

    if not _MONTH_RE.match(month):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="month must be YYYY-MM (e.g. 2026-03)",
        )

    svc = DashboardService(db)
    summary = await svc.get_summary(user_id=current_user.id, month=month)

    return DashboardRead(
        month=summary.month,
        total_in=summary.total_in,
        total_out=summary.total_out,
        net=summary.net,
        category_breakdown=[
            CategorySpendRead(category=c.category, amount=c.amount, pct=c.pct)
            for c in summary.category_breakdown
        ],
        top_merchants=[
            MerchantSpendRead(merchant=m.merchant, amount=m.amount, count=m.count)
            for m in summary.top_merchants
        ],
        needs_review_count=summary.needs_review_count,
    )
