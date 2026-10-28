from decimal import Decimal
from typing import Optional
from sqlalchemy import Boolean, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column
from backend.app.core.database import Base


class TaxRate(Base):
    """
    Sales tax / VAT rate. Matched to a quote through the customer address:
    country + region (most specific) > country only > default rate.
    """
    __tablename__ = "tax_rates"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    country: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    region: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    rate_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
