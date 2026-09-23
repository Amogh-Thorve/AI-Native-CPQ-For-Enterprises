from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Dict, Any, List, Optional
from backend.app.domains.pricing.domain.enums import PricingMethod, TieredMode
from backend.app.core.exceptions import DomainValidationError

class PricingStrategy(ABC):
    @abstractmethod
    def calculate(
        self,
        base_price: Decimal,
        quantity: int,
        discount_percent: Decimal = Decimal("0.00"),
        tiers: Optional[List[Any]] = None,
        tiered_mode: Optional[TieredMode] = None,
        **kwargs: Any
    ) -> Dict[str, Any]:
        pass

def validate_tiers(tiers_list: List[Any]) -> List[Any]:
    if not tiers_list:
        raise DomainValidationError("At least one tier configuration must be provided.")
        
    # Filter active tiers if is_active attribute exists
    active_tiers = [t for t in tiers_list if getattr(t, "is_active", True) is not False]
    if not active_tiers:
        raise DomainValidationError("At least one active tier configuration must be provided.")

    # Sort by min_quantity
    sorted_tiers = sorted(active_tiers, key=lambda t: (t.min_quantity, getattr(t, "display_order", 1)))
    
    seen_mins = set()
    for t in sorted_tiers:
        if t.min_quantity in seen_mins:
            raise DomainValidationError(f"Overlapping or duplicate tiers detected at quantity {t.min_quantity}.")
        seen_mins.add(t.min_quantity)

    if sorted_tiers[0].min_quantity != 1:
        raise DomainValidationError("Tier configurations must start at quantity 1.")
        
    for i in range(len(sorted_tiers)):
        tier = sorted_tiers[i]
        
        # Ensure Decimal/int representations
        price_dec = Decimal(str(tier.price))
        
        if tier.min_quantity < 1:
            raise DomainValidationError("Min quantity must be at least 1.")
        if price_dec < Decimal("0.00"):
            raise DomainValidationError("Price cannot be negative.")
            
        if tier.max_quantity is not None:
            if tier.max_quantity < tier.min_quantity:
                raise DomainValidationError("Max quantity cannot be less than min quantity.")
            
            # Check contiguity
            if i < len(sorted_tiers) - 1:
                next_tier = sorted_tiers[i+1]
                if next_tier.min_quantity != tier.max_quantity + 1:
                    raise DomainValidationError(
                        f"Gaps or overlaps detected: tier ending at {tier.max_quantity} "
                        f"must be followed by tier starting at {tier.max_quantity + 1}."
                    )
        else:
            # Unlimited tier must be the final tier
            if i < len(sorted_tiers) - 1:
                raise DomainValidationError("An unlimited tier (max quantity empty) must be the final tier.")
                
    return sorted_tiers

class StandardPricingStrategy(PricingStrategy):
    def calculate(
        self,
        base_price: Decimal,
        quantity: int,
        discount_percent: Decimal = Decimal("0.00"),
        tiers: Optional[List[Any]] = None,
        tiered_mode: Optional[TieredMode] = None,
        **kwargs: Any
    ) -> Dict[str, Any]:
        base_unit_price = base_price.quantize(Decimal("0.01"))
        total_price = (base_unit_price * quantity).quantize(Decimal("0.01"))
        
        return {
            "base_unit_price": base_unit_price,
            "discount_percent": Decimal("0.00").quantize(Decimal("0.01")),
            "discount_amount": Decimal("0.00").quantize(Decimal("0.01")),
            "final_unit_price": base_unit_price,
            "total_price": total_price,
            "calculation_breakdown": [
                {
                    "description": f"Standard Pricing Applied: {base_unit_price} x {quantity} = {total_price}",
                    "tier": "Standard",
                    "quantity": quantity,
                    "unit_price": f"{base_unit_price:.2f}",
                    "amount": f"{total_price:.2f}"
                }
            ]
        }

class LineDiscountPricingStrategy(PricingStrategy):
    def calculate(
        self,
        base_price: Decimal,
        quantity: int,
        discount_percent: Decimal = Decimal("0.00"),
        tiers: Optional[List[Any]] = None,
        tiered_mode: Optional[TieredMode] = None,
        **kwargs: Any
    ) -> Dict[str, Any]:
        if discount_percent < Decimal("0.00") or discount_percent > Decimal("100.00"):
            raise DomainValidationError("Discount must be between 0 and 100.")
            
        base_unit_price = base_price.quantize(Decimal("0.01"))
        discount_amount = (base_unit_price * discount_percent / Decimal("100")).quantize(Decimal("0.01"))
        final_unit_price = (base_unit_price - discount_amount).quantize(Decimal("0.01"))
        total_price = (final_unit_price * quantity).quantize(Decimal("0.01"))
        
        return {
            "base_unit_price": base_unit_price,
            "discount_percent": discount_percent.quantize(Decimal("0.01")),
            "discount_amount": discount_amount,
            "final_unit_price": final_unit_price,
            "total_price": total_price,
            "calculation_breakdown": [
                {
                    "description": f"Line discount {discount_percent}% applied (Base: {base_unit_price}, Discount: {discount_amount})",
                    "tier": "Discount",
                    "quantity": quantity,
                    "unit_price": f"{final_unit_price:.2f}",
                    "amount": f"{total_price:.2f}"
                }
            ]
        }

class TieredPricingStrategy(PricingStrategy):
    def calculate(
        self,
        base_price: Decimal,
        quantity: int,
        discount_percent: Decimal = Decimal("0.00"),
        tiers: Optional[List[Any]] = None,
        tiered_mode: Optional[TieredMode] = None,
        **kwargs: Any
    ) -> Dict[str, Any]:
        if not tiers:
            raise DomainValidationError("No pricing tiers configured for tiered pricing calculation.")
        if not tiered_mode:
            raise DomainValidationError("Tiered pricing mode (VOLUME or CUMULATIVE) must be specified.")

        sorted_tiers = validate_tiers(tiers)
        calculation_breakdown = []
        total_price = Decimal("0.00")

        if tiered_mode == TieredMode.VOLUME:
            # VOLUME Mode: Entire quantity is priced at the tier it falls into.
            matching_tier = None
            for tier in sorted_tiers:
                if tier.min_quantity <= quantity and (tier.max_quantity is None or quantity <= tier.max_quantity):
                    matching_tier = tier
                    break
            
            if not matching_tier:
                raise DomainValidationError(f"No applicable pricing tier for quantity {quantity}.")
            
            tier_price = Decimal(str(matching_tier.price)).quantize(Decimal("0.01"))
            total_price = (tier_price * quantity).quantize(Decimal("0.01"))
            final_unit_price = tier_price
            
            max_str = str(matching_tier.max_quantity) if matching_tier.max_quantity is not None else "unlimited"
            calculation_breakdown.append({
                "description": f"Volume tier {matching_tier.min_quantity}-{max_str}",
                "tier": f"{matching_tier.min_quantity}-{max_str}",
                "quantity": quantity,
                "unit_price": f"{tier_price:.2f}",
                "amount": f"{total_price:.2f}"
            })
        
        elif tiered_mode == TieredMode.CUMULATIVE:
            # CUMULATIVE Mode: Price is calculated segment by segment.
            remaining_qty = quantity
            for tier in sorted_tiers:
                if remaining_qty <= 0:
                    break
                
                tier_min = tier.min_quantity
                tier_max = tier.max_quantity
                tier_price = Decimal(str(tier.price)).quantize(Decimal("0.01"))
                
                # Calculate capacity of current tier
                if tier_max is None:
                    qty_in_tier = remaining_qty
                else:
                    tier_capacity = tier_max - tier_min + 1
                    qty_in_tier = min(remaining_qty, tier_capacity)
                
                if qty_in_tier > 0:
                    tier_amount = (qty_in_tier * tier_price).quantize(Decimal("0.01"))
                    total_price += tier_amount
                    remaining_qty -= qty_in_tier
                    
                    max_str = str(tier_max) if tier_max is not None else "unlimited"
                    calculation_breakdown.append({
                        "description": f"Cumulative tier {tier_min}-{max_str}",
                        "tier": f"{tier_min}-{max_str}",
                        "quantity": qty_in_tier,
                        "unit_price": f"{tier_price:.2f}",
                        "amount": f"{tier_amount:.2f}"
                    })

            if remaining_qty > 0:
                raise DomainValidationError(f"No applicable pricing tier for remaining quantity {remaining_qty}.")
                
            final_unit_price = (total_price / quantity).quantize(Decimal("0.01"))
            
        else:
            raise DomainValidationError(f"Unsupported tiered mode: {tiered_mode}")

        return {
            "base_unit_price": base_price.quantize(Decimal("0.01")),
            "discount_percent": Decimal("0.00").quantize(Decimal("0.01")),
            "discount_amount": Decimal("0.00").quantize(Decimal("0.01")),
            "final_unit_price": final_unit_price,
            "total_price": total_price,
            "calculation_breakdown": calculation_breakdown
        }

class BlockPricingStrategy(PricingStrategy):
    def calculate(
        self,
        base_price: Decimal,
        quantity: int,
        discount_percent: Decimal = Decimal("0.00"),
        tiers: Optional[List[Any]] = None,
        tiered_mode: Optional[TieredMode] = None,
        **kwargs: Any
    ) -> Dict[str, Any]:
        if not tiers:
            raise DomainValidationError("No pricing tiers configured for block pricing calculation.")
            
        sorted_tiers = validate_tiers(tiers)
        
        matching_tier = None
        for tier in sorted_tiers:
            if tier.min_quantity <= quantity and (tier.max_quantity is None or quantity <= tier.max_quantity):
                matching_tier = tier
                break
                
        if not matching_tier:
            raise DomainValidationError(f"No applicable pricing tier for quantity {quantity}.")
            
        block_price = Decimal(str(matching_tier.price)).quantize(Decimal("0.01"))
        total_price = block_price
        final_unit_price = (total_price / quantity).quantize(Decimal("0.01"))
        
        max_str = str(matching_tier.max_quantity) if matching_tier.max_quantity is not None else "unlimited"
        calculation_breakdown = [{
            "description": f"Block tier {matching_tier.min_quantity}-{max_str}",
            "tier": f"{matching_tier.min_quantity}-{max_str}",
            "quantity": quantity,
            "unit_price": f"{final_unit_price:.2f}",
            "amount": f"{block_price:.2f}"
        }]
        
        return {
            "base_unit_price": base_price.quantize(Decimal("0.01")),
            "discount_percent": Decimal("0.00").quantize(Decimal("0.01")),
            "discount_amount": Decimal("0.00").quantize(Decimal("0.01")),
            "final_unit_price": final_unit_price,
            "total_price": total_price,
            "calculation_breakdown": calculation_breakdown
        }

class CostPlusMarkupPricingStrategy(PricingStrategy):
    def calculate(
        self,
        base_price: Decimal,
        quantity: int,
        discount_percent: Decimal = Decimal("0.00"),
        tiers: Optional[List[Any]] = None,
        tiered_mode: Optional[TieredMode] = None,
        cost_price: Optional[Decimal] = None,
        markup_percent: Optional[Decimal] = None,
        **kwargs: Any
    ) -> Dict[str, Any]:
        if cost_price is None:
            raise DomainValidationError("Product cost must be configured for Cost + Markup pricing.")
        if cost_price < Decimal("0.00"):
            raise DomainValidationError("Product cost cannot be negative.")
        if markup_percent is None or markup_percent < Decimal("0.00"):
            raise DomainValidationError("Markup percentage cannot be negative.")

        cost_dec = cost_price.quantize(Decimal("0.01"))
        markup_factor = Decimal("1.00") + (markup_percent / Decimal("100.00"))
        selling_unit_price = (cost_dec * markup_factor).quantize(Decimal("0.01"))
        total_price = (selling_unit_price * quantity).quantize(Decimal("0.01"))

        return {
            "base_unit_price": base_price.quantize(Decimal("0.01")),
            "discount_percent": Decimal("0.00").quantize(Decimal("0.01")),
            "discount_amount": Decimal("0.00").quantize(Decimal("0.01")),
            "final_unit_price": selling_unit_price,
            "total_price": total_price,
            "calculation_breakdown": [
                {
                    "description": f"Cost + Markup Applied: Cost {cost_dec} + {markup_percent}% markup = {selling_unit_price}",
                    "tier": "Cost+Markup",
                    "quantity": quantity,
                    "unit_price": f"{selling_unit_price:.2f}",
                    "amount": f"{total_price:.2f}"
                }
            ]
        }

# Strategy Registry
_STRATEGIES: Dict[PricingMethod, PricingStrategy] = {
    PricingMethod.STANDARD: StandardPricingStrategy(),
    PricingMethod.LINE_DISCOUNT: LineDiscountPricingStrategy(),
    PricingMethod.TIERED: TieredPricingStrategy(),
    PricingMethod.BLOCK: BlockPricingStrategy(),
    PricingMethod.COST_PLUS_MARKUP: CostPlusMarkupPricingStrategy(),
}

def get_pricing_strategy(method: PricingMethod) -> PricingStrategy:
    strategy = _STRATEGIES.get(method)
    if not strategy:
        raise DomainValidationError(f"Pricing method '{method}' is not implemented or supported.")
    return strategy
