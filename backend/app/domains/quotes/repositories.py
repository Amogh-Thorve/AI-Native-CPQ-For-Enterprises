from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import select, func, or_, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from backend.app.domains.quotes.models import Quote, QuoteLineItem, QuoteAuditLog, QuoteStatus
from backend.app.domains.quotes.schemas import QuoteCreate

class QuoteRepository:
    """
    Handles persistence logic for Quotes, line items, and audit logs.
    """
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, quote_id: int) -> Optional[Quote]:
        result = await self.db.execute(
            select(Quote)
            .where(Quote.id == quote_id)
            .options(
                selectinload(Quote.items).selectinload(QuoteLineItem.product),
                selectinload(Quote.customer),
                selectinload(Quote.created_by),
                selectinload(Quote.audit_logs)
            )
        )
        return result.scalars().first()

    async def get_by_quote_number(self, quote_number: str) -> List[Quote]:
        result = await self.db.execute(
            select(Quote)
            .where(Quote.quote_number == quote_number)
            .order_by(Quote.version.desc())
            .options(
                selectinload(Quote.items).selectinload(QuoteLineItem.product),
                selectinload(Quote.customer),
                selectinload(Quote.created_by),
                selectinload(Quote.audit_logs)
            )
        )
        return list(result.scalars().all())

    async def get_latest_version(self, quote_number: str) -> Optional[Quote]:
        result = await self.db.execute(
            select(Quote)
            .where(Quote.quote_number == quote_number)
            .order_by(Quote.version.desc())
            .options(
                selectinload(Quote.items).selectinload(QuoteLineItem.product),
                selectinload(Quote.customer),
                selectinload(Quote.created_by),
                selectinload(Quote.audit_logs)
            )
            .limit(1)
        )
        return result.scalars().first()

    async def list_quotes(
        self,
        customer_id: Optional[int] = None,
        status: Optional[QuoteStatus] = None,
        search: Optional[str] = None,
        created_by_id: Optional[uuid.UUID] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Quote]:
        query = select(Quote).options(
            selectinload(Quote.items).selectinload(QuoteLineItem.product),
            selectinload(Quote.customer),
            selectinload(Quote.created_by),
            selectinload(Quote.audit_logs)
        )

        if customer_id is not None:
            query = query.where(Quote.customer_id == customer_id)
        if status is not None:
            query = query.where(Quote.status == status)
        if created_by_id is not None:
            query = query.where(Quote.created_by_id == created_by_id)
        if search:
            search_pattern = f"%{search.strip()}%"
            query = query.where(
                or_(
                    Quote.quote_number.ilike(search_pattern),
                    Quote.title.ilike(search_pattern)
                )
            )

        query = query.order_by(Quote.created_at.desc()).limit(limit).offset(offset)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def generate_next_quote_number(self) -> str:
        """
        Generates a unique reference quote number sequence, e.g. QT-100001.
        """
        result = await self.db.execute(select(func.max(Quote.id)))
        max_id = result.scalar() or 0
        return f"QT-{100000 + max_id + 1}"

    async def create(
        self,
        creator_id: uuid.UUID,
        schema: QuoteCreate,
        quote_number: str,
        version: int = 1,
        parent_id: Optional[int] = None
    ) -> Quote:
        db_quote = Quote(
            quote_number=quote_number,
            version=version,
            title=schema.title or f"Quote {quote_number}",
            description=schema.description,
            currency=schema.currency or "USD",
            valid_until=schema.valid_until,
            notes=schema.notes,
            status=QuoteStatus.DRAFT,
            subtotal=Decimal("0.00"),
            discount_amount=Decimal("0.00"),
            tax_amount=Decimal("0.00"),
            total_amount=Decimal("0.00"),
            margin_percentage=Decimal("0.00"),
            customer_id=schema.customer_id,
            price_book_id=schema.price_book_id,
            external_opportunity_id=schema.external_opportunity_id,
            created_by_id=creator_id,
            parent_quote_id=parent_id
        )
        self.db.add(db_quote)
        await self.db.flush()
        return db_quote

    async def update(self, db_quote: Quote, update_data: Dict[str, Any]) -> Quote:
        for field, value in update_data.items():
            if hasattr(db_quote, field):
                setattr(db_quote, field, value)
        self.db.add(db_quote)
        await self.db.flush()
        return db_quote

    async def delete(self, db_quote: Quote) -> None:
        await self.db.delete(db_quote)
        await self.db.flush()

    async def get_line_item(self, item_id: int) -> Optional[QuoteLineItem]:
        result = await self.db.execute(
            select(QuoteLineItem)
            .where(QuoteLineItem.id == item_id)
            .options(selectinload(QuoteLineItem.product))
        )
        return result.scalars().first()

    async def add_line_item(
        self,
        quote_id: int,
        product_id: int,
        product_name: str,
        sku: str,
        billing_type: str,
        currency: str,
        quantity: int,
        unit_price: Decimal,
        discount_percentage: Decimal,
        discount_amount: Decimal,
        total_price: Decimal,
        pricing_method: Optional[str] = None,
        pricing_breakdown: Optional[List[Dict[str, Any]]] = None,
        margin_amount: Optional[Decimal] = None,
        margin_percentage: Optional[Decimal] = None,
        configuration_id: Optional[str] = None,
        configuration_snapshot: Optional[Dict[str, Any]] = None
    ) -> QuoteLineItem:
        db_item = QuoteLineItem(
            quote_id=quote_id,
            product_id=product_id,
            product_name=product_name,
            sku=sku,
            billing_type=billing_type,
            currency=currency,
            quantity=quantity,
            unit_price=unit_price,
            discount_percentage=discount_percentage,
            discount_amount=discount_amount,
            total_price=total_price,
            pricing_method=pricing_method,
            pricing_breakdown=pricing_breakdown,
            margin_amount=margin_amount,
            margin_percentage=margin_percentage,
            configuration_id=configuration_id,
            configuration_snapshot=configuration_snapshot
        )
        self.db.add(db_item)
        await self.db.flush()
        return db_item

    async def update_line_item(self, db_item: QuoteLineItem, update_data: Dict[str, Any]) -> QuoteLineItem:
        for field, value in update_data.items():
            if hasattr(db_item, field):
                setattr(db_item, field, value)
        self.db.add(db_item)
        await self.db.flush()
        return db_item

    async def delete_line_item(self, db_item: QuoteLineItem) -> None:
        await self.db.delete(db_item)
        await self.db.flush()

    async def recalculate_totals(self, quote: Quote) -> Quote:
        """
        Recalculates subtotal, discount, tax, grand total and weighted margin.
        Uses pure Decimal arithmetic.
        """
        items_result = await self.db.execute(
            select(QuoteLineItem).where(QuoteLineItem.quote_id == quote.id)
        )
        items = list(items_result.scalars().all())
        subtotal = sum((item.total_price for item in items), Decimal("0.00"))
        # If quote has custom discount_amount set, preserve it; otherwise can sum line discounts or keep quote discount
        discount_total = quote.discount_amount or Decimal("0.00")
        tax = quote.tax_amount or Decimal("0.00")
        grand_total = subtotal - discount_total + tax
        if grand_total < Decimal("0.00"):
            grand_total = Decimal("0.00")

        quote.subtotal = subtotal
        quote.total_amount = grand_total

        # Calculate weighted average margin percentage if items have margin
        total_revenue = subtotal
        if total_revenue > Decimal("0.00"):
            total_margin_val = sum(((item.margin_amount or Decimal("0.00")) for item in items), Decimal("0.00"))
            quote.margin_percentage = (total_margin_val / total_revenue * Decimal("100.00")).quantize(Decimal("0.01"))
        else:
            quote.margin_percentage = Decimal("0.00")

        await self.db.flush()
        return quote

    async def log_audit(
        self,
        quote_id: int,
        action: str,
        user_id: Optional[uuid.UUID] = None,
        user_role: Optional[str] = None,
        before_value: Optional[Dict[str, Any]] = None,
        after_value: Optional[Dict[str, Any]] = None
    ) -> QuoteAuditLog:
        audit_entry = QuoteAuditLog(
            quote_id=quote_id,
            action=action,
            user_id=user_id,
            user_role=user_role,
            before_value=before_value,
            after_value=after_value,
            timestamp=datetime.now(timezone.utc)
        )
        self.db.add(audit_entry)
        await self.db.flush()
        return audit_entry
