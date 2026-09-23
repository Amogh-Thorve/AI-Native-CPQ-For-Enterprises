from decimal import Decimal
from typing import List, Optional, Any, Set
import uuid
from datetime import datetime, timezone
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.domains.catalog.services import CatalogService
from backend.app.domains.catalog.models import Product
from backend.app.domains.pricing.api.schemas import (
    CalculatePriceRequest, CalculatePriceResponse, PricingTierCreate,
    PricingSettingUpdate, EnrichedProductRead
)
from backend.app.domains.pricing.domain.engine import PricingEngine
from backend.app.domains.pricing.domain.enums import PricingMethod, TieredMode
from backend.app.domains.pricing.domain.strategies import validate_tiers
from backend.app.domains.pricing.infrastructure.repositories import (
    ProductPricingTierRepository, ProductPricingSettingRepository
)
from backend.app.domains.pricing.repositories import PricingAuditLogRepository
from backend.app.domains.pricing.models import ProductPricingTier, ProductPricingSetting
from backend.app.core.exceptions import DomainValidationError, EntityNotFoundError

class PricingApplicationService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.catalog_service = CatalogService(db)
        self.tier_repo = ProductPricingTierRepository(db)
        self.setting_repo = ProductPricingSettingRepository(db)
        self.audit_repo = PricingAuditLogRepository(db)

    async def get_or_create_pricing_setting(self, product_id: int) -> ProductPricingSetting:
        await self.catalog_service.get_product(product_id)
        setting = await self.setting_repo.get_by_product_id(product_id)
        if not setting:
            setting = ProductPricingSetting(
                product_id=product_id,
                pricing_method=PricingMethod.STANDARD.value,
                markup_percent=0.00,
                status="ACTIVE",
                discount_percent=0.00
            )
            self.db.add(setting)
            await self.db.flush()
            await self.db.commit()
        return setting

    async def update_pricing_setting(self, product_id: int, schema: PricingSettingUpdate) -> ProductPricingSetting:
        await self.catalog_service.get_product(product_id)
        if schema.markup_percent < Decimal("0.00"):
            raise DomainValidationError("Markup percentage cannot be negative.")
        if schema.discount_percent is not None:
            if schema.discount_percent < Decimal("0.00") or schema.discount_percent > Decimal("100.00"):
                raise DomainValidationError("Discount must be between 0 and 100.")
            
        valid_statuses = {"DRAFT", "ACTIVE", "INACTIVE", "ARCHIVED"}
        status_val = schema.status.upper() if schema.status else "ACTIVE"
        if status_val not in valid_statuses:
            raise DomainValidationError(f"Invalid pricing configuration status: {status_val}. Must be one of {valid_statuses}")

        if schema.effective_from and schema.effective_until:
            eff_from = schema.effective_from if schema.effective_from.tzinfo else schema.effective_from.replace(tzinfo=timezone.utc)
            eff_until = schema.effective_until if schema.effective_until.tzinfo else schema.effective_until.replace(tzinfo=timezone.utc)
            if eff_until <= eff_from:
                raise DomainValidationError("Effective until date must be after effective from date.")

        setting = await self.setting_repo.create_or_update(
            product_id=product_id,
            method=schema.pricing_method.value,
            markup_percent=float(schema.markup_percent),
            status=status_val,
            effective_from=schema.effective_from,
            effective_until=schema.effective_until,
            discount_percent=float(schema.discount_percent) if schema.discount_percent is not None else 0.00
        )
        await self.db.commit()
        return setting

    async def activate_pricing_setting(self, product_id: int) -> ProductPricingSetting:
        setting = await self.get_or_create_pricing_setting(product_id)
        setting.status = "ACTIVE"
        self.db.add(setting)
        await self.db.commit()
        return setting

    async def deactivate_pricing_setting(self, product_id: int) -> ProductPricingSetting:
        setting = await self.get_or_create_pricing_setting(product_id)
        setting.status = "INACTIVE"
        self.db.add(setting)
        await self.db.commit()
        return setting

    async def list_enriched_products(self, has_cost_view: bool = False, has_margin_view: bool = False) -> List[EnrichedProductRead]:
        # Fetch all products
        result = await self.db.execute(select(Product).options(selectinload(Product.category)))
        products = result.scalars().all()
        
        enriched = []
        for p in products:
            # Get setting
            setting = await self.setting_repo.get_by_product_id(p.id)
            method = PricingMethod(setting.pricing_method) if setting else PricingMethod.STANDARD
            markup = Decimal(str(setting.markup_percent)) if setting else Decimal("0.00")
            discount = Decimal(str(setting.discount_percent)) if (setting and setting.discount_percent is not None) else Decimal("0.00")
            status_val = setting.status if setting else "ACTIVE"
            eff_from = setting.effective_from if setting else None
            eff_until = setting.effective_until if setting else None

            # Check tiers
            tiers = await self.tier_repo.get_by_product_id(p.id)
            has_tiers = len(tiers) > 0

            # Calculate margin percentage if authorized
            margin_pct = None
            if has_margin_view and p.cost_price is not None and p.base_price > 0:
                bp_dec = Decimal(str(p.base_price))
                cp_dec = Decimal(str(p.cost_price))
                margin_pct = (((bp_dec - cp_dec) / bp_dec) * Decimal("100.00")).quantize(Decimal("0.01"))
            
            enriched.append(EnrichedProductRead(
                id=p.id,
                sku=p.sku,
                name=p.name,
                description=p.description,
                base_price=Decimal(str(p.base_price)),
                cost_price=Decimal(str(p.cost_price)) if (p.cost_price is not None and has_cost_view) else None,
                margin_percentage=margin_pct,
                currency=p.currency,
                is_active=p.is_active,
                billing_type=p.billing_type,
                category_name=p.category.name if p.category else None,
                pricing_method=method,
                markup_percent=markup,
                discount_percent=discount,
                status=status_val,
                effective_from=eff_from,
                effective_until=eff_until,
                has_tiers=has_tiers
            ))
        return enriched

    async def create_pricing_tiers(self, product_id: int, schemas: List[PricingTierCreate]) -> List[ProductPricingTier]:
        product = await self.catalog_service.get_product(product_id)
        if not schemas:
            raise DomainValidationError("At least one tier configuration must be provided.")
            
        validated_sorted = validate_tiers(schemas)
        await self.tier_repo.delete_by_product_id(product_id)
        
        saved_tiers = []
        for idx, s in enumerate(validated_sorted, start=1):
            db_tier = ProductPricingTier(
                product_id=product_id,
                pricing_method=s.pricing_method.value,
                tiered_mode=s.tiered_mode.value if s.tiered_mode else None,
                min_quantity=s.min_quantity,
                max_quantity=s.max_quantity,
                price=s.price,
                display_order=s.display_order if getattr(s, "display_order", None) else idx,
                is_active=s.is_active if getattr(s, "is_active", None) is not None else True
            )
            saved_tier = await self.tier_repo.create(db_tier)
            saved_tiers.append(saved_tier)
            
        await self.db.commit()
        return saved_tiers

    async def get_pricing_tiers(self, product_id: int) -> List[ProductPricingTier]:
        await self.catalog_service.get_product(product_id)
        return await self.tier_repo.get_by_product_id(product_id)

    async def delete_pricing_tiers(self, product_id: int) -> None:
        await self.catalog_service.get_product(product_id)
        await self.tier_repo.delete_by_product_id(product_id)
        await self.db.commit()

    async def calculate_price(
        self,
        request: CalculatePriceRequest,
        user_permissions: Optional[Set[str]] = None,
        user_id: Optional[uuid.UUID] = None,
        user_role: Optional[str] = None
    ) -> CalculatePriceResponse:
        permissions = user_permissions or set()

        # 1. Validation - Quantity
        if request.quantity <= 0:
            raise DomainValidationError("Invalid quantity.")

        # 2. Retrieve Product from catalog
        product = await self.catalog_service.get_product(request.product_id)

        # 3. Product active status check
        if not product.is_active:
            raise DomainValidationError("Product is inactive.")

        # 4. Resolve Pricing Method & Configuration
        setting = await self.setting_repo.get_by_product_id(request.product_id)
        pricing_method = request.pricing_method
        if pricing_method is None:
            pricing_method = PricingMethod(setting.pricing_method) if setting else PricingMethod.STANDARD

        # 5. Configuration Lifecycle & Effective Dates Validation
        if setting:
            status_val = setting.status.upper() if setting.status else "ACTIVE"
            if status_val in ("INACTIVE", "ARCHIVED"):
                raise DomainValidationError("Pricing configuration is inactive.")
            if status_val == "DRAFT":
                raise DomainValidationError("Pricing configuration is in draft status and cannot be used for live pricing.")

            now = datetime.now(timezone.utc)
            if setting.effective_until:
                eff_until = setting.effective_until if setting.effective_until.tzinfo else setting.effective_until.replace(tzinfo=timezone.utc)
                if now >= eff_until:
                    raise DomainValidationError("Pricing configuration has expired.")
            if setting.effective_from:
                eff_from = setting.effective_from if setting.effective_from.tzinfo else setting.effective_from.replace(tzinfo=timezone.utc)
                if now < eff_from:
                    raise DomainValidationError("Pricing configuration is not yet effective.")

        # 6. Validation - Discount range (if using LINE_DISCOUNT)
        discount_percent = request.discount_percent
        if pricing_method == PricingMethod.LINE_DISCOUNT:
            if request.custom_markup_percent is not None:
                discount_percent = request.custom_markup_percent
            elif discount_percent is None or discount_percent == Decimal("0.00"):
                if setting and setting.discount_percent:
                    discount_percent = Decimal(str(setting.discount_percent))
                elif setting and setting.pricing_method == PricingMethod.LINE_DISCOUNT.value:
                    discount_percent = Decimal(str(setting.markup_percent))
            if discount_percent is None:
                discount_percent = Decimal("0.00")
            if discount_percent < Decimal("0.00") or discount_percent > Decimal("100.00"):
                raise DomainValidationError("Discount must be between 0 and 100.")
        else:
            discount_percent = Decimal("0.00")

        # 7. Load tiers if TIERED or BLOCK is requested
        tiers_list = []
        req_tiered_mode = None
        if pricing_method in (PricingMethod.TIERED, PricingMethod.BLOCK):
            if request.custom_tiers is not None:
                validated_sorted = validate_tiers(request.custom_tiers)
                tiers_list = [
                    ProductPricingTier(
                        product_id=request.product_id,
                        pricing_method=s.pricing_method.value,
                        tiered_mode=s.tiered_mode.value if s.tiered_mode else None,
                        min_quantity=s.min_quantity,
                        max_quantity=s.max_quantity,
                        price=s.price,
                        display_order=getattr(s, "display_order", 1),
                        is_active=getattr(s, "is_active", True)
                    ) for s in validated_sorted
                ]
            else:
                db_tiers = await self.tier_repo.get_by_product_id(request.product_id)
                if not db_tiers:
                    raise DomainValidationError(f"No pricing tiers configured for product {request.product_id}.")
                method_tiers = [t for t in db_tiers if t.pricing_method == pricing_method.value and getattr(t, "is_active", True)]
                if not method_tiers:
                    raise DomainValidationError(
                        f"Product has tiers configured, but none for pricing method: {pricing_method.value}"
                    )
                tiers_list = method_tiers
            
            if pricing_method == PricingMethod.TIERED:
                req_tiered_mode = request.tiered_mode
                if not req_tiered_mode:
                    config_mode = tiers_list[0].tiered_mode if tiers_list else None
                    if config_mode:
                        req_tiered_mode = TieredMode(config_mode)
                    else:
                        raise DomainValidationError("Tiered pricing mode (VOLUME or CUMULATIVE) must be specified.")

        # 8. Load Cost + Markup settings if requested
        cost_price = None
        markup_percent = None
        if pricing_method == PricingMethod.COST_PLUS_MARKUP:
            if product.cost_price is None or float(product.cost_price) < 0:
                raise DomainValidationError("Product must have a valid cost configured for Cost + Markup pricing.")
            
            cost_price = Decimal(str(product.cost_price))
            
            if request.custom_markup_percent is not None:
                markup_percent = request.custom_markup_percent
            else:
                markup_percent = Decimal(str(setting.markup_percent)) if setting else Decimal("0.00")
            if markup_percent < Decimal("0.00"):
                raise DomainValidationError("Markup percentage cannot be negative.")
        elif product.cost_price is not None:
            cost_price = Decimal(str(product.cost_price))

        # 9. Resolve Base Price (standard fallback)
        base_price_float = await self.catalog_service.get_product_price(
            product_id=request.product_id,
            price_book_id=request.price_book_id
        )
        base_price = Decimal(str(base_price_float))

        # 10. Execute calculation via Domain Engine
        calc_dict = PricingEngine.calculate(
            product_id=product.id,
            sku=product.sku,
            name=product.name,
            billing_type=product.billing_type,
            currency=product.currency,
            base_price=base_price,
            quantity=request.quantity,
            pricing_method=pricing_method,
            discount_percent=discount_percent,
            tiers=tiers_list,
            tiered_mode=req_tiered_mode,
            cost_price=cost_price,
            markup_percent=markup_percent
        )

        # 11. Manual Pricing Override (Permission: pricing.override)
        if request.override_unit_price is not None:
            if "pricing.override" not in permissions:
                raise HTTPException(
                    status_code=403,
                    detail="Permission 'pricing.override' required for manual price override."
                )
            if not request.override_reason:
                raise DomainValidationError("A reason must be provided for manual price override.")

            orig_unit_price = calc_dict["final_unit_price"]
            orig_total_price = calc_dict["total_price"]

            override_unit = request.override_unit_price.quantize(Decimal("0.01"))
            override_total = (override_unit * request.quantity).quantize(Decimal("0.01"))

            calc_dict["final_unit_price"] = override_unit
            calc_dict["total_price"] = override_total

            # Recalculate margins with override price
            if calc_dict["total_cost"] is not None:
                calc_dict["margin_amount"] = (override_total - calc_dict["total_cost"]).quantize(Decimal("0.01"))
                if override_total > Decimal("0.00"):
                    calc_dict["margin_percentage"] = (
                        ((override_total - calc_dict["total_cost"]) / override_total) * Decimal("100.00")
                    ).quantize(Decimal("0.01"))
                else:
                    calc_dict["margin_percentage"] = None

            calc_dict["calculation_breakdown"].append({
                "description": f"Manual price override applied: from {orig_unit_price} to {override_unit}. Reason: {request.override_reason}",
                "tier": "Override",
                "quantity": request.quantity,
                "unit_price": f"{override_unit:.2f}",
                "amount": f"{override_total:.2f}"
            })

            # Audit log for manual override
            await self.audit_repo.log(
                user_id=user_id,
                user_role=user_role or "Unknown",
                action="PRICING_OVERRIDE_USED",
                product_id=product.id,
                before_value={"final_unit_price": str(orig_unit_price), "total_price": str(orig_total_price)},
                after_value={
                    "final_unit_price": str(override_unit),
                    "total_price": str(override_total),
                    "reason": request.override_reason
                }
            )
            await self.db.commit()

        # 12. Sensitive Data RBAC Masking
        has_cost_view = "pricing.cost.view" in permissions
        has_margin_view = "pricing.margin.view" in permissions

        if not has_cost_view:
            calc_dict["unit_cost"] = None
            calc_dict["total_cost"] = None
        if not has_margin_view:
            calc_dict["margin_amount"] = None
            calc_dict["margin_percentage"] = None

        return CalculatePriceResponse(**calc_dict)
