import enum
import uuid
from decimal import Decimal
from datetime import datetime, timezone
from typing import List, Optional, Any, Dict
from sqlalchemy import String, ForeignKey, Numeric, Integer, DateTime, Text, JSON, func, Uuid, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.app.core.database import Base

def utc_now() -> datetime:
    return datetime.now(timezone.utc)

class QuoteStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"

    @classmethod
    def _missing_(cls, value: object):
        # Gracefully handle lowercase database values if any exist
        if isinstance(value, str):
            val_upper = value.upper()
            for member in cls:
                if member.value == val_upper:
                    return member
        return None

class Quote(Base):
    """
    Quote database model representing enterprise sales quotations.
    Maintains revision versions, financial aggregates, lifecycle states,
    and historical customer / pricing snapshots.
    """
    __tablename__ = "quotes"
    __table_args__ = (
        UniqueConstraint('quote_number', 'version', name='uq_quotes_quote_number_version'),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    quote_number: Mapped[str] = mapped_column(String(50), index=True, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[QuoteStatus] = mapped_column(String(50), default=QuoteStatus.DRAFT, nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="USD", nullable=False)
    valid_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Financial Aggregates (Pure Decimal / PostgreSQL NUMERIC)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    margin_percentage: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False)
    created_by_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False)
    price_book_id: Mapped[Optional[int]] = mapped_column(ForeignKey("price_books.id"), nullable=True)
    
    # Salesforce Opportunity ID mapping
    external_opportunity_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    # Salesforce Quote ID mapping
    external_crm_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    parent_quote_id: Mapped[Optional[int]] = mapped_column(ForeignKey("quotes.id", ondelete="SET NULL"), nullable=True)

    # Relationships
    customer: Mapped["Customer"] = relationship("Customer", lazy="selectin")
    created_by: Mapped["User"] = relationship("User", lazy="selectin")
    items: Mapped[List["QuoteLineItem"]] = relationship(
        back_populates="quote",
        cascade="all, delete-orphan",
        order_by="QuoteLineItem.id",
        lazy="selectin"
    )
    parent_quote: Mapped[Optional["Quote"]] = relationship("Quote", remote_side=[id], lazy="selectin")
    audit_logs: Mapped[List["QuoteAuditLog"]] = relationship(
        back_populates="quote",
        cascade="all, delete-orphan",
        order_by="QuoteAuditLog.timestamp.desc()",
        lazy="selectin"
    )

class QuoteLineItem(Base):
    """
    QuoteLineItem database model representing line configuration items.
    Saves negotiated rates, discounts, quantities, cost configurations,
    and a frozen snapshot of Pricing Engine breakdowns and Configuration sessions.
    """
    __tablename__ = "quote_line_items"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    quote_id: Mapped[int] = mapped_column(ForeignKey("quotes.id", ondelete="CASCADE"), nullable=False)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    
    # Historical catalog snapshot (frozen at quote save time)
    product_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    sku: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    billing_type: Mapped[str] = mapped_column(String(50), default="MRC", nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="USD", nullable=False)

    # Configuration Engine Integration Snapshot
    configuration_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    configuration_snapshot: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)

    # Quantity and Pricing Calculations
    quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    discount_percentage: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("0.00"), nullable=False)
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    total_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    # Pricing Engine Snapshot (breakdown waterfall & method)
    pricing_method: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    pricing_breakdown: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(JSON, nullable=True)
    
    # Financial metrics
    margin_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    margin_percentage: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2), nullable=True)

    quote: Mapped["Quote"] = relationship(back_populates="items")
    product: Mapped["Product"] = relationship("Product", lazy="selectin")

class QuoteAuditLog(Base):
    """
    Audit log tracking all critical Quote mutations:
    QUOTE_CREATED, QUOTE_UPDATED, QUOTE_ITEM_ADDED, QUOTE_ITEM_UPDATED,
    QUOTE_ITEM_REMOVED, QUOTE_SUBMITTED, QUOTE_CANCELLED.
    """
    __tablename__ = "quote_audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    quote_id: Mapped[int] = mapped_column(ForeignKey("quotes.id", ondelete="CASCADE"), index=True, nullable=False)
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid, ForeignKey("users.id"), nullable=True)
    user_role: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    action: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    before_value: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    after_value: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    quote: Mapped["Quote"] = relationship(back_populates="audit_logs")
    user: Mapped[Optional["User"]] = relationship("User", lazy="selectin")
