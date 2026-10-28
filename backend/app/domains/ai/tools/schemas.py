"""
Typed inputs and outputs for every tool.

Inputs forbid unknown keys, so a caller cannot smuggle a price (`unit_price`, `total`, ...) into a line.
Prices are always computed by the pricing engine; a line only carries product, quantity, discount and
an optional configuration session.
"""
from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class _In(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ─── Inputs ─────────────────────────────────────────────────────────────────

class SearchProductsIn(_In):
    query: Optional[str] = Field(default=None, max_length=120, description="Matches product name or SKU")
    category_id: Optional[int] = None
    active_only: bool = True
    limit: int = Field(default=20, ge=1, le=50)


class GetCustomerIn(_In):
    customer_id: int = Field(gt=0)


class ListCustomersIn(_In):
    status: Optional[str] = Field(default=None, max_length=20)
    customer_type: Optional[str] = Field(default=None, max_length=20)
    industry: Optional[str] = Field(default=None, max_length=100)
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


class SelectionIn(_In):
    group_id: int
    option_ids: List[int] = Field(default_factory=list, max_length=50)


class ValidateConfigurationIn(_In):
    product_id: int
    selections: List[SelectionIn] = Field(default_factory=list, max_length=50)


class ItemIn(_In):
    """A product line request. This is the only shape a price or a line can take."""
    product_id: int
    quantity: int = Field(default=1, ge=1, le=100000)
    discount_percent: Decimal = Field(default=Decimal("0"), ge=0, le=100)
    configuration_session_id: Optional[UUID] = None


class PriceItemIn(ItemIn):
    pass


class CreateQuoteIn(_In):
    customer_id: int = Field(gt=0)
    title: Optional[str] = Field(default=None, max_length=255)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    valid_days: Optional[int] = Field(default=None, ge=1, le=365)
    items: List[ItemIn] = Field(default_factory=list, max_length=50)


class AddQuoteItemIn(ItemIn):
    quote_id: int = Field(gt=0)


class UpdateQuoteItemIn(_In):
    quote_id: int = Field(gt=0)
    item_id: int = Field(gt=0)
    quantity: Optional[int] = Field(default=None, ge=1, le=100000)
    discount_percent: Optional[Decimal] = Field(default=None, ge=0, le=100)


class RemoveQuoteItemIn(_In):
    quote_id: int = Field(gt=0)
    item_id: int = Field(gt=0)


class QuoteRefIn(_In):
    quote_id: int = Field(gt=0)


# ─── Outputs ────────────────────────────────────────────────────────────────

class ProductOut(BaseModel):
    id: int
    sku: str
    name: str
    base_price: Decimal
    cost_price: Optional[Decimal] = None
    currency: str
    is_active: bool
    billing_type: str


class ProductListOut(BaseModel):
    items: List[ProductOut]


class CustomerOut(BaseModel):
    id: int
    customer_number: str
    legal_name: str
    display_name: Optional[str] = None
    status: str
    customer_type: str
    industry: Optional[str] = None
    email: Optional[str] = None
    currency: str


class CustomerListOut(BaseModel):
    items: List[CustomerOut]
    total: int
    page: int
    page_size: int


class ConfigErrorOut(BaseModel):
    rule_type: str
    message: str


class ValidateConfigurationOut(BaseModel):
    valid: bool
    errors: List[ConfigErrorOut] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


class PriceOut(BaseModel):
    product_id: int
    sku: str
    quantity: int
    pricing_method: str
    billing_type: str
    currency: str
    base_unit_price: Decimal
    discount_percent: Decimal
    final_unit_price: Decimal
    total_price: Decimal
    unit_cost: Optional[Decimal] = None
    total_cost: Optional[Decimal] = None
    margin_amount: Optional[Decimal] = None
    margin_percentage: Optional[Decimal] = None
    configuration_session_id: Optional[UUID] = None


class LineOut(BaseModel):
    id: int
    product_id: int
    product_name: Optional[str] = None
    sku: Optional[str] = None
    billing_type: str
    quantity: int
    unit_price: Decimal
    discount_percentage: Decimal
    total_price: Decimal
    margin_amount: Optional[Decimal] = None
    margin_percentage: Optional[Decimal] = None


class QuoteOut(BaseModel):
    id: int
    quote_number: str
    version: int
    status: str
    customer_id: int
    title: Optional[str] = None
    currency: str
    valid_until: Optional[datetime] = None
    subtotal: Decimal
    discount_amount: Decimal
    tax_amount: Decimal
    total_amount: Decimal
    margin_percentage: Optional[Decimal] = None
    items: List[LineOut] = Field(default_factory=list)
