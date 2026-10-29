"""
Ground truth for what a Sales Representative must never be told, from the real cost data behind a quote:
unit and total cost, margin amounts (unit and line), margin percent and markup percent.
"""
from decimal import ROUND_HALF_UP, Decimal
from typing import Iterable, List

from sqlalchemy import select

from backend.app.domains.catalog.models import Product
from backend.app.domains.quotes.models import Quote, QuoteLineItem


def _q2(value) -> Decimal:
    return Decimal(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


async def derived_secrets(db, quote_ids: Iterable[int]) -> List[Decimal]:
    ids = list(quote_ids)
    values = set()
    if not ids:
        return []
    items = (await db.execute(select(QuoteLineItem).where(QuoteLineItem.quote_id.in_(ids)))).scalars().all()
    for item in items:
        product = await db.get(Product, item.product_id)
        if product is None or product.cost_price is None:
            continue
        cost = Decimal(product.cost_price)
        unit_price, total = Decimal(item.unit_price), Decimal(item.total_price)
        line_cost = cost * item.quantity
        margin = total - line_cost
        values |= {_q2(cost), _q2(line_cost), _q2(unit_price - cost), _q2(margin)}
        if total:
            values.add(_q2(margin / total * 100))
        if cost:
            values.add(_q2((unit_price - cost) / cost * 100))  # markup on cost
        for v in (item.margin_amount, item.margin_percentage):
            if v is not None:
                values.add(_q2(v))
    for quote in (await db.execute(select(Quote).where(Quote.id.in_(ids)))).scalars():
        if quote.margin_percentage is not None:
            values.add(_q2(quote.margin_percentage))
    return sorted(v for v in values if v > 0)
