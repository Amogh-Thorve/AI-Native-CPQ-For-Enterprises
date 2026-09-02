from decimal import Decimal
from typing import Dict, Any, Optional, List
from backend.app.domains.pricing.domain.enums import PricingMethod, TieredMode
from backend.app.domains.pricing.domain.strategies import get_pricing_strategy
from backend.app.core.exceptions import DomainValidationError

class PricingEngine:
    @staticmethod
    def calculate(
        product_id: int,
        sku: str,
        name: str,
        billing_type: str,
        currency: str,
        base_price: Decimal,
        quantity: int,
        pricing_method: PricingMethod,
        discount_percent: Decimal = Decimal("0.00"),
        tiers: Optional[List[Any]] = None,
        tiered_mode: Optional[TieredMode] = None,
        cost_price: Optional[Decimal] = None,
        markup_percent: Optional[Decimal] = None,
    ) -> Dict[str, Any]:
        """
        Calculates pricing using the chosen strategy.
        All input values should already be validated/formatted by the application service.
        """
        # Validate quantity
        if quantity <= 0:
            raise DomainValidationError("Quantity must be a positive integer greater than zero.")
            
        # Get strategy from registry
        strategy = get_pricing_strategy(pricing_method)
        
        # Calculate
        calc_result = strategy.calculate(
            base_price=base_price,
            quantity=quantity,
            discount_percent=discount_percent,
            tiers=tiers,
            tiered_mode=tiered_mode,
            cost_price=cost_price,
            markup_percent=markup_percent
        )
        
        # Return complete payload
        return {
            "product_id": product_id,
            "product_name": name,
            "sku": sku,
            "quantity": quantity,
            "pricing_method": pricing_method,
            "billing_type": billing_type,
            "base_unit_price": calc_result["base_unit_price"],
            "discount_percent": calc_result["discount_percent"],
            "discount_amount": calc_result["discount_amount"],
            "final_unit_price": calc_result["final_unit_price"],
            "total_price": calc_result["total_price"],
            "currency": currency,
            "calculation_breakdown": calc_result["calculation_breakdown"]
        }
