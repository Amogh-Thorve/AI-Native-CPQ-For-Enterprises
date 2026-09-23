from pydantic import BaseModel, Field, field_serializer, ConfigDict
from decimal import Decimal
from typing import List, Optional, Any
from datetime import datetime
from backend.app.domains.pricing.domain.enums import PricingMethod, TieredMode

class PricingTierBase(BaseModel):
    min_quantity: int = Field(..., ge=1, description="Minimum quantity for the tier (inclusive)")
    max_quantity: Optional[int] = Field(None, description="Maximum quantity for the tier (inclusive, null = unlimited)")
    price: Decimal = Field(..., ge=0, description="Per-unit price or fixed block price for the range")
    display_order: int = Field(default=1, ge=1, description="Display sort order for the tier")
    is_active: bool = Field(default=True, description="Whether this tier is currently active")

class PricingTierCreate(PricingTierBase):
    pricing_method: PricingMethod = Field(..., description="TIERED or BLOCK")
    tiered_mode: Optional[TieredMode] = Field(None, description="VOLUME or CUMULATIVE (only for TIERED method)")

class PricingTierRead(PricingTierBase):
    id: int
    product_id: int
    pricing_method: PricingMethod
    tiered_mode: Optional[TieredMode] = None

    model_config = ConfigDict(from_attributes=True)

    @field_serializer("price")
    def serialize_price(self, v: Decimal) -> str:
        return f"{v:.2f}"

class PricingSettingRead(BaseModel):
    product_id: int
    pricing_method: PricingMethod
    markup_percent: Decimal
    status: str = "ACTIVE"
    effective_from: Optional[datetime] = None
    effective_until: Optional[datetime] = None
    discount_percent: Optional[Decimal] = Decimal("0.00")

    model_config = ConfigDict(from_attributes=True)

    @field_serializer("markup_percent", "discount_percent")
    def serialize_markup(self, v: Optional[Decimal]) -> Optional[str]:
        if v is None:
            return None
        return f"{v:.2f}"

class PricingSettingUpdate(BaseModel):
    pricing_method: PricingMethod = Field(..., description="Pricing method configured for product")
    markup_percent: Decimal = Field(default=Decimal("0.00"), ge=0, description="Markup percentage")
    status: Optional[str] = Field(default="ACTIVE", description="DRAFT, ACTIVE, INACTIVE, ARCHIVED")
    effective_from: Optional[datetime] = Field(default=None, description="Start date/time when this config becomes effective")
    effective_until: Optional[datetime] = Field(default=None, description="End date/time when this config expires")
    discount_percent: Optional[Decimal] = Field(default=Decimal("0.00"), ge=0, le=100, description="Default line discount percent")

class EnrichedProductRead(BaseModel):
    id: int
    sku: str
    name: str
    description: Optional[str] = None
    base_price: Decimal
    cost_price: Optional[Decimal] = None
    margin_percentage: Optional[Decimal] = None
    currency: str
    is_active: bool
    billing_type: str
    category_name: Optional[str] = None
    pricing_method: PricingMethod = PricingMethod.STANDARD
    markup_percent: Decimal = Decimal("0.00")
    discount_percent: Decimal = Decimal("0.00")
    status: str = "ACTIVE"
    effective_from: Optional[datetime] = None
    effective_until: Optional[datetime] = None
    has_tiers: bool = False

    model_config = ConfigDict(from_attributes=True)

    @field_serializer("base_price", "cost_price", "margin_percentage", "markup_percent", "discount_percent")
    def serialize_decimals(self, v: Optional[Decimal]) -> Optional[str]:
        if v is None:
            return None
        return f"{v:.2f}"

class CalculatePriceRequest(BaseModel):
    product_id: int = Field(..., description="ID of the product in the catalog")
    quantity: int = Field(..., description="Positive integer quantity")
    pricing_method: Optional[PricingMethod] = Field(default=None, description="Pricing method, e.g. STANDARD, LINE_DISCOUNT, TIERED, BLOCK, COST_PLUS_MARKUP. Defaults to product setting if omitted.")
    discount_percent: Optional[Decimal] = Field(default=Decimal("0.00"), description="Percentage discount for LINE_DISCOUNT")
    tiered_mode: Optional[TieredMode] = Field(default=None, description="Tiered pricing mode (VOLUME or CUMULATIVE)")
    price_book_id: Optional[int] = Field(None, description="Optional custom Price Book ID")
    custom_markup_percent: Optional[Decimal] = Field(default=None, description="Dynamic override for markup/discount percent during preview")
    custom_tiers: Optional[List[PricingTierCreate]] = Field(default=None, description="Dynamic override for tiers during preview")
    override_unit_price: Optional[Decimal] = Field(default=None, ge=0, description="Manual price override (requires pricing.override permission)")
    override_reason: Optional[str] = Field(default=None, max_length=500, description="Audit reason for manual price override")

class CalculatePriceResponse(BaseModel):
    product_id: int
    product_name: str
    sku: str
    quantity: int
    pricing_method: PricingMethod
    billing_type: str
    base_unit_price: Decimal
    discount_percent: Decimal
    discount_amount: Decimal
    final_unit_price: Decimal
    total_price: Decimal
    unit_cost: Optional[Decimal] = None
    total_cost: Optional[Decimal] = None
    margin_amount: Optional[Decimal] = None
    margin_percentage: Optional[Decimal] = None
    currency: str
    calculation_breakdown: List[Any] = []

    model_config = ConfigDict(
        from_attributes=True,
        json_encoders={
            Decimal: lambda v: f"{v:.2f}"
        }
    )

    @field_serializer("base_unit_price", "discount_percent", "discount_amount", "final_unit_price", "total_price", "unit_cost", "total_cost", "margin_amount", "margin_percentage")
    def serialize_decimal(self, v: Optional[Decimal]) -> Optional[str]:
        if v is None:
            return None
        return f"{v:.2f}"
