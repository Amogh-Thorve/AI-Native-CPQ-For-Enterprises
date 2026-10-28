"""
Content hash of a quote, and the metrics the approval rules read from it.

The hash covers what an approver actually reviews: version, customer, currency, every line's product,
quantity, prices, discounts and margin, and the quote totals. A change to any of these changes the hash,
so an approval given for one hash does not carry over to another.
"""
import hashlib
import json
from decimal import Decimal
from typing import Any, Dict, Optional

from backend.app.domains.approval.engine import QuoteMetrics, compute_metrics

_MONEY = Decimal("0.01")


def _m(value: Any) -> str:
    return str((Decimal(value or 0)).quantize(_MONEY))


def _pct(value: Any) -> Optional[str]:
    return None if value is None else str(Decimal(value).quantize(_MONEY))


def canonical_payload(quote) -> Dict[str, Any]:
    lines = sorted(quote.items, key=lambda i: i.id or 0)
    return {
        "version": quote.version,
        "customer_id": quote.customer_id,
        "currency": quote.currency,
        "subtotal": _m(quote.subtotal),
        "discount_amount": _m(quote.discount_amount),
        "tax_amount": _m(quote.tax_amount),
        "total_amount": _m(quote.total_amount),
        "margin_percentage": _pct(quote.margin_percentage),
        "lines": [
            {
                "product_id": i.product_id,
                "billing_type": i.billing_type,
                "quantity": i.quantity,
                "unit_price": _m(i.unit_price),
                "discount_percentage": _pct(i.discount_percentage),
                "discount_amount": _m(i.discount_amount),
                "total_price": _m(i.total_price),
                "margin_amount": None if i.margin_amount is None else _m(i.margin_amount),
            }
            for i in lines
        ],
    }


def snapshot_hash(quote) -> str:
    raw = json.dumps(canonical_payload(quote), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def metrics_for_quote(quote) -> QuoteMetrics:
    margin = None
    if quote.subtotal and quote.subtotal > 0 and quote.margin_percentage is not None:
        margin = Decimal(quote.margin_percentage)
    return compute_metrics(
        subtotal=Decimal(quote.subtotal or 0),
        total=Decimal(quote.total_amount or 0),
        discount_amount=Decimal(quote.discount_amount or 0),
        line_discounts=[Decimal(i.discount_percentage or 0) for i in quote.items],
        margin_percent=margin,
    )
