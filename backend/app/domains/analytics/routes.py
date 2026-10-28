from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.domains.approval.models import ApprovalRequest, ApprovalStatus
from backend.app.domains.auth.dependencies import PermissionChecker
from backend.app.domains.auth.models import User
from backend.app.domains.customer.models import Customer
from backend.app.domains.quotes.models import Quote, QuoteLineItem, QuoteStatus
from backend.app.domains.quotes.services import QuoteService

router = APIRouter(prefix="/analytics", tags=["analytics"])

OPEN_STATES = [QuoteStatus.DRAFT.value, QuoteStatus.SUBMITTED.value, QuoteStatus.APPROVED.value, QuoteStatus.SENT.value]
LOST_STATES = [QuoteStatus.REJECTED.value, QuoteStatus.EXPIRED.value]


class RecentQuote(BaseModel):
    id: int
    quote_number: str
    title: Optional[str]
    customer_name: str
    total_amount: float
    currency: str
    status: str
    created_at: datetime


class MonthPoint(BaseModel):
    month: str  # YYYY-MM
    won_revenue: float
    quotes_created: int


class RankedItem(BaseModel):
    name: str
    value: float


class DashboardResponse(BaseModel):
    won_revenue: float
    won_revenue_this_month: float
    won_revenue_last_month: float
    open_pipeline_value: float
    open_quotes: int
    status_counts: Dict[str, int]
    pending_approvals: int
    win_rate_percent: Optional[float]
    average_margin_percent: Optional[float]
    total_customers: int
    monthly: List[MonthPoint]
    top_products: List[RankedItem]
    top_customers: List[RankedItem]
    recent_quotes: List[RecentQuote]


def _month_key(dt: datetime) -> str:
    return f"{dt.year:04d}-{dt.month:02d}"


@router.get("/dashboard", response_model=DashboardResponse)
async def dashboard(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker("quotes.read")),
):
    """
    Live workspace KPIs computed from the quotes the caller is allowed to see
    (sales reps: their own; managers/executives/admins: everyone's).
    """
    quote_service = QuoteService(db)
    if await quote_service.expire_overdue_quotes():
        await db.commit()

    roles = [r.name for r in current_user.roles]
    perms = {p.name for r in current_user.roles for p in r.permissions}
    org_wide = any(r in roles for r in ["Administrator", "Executive", "Sales Manager"])
    scope = [] if org_wide else [Quote.created_by_id == current_user.id]

    quotes = list((await db.execute(select(Quote).where(*scope).order_by(Quote.created_at.desc()))).scalars().all())
    status_counts: Dict[str, int] = defaultdict(int)
    for q in quotes:
        status_counts[q.status.value if hasattr(q.status, "value") else str(q.status)] += 1

    now = datetime.now(timezone.utc)
    this_m, last_m = _month_key(now), _month_key(_prev_month(now))
    won = [q for q in quotes if str(q.status) == QuoteStatus.ACCEPTED.value]
    won_total = sum((q.total_amount for q in won), Decimal(0))
    open_q = [q for q in quotes if str(q.status) in OPEN_STATES]
    open_total = sum((q.total_amount for q in open_q), Decimal(0))
    lost = sum(1 for q in quotes if str(q.status) in LOST_STATES)
    win_rate = round(len(won) / (len(won) + lost) * 100, 1) if (len(won) + lost) else None

    # last 6 months window
    months: List[str] = []
    y, m = now.year, now.month
    for _ in range(6):
        months.append(f"{y:04d}-{m:02d}")
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    months.reverse()
    won_by_month: Dict[str, Decimal] = defaultdict(Decimal)
    created_by_month: Dict[str, int] = defaultdict(int)
    for q in quotes:
        created_by_month[_month_key(q.created_at)] += 1
    for q in won:
        won_by_month[_month_key(q.updated_at)] += q.total_amount
    monthly = [MonthPoint(month=k, won_revenue=float(won_by_month[k]), quotes_created=created_by_month[k]) for k in months]

    ids = [q.id for q in quotes]
    top_products: List[RankedItem] = []
    top_customers: List[RankedItem] = []
    if ids:
        rows = await db.execute(
            select(QuoteLineItem.product_name, func.sum(QuoteLineItem.total_price))
            .join(Quote, Quote.id == QuoteLineItem.quote_id)
            .where(QuoteLineItem.quote_id.in_(ids), Quote.status.in_(OPEN_STATES + [QuoteStatus.ACCEPTED.value]))
            .group_by(QuoteLineItem.product_name).order_by(func.sum(QuoteLineItem.total_price).desc()).limit(5)
        )
        top_products = [RankedItem(name=n or "Unnamed", value=float(v or 0)) for n, v in rows]
        rows = await db.execute(
            select(Customer.display_name, Customer.legal_name, func.sum(Quote.total_amount))
            .join(Quote, Quote.customer_id == Customer.id)
            .where(Quote.id.in_(ids), Quote.status.in_(OPEN_STATES + [QuoteStatus.ACCEPTED.value]))
            .group_by(Customer.id, Customer.display_name, Customer.legal_name)
            .order_by(func.sum(Quote.total_amount).desc()).limit(5)
        )
        top_customers = [RankedItem(name=d or l, value=float(v or 0)) for d, l, v in rows]

    avg_margin: Optional[float] = None
    if "pricing.margin.view" in perms:
        margins = [q.margin_percentage for q in quotes if q.margin_percentage is not None and str(q.status) in OPEN_STATES + [QuoteStatus.ACCEPTED.value] and q.subtotal > 0]
        if margins:
            avg_margin = round(float(sum(margins) / len(margins)), 1)

    pending = (await db.execute(
        select(func.count()).select_from(ApprovalRequest).where(ApprovalRequest.status == ApprovalStatus.PENDING.value)
    )).scalar() or 0
    if not org_wide:
        pending = (await db.execute(
            select(func.count()).select_from(ApprovalRequest).join(Quote, Quote.id == ApprovalRequest.quote_id)
            .where(ApprovalRequest.status == ApprovalStatus.PENDING.value, Quote.created_by_id == current_user.id)
        )).scalar() or 0

    customer_count = (await db.execute(select(func.count()).select_from(Customer).where(Customer.deleted_at.is_(None)))).scalar() or 0

    recent = [
        RecentQuote(
            id=q.id, quote_number=q.quote_number, title=q.title,
            customer_name=(q.customer.display_name or q.customer.legal_name) if q.customer else f"Customer #{q.customer_id}",
            total_amount=float(q.total_amount), currency=q.currency,
            status=q.status.value if hasattr(q.status, "value") else str(q.status), created_at=q.created_at,
        ) for q in quotes[:8]
    ]

    return DashboardResponse(
        won_revenue=float(won_total),
        won_revenue_this_month=float(won_by_month[this_m]),
        won_revenue_last_month=float(won_by_month[last_m]),
        open_pipeline_value=float(open_total),
        open_quotes=len(open_q),
        status_counts=dict(status_counts),
        pending_approvals=int(pending),
        win_rate_percent=win_rate,
        average_margin_percent=avg_margin,
        total_customers=int(customer_count),
        monthly=monthly,
        top_products=top_products,
        top_customers=top_customers,
        recent_quotes=recent,
    )


def _prev_month(now: datetime) -> datetime:
    return now.replace(year=now.year - 1, month=12, day=1) if now.month == 1 else now.replace(month=now.month - 1, day=1)
