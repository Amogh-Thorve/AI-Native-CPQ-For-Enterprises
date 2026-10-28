from decimal import Decimal
from typing import Optional, Tuple

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.domains.customer.models import CustomerAddress
from backend.app.domains.tax.models import TaxRate


async def resolve_tax_rate(db: AsyncSession, customer_id: int) -> Tuple[Optional[Decimal], Optional[str]]:
    """
    Picks the tax rate for a customer: country+region match, then country match, then the default rate.
    Returns (None, None) when no rate applies.
    """
    address = (await db.execute(
        select(CustomerAddress).where(CustomerAddress.customer_id == customer_id)
        .order_by(CustomerAddress.is_primary.desc(), CustomerAddress.id)
    )).scalars().first()

    rates = list((await db.execute(select(TaxRate).where(TaxRate.is_active.is_(True)))).scalars().all())
    if not rates:
        return None, None

    def norm(v: Optional[str]) -> str:
        return (v or "").strip().lower()

    if address:
        country, region = norm(address.country), norm(address.state)
        for r in rates:
            if norm(r.country) == country and r.region and norm(r.region) == region:
                return r.rate_percent, r.name
        for r in rates:
            if norm(r.country) == country and not r.region:
                return r.rate_percent, r.name
    for r in rates:
        if r.is_default:
            return r.rate_percent, r.name
    return None, None


def compute_tax(taxable_amount: Decimal, rate: Optional[Decimal]) -> Decimal:
    if not rate or taxable_amount <= 0:
        return Decimal("0.00")
    return (taxable_amount * rate / Decimal("100")).quantize(Decimal("0.01"))
