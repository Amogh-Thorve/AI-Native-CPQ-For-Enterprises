from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from backend.app.domains.pricing.models import PricingRuleType

class PricingRuleBase(BaseModel):
    name: str
    rule_type: PricingRuleType
    is_active: bool = True
    conditions: Dict[str, Any] = {}
    actions: Dict[str, Any] = {}
    description: Optional[str] = None
    status: Optional[str] = "ACTIVE"

class PricingRuleCreate(PricingRuleBase):
    pass

class PricingRuleUpdate(BaseModel):
    name: Optional[str] = None
    rule_type: Optional[PricingRuleType] = None
    is_active: Optional[bool] = None
    conditions: Optional[Dict[str, Any]] = None
    actions: Optional[Dict[str, Any]] = None
    description: Optional[str] = None
    status: Optional[str] = None

class PricingRuleRead(PricingRuleBase):
    id: int

    model_config = {"from_attributes": True}

class CalculatePriceRequest(BaseModel):
    product_id: int
    quantity: int
    customer_id: Optional[int] = None
    price_book_id: Optional[int] = None
    requested_discount: float = 0.0  # Rep manual override discount percentage

class CalculatePriceResponse(BaseModel):
    product_id: int
    base_price: float
    discounted_price: float
    total_amount: float
    applied_rules: List[str] = []
    margin_percentage: float = 100.0  # Placeholder margin calculation
