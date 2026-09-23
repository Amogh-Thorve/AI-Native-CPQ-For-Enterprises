from pydantic import BaseModel, Field, field_serializer, ConfigDict, computed_field
from decimal import Decimal
from typing import Optional, List, Dict, Any
from datetime import datetime
import uuid
from backend.app.domains.quotes.models import QuoteStatus

class CustomerSummaryRead(BaseModel):
    id: int
    legal_name: Optional[str] = None
    display_name: Optional[str] = None
    customer_number: Optional[str] = None
    email: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

    @computed_field
    @property
    def name(self) -> str:
        return self.display_name or self.legal_name or f"Customer #{self.id}"

class UserSummaryRead(BaseModel):
    id: uuid.UUID
    username: str
    email: str
    first_name: str
    last_name: str

    model_config = ConfigDict(from_attributes=True)

class QuoteLineItemBase(BaseModel):
    product_id: int = Field(..., description="Catalog product ID")
    quantity: int = Field(default=1, ge=1, description="Positive quantity")
    discount_percentage: Decimal = Field(default=Decimal("0.00"), ge=Decimal("0.00"), le=Decimal("100.00"), description="Line item discount percentage (0 to 100)")
    configuration_id: Optional[str] = Field(default=None, description="Optional configuration session reference")
    configuration_snapshot: Optional[Dict[str, Any]] = Field(default=None, description="Optional configuration snapshot")

class QuoteLineItemCreate(QuoteLineItemBase):
    pass

class QuoteLineItemUpdate(BaseModel):
    quantity: Optional[int] = Field(default=None, ge=1)
    discount_percentage: Optional[Decimal] = Field(default=None, ge=Decimal("0.00"), le=Decimal("100.00"))
    configuration_id: Optional[str] = None
    configuration_snapshot: Optional[Dict[str, Any]] = None

class QuoteLineItemRead(QuoteLineItemBase):
    id: int
    quote_id: int
    product_name: Optional[str] = None
    sku: Optional[str] = None
    billing_type: str = "MRC"
    currency: str = "USD"
    unit_price: Decimal
    discount_amount: Decimal
    total_price: Decimal
    pricing_method: Optional[str] = None
    pricing_breakdown: Optional[List[Dict[str, Any]]] = None
    margin_amount: Optional[Decimal] = None
    margin_percentage: Optional[Decimal] = None

    model_config = ConfigDict(from_attributes=True)

    @computed_field
    @property
    def line_total(self) -> Decimal:
        return self.total_price

    @field_serializer("unit_price", "discount_percentage", "discount_amount", "total_price", "margin_amount", "margin_percentage", "line_total")
    def serialize_decimals(self, v: Optional[Decimal]) -> Optional[str]:
        if v is None:
            return None
        return f"{v:.2f}"

class QuoteAuditLogRead(BaseModel):
    id: int
    quote_id: int
    user_id: Optional[uuid.UUID] = None
    user_role: Optional[str] = None
    action: str
    before_value: Optional[Dict[str, Any]] = None
    after_value: Optional[Dict[str, Any]] = None
    timestamp: datetime

    model_config = ConfigDict(from_attributes=True)

class QuoteBase(BaseModel):
    customer_id: int = Field(..., description="Target customer ID")
    title: Optional[str] = Field(default=None, max_length=255, description="Descriptive title/name for the quote")
    description: Optional[str] = Field(default=None, description="Detailed quote description")
    currency: str = Field(default="USD", max_length=10, description="ISO Currency code")
    valid_until: Optional[datetime] = Field(default=None, description="Expiration/validity cutoff date")
    notes: Optional[str] = Field(default=None, description="Internal or external notes")
    price_book_id: Optional[int] = None
    external_opportunity_id: Optional[str] = None

class QuoteCreate(QuoteBase):
    items: List[QuoteLineItemCreate] = []

class QuoteUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    currency: Optional[str] = None
    valid_until: Optional[datetime] = None
    notes: Optional[str] = None
    status: Optional[QuoteStatus] = None
    price_book_id: Optional[int] = None
    external_opportunity_id: Optional[str] = None
    external_crm_id: Optional[str] = None

class QuoteRead(QuoteBase):
    id: int
    quote_number: str
    version: int
    status: QuoteStatus
    subtotal: Decimal
    discount_amount: Decimal
    tax_amount: Decimal
    total_amount: Decimal
    margin_percentage: Optional[Decimal] = None
    created_by_id: uuid.UUID
    created_by: Optional[UserSummaryRead] = None
    customer: Optional[CustomerSummaryRead] = None
    created_at: datetime
    updated_at: datetime
    parent_quote_id: Optional[int] = None
    items: List[QuoteLineItemRead] = []
    audit_logs: List[QuoteAuditLogRead] = []

    model_config = ConfigDict(from_attributes=True)

    @computed_field
    @property
    def grand_total(self) -> Decimal:
        return self.total_amount

    @computed_field
    @property
    def discount_total(self) -> Decimal:
        return self.discount_amount

    @field_serializer("subtotal", "discount_amount", "tax_amount", "total_amount", "margin_percentage", "grand_total", "discount_total")
    def serialize_totals(self, v: Optional[Decimal]) -> Optional[str]:
        if v is None:
            return None
        return f"{v:.2f}"
