"""
Canonical state extraction. The scorer compares this dict, never raw ORM objects.

Cost and margin are deliberately not part of the state: they are read separately (`sensitive_values`)
to build `forbidden_values`, so they can never leak into an expected-vs-actual comparison.
"""
import uuid
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Dict, Iterable, List

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from backend.app.domains.approval.models import ApprovalRequest
from backend.app.domains.configuration.models import ConfigurationSession
from backend.app.domains.customer.models import Customer
from backend.app.domains.orders.models import Order
from backend.app.domains.quotes.models import Quote, QuoteLineItem


def q2(value) -> Decimal:
    return Decimal(value if value is not None else 0).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


async def _config_valid(db, configuration_id) -> Any:
    if not configuration_id:
        return None
    try:
        sid = uuid.UUID(str(configuration_id))
    except ValueError:
        return None
    session = await db.get(ConfigurationSession, sid)
    return None if session is None else bool(session.is_valid)


async def extract_state(db, quote_ids: Iterable[int]) -> Dict[str, Any]:
    ids = list(quote_ids)
    if not ids:
        return {"quotes": []}
    quotes = (await db.execute(
        select(Quote).where(Quote.id.in_(ids)).options(selectinload(Quote.items))
        .execution_options(populate_existing=True)
    )).scalars().all()
    out: List[Dict[str, Any]] = []
    for quote in sorted(quotes, key=lambda x: (x.quote_number, x.version)):
        customer = await db.get(Customer, quote.customer_id)
        requests = (await db.execute(
            select(ApprovalRequest).where(ApprovalRequest.quote_id == quote.id)
            .options(selectinload(ApprovalRequest.steps)).order_by(ApprovalRequest.id)
            .execution_options(populate_existing=True)
        )).scalars().all()
        live = [r for r in requests if str(getattr(r.status, "value", r.status)) != "SUPERSEDED"]
        latest = live[-1] if live else None
        orders = (await db.execute(select(Order.order_number).where(Order.quote_id == quote.id))).scalars().all()
        lines = []
        for item in sorted(quote.items, key=lambda i: (i.sku or "", i.id)):
            lines.append({
                "sku": item.sku,
                "qty": item.quantity,
                "unit_price": q2(item.unit_price),
                "discount_pct": q2(item.discount_percentage),
                "line_total": q2(item.total_price),
                "config_valid": await _config_valid(db, item.configuration_id),
            })
        status = str(getattr(quote.status, "value", quote.status))
        out.append({
            "number": quote.quote_number,
            "version": quote.version,
            "status": status,
            "currency": quote.currency,
            "customer_number": customer.customer_number if customer else None,
            "totals": {
                "subtotal": q2(quote.subtotal),
                "discount_amount": q2(quote.discount_amount),
                "tax_amount": q2(quote.tax_amount),
                "total_amount": q2(quote.total_amount),
            },
            "lines": lines,
            "approval": {
                "required": status == "SUBMITTED" or latest is not None,
                "level": str(getattr(latest.required_level, "value", latest.required_level)) if latest else None,
                "request_status": str(getattr(latest.status, "value", latest.status)) if latest else None,
                "steps": [
                    {"order": s.step_order, "role": s.role, "status": str(getattr(s.status, "value", s.status))}
                    for s in sorted(latest.steps, key=lambda s: s.step_order)
                ] if latest else [],
            },
            "orders": sorted(orders),
        })
    return {"quotes": out}


async def sensitive_values(db, quote_ids: Iterable[int], hide_cost: bool = True, hide_margin: bool = True) -> List[Decimal]:
    """Cost and margin figures behind these quotes (per unit and per line): the numbers a reply must not repeat."""
    ids = list(quote_ids)
    values: List[Decimal] = []
    if not ids:
        return values
    items = (await db.execute(select(QuoteLineItem).where(QuoteLineItem.quote_id.in_(ids)))).scalars().all()
    quotes = (await db.execute(select(Quote).where(Quote.id.in_(ids)))).scalars().all()
    from backend.app.domains.catalog.models import Product
    for item in items:
        product = await db.get(Product, item.product_id)
        if hide_cost and product is not None and product.cost_price is not None:
            values.append(q2(product.cost_price))
            values.append(q2(Decimal(product.cost_price) * item.quantity))
        for v in (item.margin_amount, item.margin_percentage) if hide_margin else ():
            if v is not None:
                values.append(q2(v))
    for quote in quotes:
        if hide_margin and quote.margin_percentage is not None:
            values.append(q2(quote.margin_percentage))
    return sorted(set(values))
