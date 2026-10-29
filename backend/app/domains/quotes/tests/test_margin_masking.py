from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace as NS
import uuid

from backend.app.domains.quotes.routes import _can_view_margin, _mask_quote
from backend.app.domains.quotes.models import QuoteStatus


def _user(*perms):
    return NS(roles=[NS(permissions=[NS(name=p) for p in perms])])


def _quote():
    now = datetime.now(timezone.utc)
    item = NS(
        id=1, quote_id=1, product_id=1, quantity=2, discount_percentage=Decimal("0"),
        unit_price=Decimal("100"), discount_amount=Decimal("0"), total_price=Decimal("200"),
        margin_amount=Decimal("80"), margin_percentage=Decimal("40"),
        configuration_id=None, configuration_snapshot=None, product_name="P", sku="S",
        billing_type="MRC", currency="USD", pricing_method=None, pricing_breakdown=None,
    )
    return NS(
        id=1, quote_number="Q-1", version=1, status=QuoteStatus.DRAFT, customer_id=1, title=None,
        description=None, currency="USD", valid_until=None, notes=None, price_book_id=None,
        external_opportunity_id=None, subtotal=Decimal("200"), discount_amount=Decimal("0"),
        tax_amount=Decimal("0"), total_amount=Decimal("200"), margin_percentage=Decimal("40"),
        created_by_id=uuid.uuid4(), created_by=None, customer=None, created_at=now, updated_at=now,
        parent_quote_id=None, tax_rate_percent=None, tax_label=None, share_token=None,
        customer_response_name=None, customer_response_note=None, customer_responded_at=None,
        items=[item], audit_logs=[],
    )


def test_rep_without_permission_gets_null_margin():
    out = _mask_quote(_quote(), _can_view_margin(_user("quotes.read")))
    assert out.margin_percentage is None
    assert out.items[0].margin_amount is None and out.items[0].margin_percentage is None
    assert out.total_amount == Decimal("200")


def test_user_with_permission_sees_margin():
    out = _mask_quote(_quote(), _can_view_margin(_user("pricing.margin.view")))
    assert out.margin_percentage == Decimal("40")
    assert out.items[0].margin_amount == Decimal("80")
