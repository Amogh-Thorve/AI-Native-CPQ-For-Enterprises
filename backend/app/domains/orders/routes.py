import uuid
from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, ConfigDict, field_serializer
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.core.exceptions import DomainValidationError, EntityNotFoundError
from backend.app.domains.auth.dependencies import PermissionChecker
from backend.app.domains.auth.models import User
from backend.app.domains.orders.models import Order, OrderLine, OrderStatus
from backend.app.domains.quotes.models import QuoteStatus
from backend.app.domains.quotes.services import QuoteService

router = APIRouter(prefix="/orders", tags=["orders"])

TRANSITIONS = {
    OrderStatus.PENDING.value: {OrderStatus.CONFIRMED.value, OrderStatus.CANCELLED.value},
    OrderStatus.CONFIRMED.value: {OrderStatus.FULFILLED.value, OrderStatus.CANCELLED.value},
    OrderStatus.FULFILLED.value: set(),
    OrderStatus.CANCELLED.value: set(),
}


class OrderLineRead(BaseModel):
    id: int
    product_id: int
    product_name: Optional[str]
    sku: Optional[str]
    billing_type: str
    quantity: int
    unit_price: Decimal
    discount_percentage: Decimal
    total_price: Decimal
    model_config = ConfigDict(from_attributes=True)

    @field_serializer("unit_price", "discount_percentage", "total_price")
    def _money(self, v: Decimal) -> str:
        return f"{v:.2f}"


class OrderRead(BaseModel):
    id: int
    order_number: str
    quote_id: int
    quote_number: Optional[str] = None
    customer_id: int
    customer_name: Optional[str] = None
    status: str
    currency: str
    subtotal: Decimal
    discount_amount: Decimal
    tax_amount: Decimal
    total_amount: Decimal
    notes: Optional[str] = None
    created_at: datetime
    lines: List[OrderLineRead] = []

    @field_serializer("subtotal", "discount_amount", "tax_amount", "total_amount")
    def _money(self, v: Decimal) -> str:
        return f"{v:.2f}"


class OrderStatusUpdate(BaseModel):
    status: OrderStatus
    notes: Optional[str] = None


def to_read(o: Order) -> OrderRead:
    cust = o.customer
    return OrderRead(
        id=o.id, order_number=o.order_number, quote_id=o.quote_id, quote_number=o.quote.quote_number if o.quote else None,
        customer_id=o.customer_id, customer_name=(cust.display_name or cust.legal_name) if cust else None,
        status=o.status, currency=o.currency, subtotal=o.subtotal, discount_amount=o.discount_amount, tax_amount=o.tax_amount,
        total_amount=o.total_amount, notes=o.notes, created_at=o.created_at,
        lines=[OrderLineRead.model_validate(l) for l in o.lines],
    )


async def _get(db: AsyncSession, order_id: int) -> Order:
    order = await db.get(Order, order_id)
    if not order:
        raise EntityNotFoundError(f"Order {order_id} not found.")
    return order


@router.post("/from-quote/{quote_id}", response_model=OrderRead, status_code=status.HTTP_201_CREATED)
async def create_order_from_quote(
    quote_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker("quotes.update")),
):
    """Book an order from an ACCEPTED quote. A quote can be booked once; line prices are copied as frozen."""
    qs = QuoteService(db)
    quote = await qs.get_quote(quote_id, current_user)
    if (quote.status.value if hasattr(quote.status, "value") else str(quote.status)) != QuoteStatus.ACCEPTED.value:
        raise DomainValidationError("Only accepted quotes can be converted to orders.")
    existing = (await db.execute(select(Order).where(Order.quote_id == quote.id))).scalars().first()
    if existing:
        raise DomainValidationError(f"This quote is already booked as order {existing.order_number}.")

    count = (await db.execute(select(func.coalesce(func.max(Order.id), 0)))).scalar() or 0
    order = Order(
        order_number=f"SO-{100001 + count}", quote_id=quote.id, customer_id=quote.customer_id,
        status=OrderStatus.PENDING.value, currency=quote.currency, subtotal=quote.subtotal,
        discount_amount=quote.discount_amount, tax_amount=quote.tax_amount, total_amount=quote.total_amount,
        created_by_id=current_user.id,
        lines=[OrderLine(
            product_id=i.product_id, product_name=i.product_name, sku=i.sku, billing_type=i.billing_type, quantity=i.quantity,
            unit_price=i.unit_price, discount_percentage=i.discount_percentage, total_price=i.total_price,
        ) for i in quote.items],
    )
    db.add(order)
    await db.flush()
    await qs.quote_repo.log_audit(
        quote_id=quote.id, action="ORDER_CREATED", user_id=current_user.id,
        after_value={"order_number": order.order_number, "total": f"{order.total_amount:.2f}"},
    )
    await db.commit()
    return to_read(await _get(db, order.id))


@router.get("/", response_model=List[OrderRead])
async def list_orders(
    status_filter: Optional[OrderStatus] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker("quotes.read")),
):
    stmt = select(Order).order_by(Order.id.desc()).limit(200)
    roles = {r.name for r in current_user.roles}
    if not roles.intersection({"Administrator", "Executive", "Sales Manager"}):
        stmt = stmt.where(Order.created_by_id == current_user.id)
    if status_filter:
        stmt = stmt.where(Order.status == status_filter.value)
    return [to_read(o) for o in (await db.execute(stmt)).scalars().all()]


@router.get("/{order_id}", response_model=OrderRead)
async def get_order(order_id: int, db: AsyncSession = Depends(get_db), current_user: User = Depends(PermissionChecker("quotes.read"))):
    order = await _get(db, order_id)
    await QuoteService(db).get_quote(order.quote_id, current_user)  # RBAC via the parent quote
    return to_read(order)


@router.post("/{order_id}/status", response_model=OrderRead)
async def update_order_status(
    order_id: int,
    body: OrderStatusUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker("quotes.update")),
):
    order = await _get(db, order_id)
    await QuoteService(db).get_quote(order.quote_id, current_user)
    if body.status.value not in TRANSITIONS[order.status]:
        raise DomainValidationError(f"Cannot move an order from {order.status} to {body.status.value}.")
    order.status = body.status.value
    if body.notes:
        order.notes = body.notes
    db.add(order)
    await db.commit()
    return to_read(await _get(db, order_id))
