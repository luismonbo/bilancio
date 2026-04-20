"""DashboardService — monthly spending aggregates."""

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bilancio.storage.models import Transaction


@dataclass
class CategorySpend:
    category: str
    amount: float   # sum of outflows; negative value
    pct: float      # percentage of total_out (0–100)


@dataclass
class MerchantSpend:
    merchant: str
    amount: float   # sum of outflows; negative value
    count: int


@dataclass
class DashboardSummary:
    month: str                           # "YYYY-MM"
    total_in: float                      # sum of positive amounts
    total_out: float                     # sum of negative amounts (negative)
    net: float                           # total_in + total_out
    category_breakdown: list[CategorySpend]   # sorted by abs(amount) desc
    top_merchants: list[MerchantSpend]   # top 10 by abs(amount)
    needs_review_count: int              # is_transfer=False AND category IS NULL


class DashboardService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_summary(self, *, user_id: int, month: str) -> DashboardSummary:
        """Return aggregated spending for the given month (YYYY-MM).

        Excludes transfers (is_transfer=True) from all aggregates.
        """
        year, mon = (int(p) for p in month.split("-"))
        month_start = datetime(year, mon, 1, tzinfo=UTC)
        next_start = (
            datetime(year + 1, 1, 1, tzinfo=UTC)
            if mon == 12
            else datetime(year, mon + 1, 1, tzinfo=UTC)
        )

        stmt = (
            select(Transaction)
            .where(Transaction.user_id == user_id)
            .where(Transaction.is_transfer.is_(False))
            .where(Transaction.value_date >= month_start)
            .where(Transaction.value_date < next_start)
        )
        txs = list((await self._db.execute(stmt)).scalars().all())

        total_in = sum(float(t.amount) for t in txs if float(t.amount) > 0)
        total_out = sum(float(t.amount) for t in txs if float(t.amount) < 0)
        net = total_in + total_out

        category_breakdown = _category_breakdown(txs, total_out)
        top_merchants = _top_merchants(txs)
        needs_review_count = sum(1 for t in txs if t.category is None)

        return DashboardSummary(
            month=month,
            total_in=round(total_in, 2),
            total_out=round(total_out, 2),
            net=round(net, 2),
            category_breakdown=category_breakdown,
            top_merchants=top_merchants,
            needs_review_count=needs_review_count,
        )


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _category_breakdown(
    txs: list[Transaction], total_out: float
) -> list[CategorySpend]:
    cat_totals: dict[str, float] = {}
    for t in txs:
        amt = float(t.amount)
        if amt < 0:
            key = t.category or "Uncategorised"
            cat_totals[key] = cat_totals.get(key, 0.0) + amt

    abs_out = abs(total_out) if total_out != 0 else 1.0
    return sorted(
        [
            CategorySpend(
                category=cat,
                amount=round(amt, 2),
                pct=round(abs(amt) / abs_out * 100, 1),
            )
            for cat, amt in cat_totals.items()
        ],
        key=lambda c: abs(c.amount),
        reverse=True,
    )


def _top_merchants(txs: list[Transaction]) -> list[MerchantSpend]:
    merchant_amounts: dict[str, list[float]] = {}
    for t in txs:
        amt = float(t.amount)
        if amt < 0 and t.merchant_clean:
            merchant_amounts.setdefault(t.merchant_clean, []).append(amt)

    return sorted(
        [
            MerchantSpend(
                merchant=m,
                amount=round(sum(amounts), 2),
                count=len(amounts),
            )
            for m, amounts in merchant_amounts.items()
        ],
        key=lambda m: abs(m.amount),
        reverse=True,
    )[:10]
