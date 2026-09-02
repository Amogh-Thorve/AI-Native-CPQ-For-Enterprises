from pydantic import BaseModel, Field, field_serializer, ConfigDict
from decimal import Decimal
from typing import List, Optional, Any
from backend.app.domains.pricing.domain.enums import PricingMethod, TieredMode

class PricingTierBase(BaseModel):
    min_quantity: int = Field(..., ge=1, description="Minimum quantity for the tier (inclusive)")
    max_quantity: Optional[int] = Field(None, description="Maximum quantity for the tier (inclusive, null = unlimited)")
    price: Decimal = Field(..., ge=0, description="Per-unit price or fixed block price for the range")

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

    model_config = ConfigDict(from_attributes=True)

    @field_serializer("markup_percent")
    def serialize_markup(self, v: Decimal) -> str:
        return f"{v:.2f}"

class PricingSettingUpdate(BaseModel):
    pricing_method: PricingMethod = Field(..., description="Pricing method configured for product")
    markup_percent: Decimal = Field(default=Decimal("0.00"), ge=0, description="Markup percentage")

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
    has_tiers: bool = False

    model_config = ConfigDict(from_attributes=True)

    @field_serializer("base_price", "cost_price", "margin_percentage", "markup_percent")
    def serialize_decimals(self, v: Optional[Decimal]) -> Optional[str]:
        if v is None:
            return None
        return f"{v:.2f}"

class CalculatePriceRequest(BaseModel):
    product_id: int = Field(..., description="ID of the product in the catalog")
    quantity: int = Field(..., description="Positive integer quantity")
    pricing_method: PricingMethod = Field(..., description="Pricing method, e.g. STANDARD, LINE_DISCOUNT, TIERED, BLOCK, COST_PLUS_MARKUP")
    discount_percent: Optional[Decimal] = Field(default=Decimal("0.00"), description="Percentage discount for LINE_DISCOUNT")
    tiered_mode: Optional[TieredMode] = Field(default=None, description="Tiered pricing mode (VOLUME or CUMULATIVE)")
    price_book_id: Optional[int] = Field(None, description="Optional custom Price Book ID")
    custom_markup_percent: Optional[Decimal] = Field(default=None, description="Dynamic override for markup/discount percent during preview")
    custom_tiers: Optional[List[PricingTierCreate]] = Field(default=None, description="Dynamic override for tiers during preview")

class CalculatePriceResponse(BaseModel):
    product_id: int
    product_name: str
    quantity: int
    pricing_method: PricingMethod
    billing_type: str
    base_unit_price: Decimal
    discount_percent: Decimal
    discount_amount: Decimal
    final_unit_price: Decimal
    total_price: Decimal
    currency: str
    calculation_breakdown: List[Any] = []

    model_config = ConfigDict(
        from_attributes=True,
        json_encoders={
            Decimal: lambda v: f"{v:.2f}"
        }
    )

    @field_serializer("base_unit_price", "discount_percent", "discount_amount", "final_unit_price", "total_price")
    def serialize_decimal(self, v: Decimal) -> str:
        return f"{v:.2f}"
