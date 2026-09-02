from decimal import Decimal
from typing import List
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
from backend.app.domains.pricing.models import ProductPricingTier, ProductPricingSetting
from backend.app.core.exceptions import DomainValidationError, EntityNotFoundError

class PricingApplicationService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.catalog_service = CatalogService(db)
        self.tier_repo = ProductPricingTierRepository(db)
        self.setting_repo = ProductPricingSettingRepository(db)

    async def get_or_create_pricing_setting(self, product_id: int) -> ProductPricingSetting:
        await self.catalog_service.get_product(product_id)
        setting = await self.setting_repo.get_by_product_id(product_id)
        if not setting:
            setting = ProductPricingSetting(
                product_id=product_id,
                pricing_method=PricingMethod.STANDARD.value,
                markup_percent=0.00
            )
            self.db.add(setting)
            await self.db.flush()
            await self.db.commit()
        return setting

    async def update_pricing_setting(self, product_id: int, schema: PricingSettingUpdate) -> ProductPricingSetting:
        await self.catalog_service.get_product(product_id)
        if schema.markup_percent < Decimal("0.00"):
            raise DomainValidationError("Markup percentage cannot be negative.")
            
        setting = await self.setting_repo.create_or_update(
            product_id=product_id,
            method=schema.pricing_method.value,
            markup_percent=float(schema.markup_percent)
        )
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
            
            # Check tiers
            tiers = await self.tier_repo.get_by_product_id(p.id)
            has_tiers = len(tiers) > 0

            # Calculate margin percentage if authorized
            margin_pct = None
            if has_margin_view and p.cost_price is not None and p.base_price > 0:
                bp_dec = Decimal(str(p.base_price))
                cp_dec = Decimal(str(p.cost_price))
                margin_pct = ((bp_dec - cp_dec) / bp_dec) * Decimal("100.00")
            
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
        for s in validated_sorted:
            db_tier = ProductPricingTier(
                product_id=product_id,
                pricing_method=s.pricing_method.value,
                tiered_mode=s.tiered_mode.value if s.tiered_mode else None,
                min_quantity=s.min_quantity,
                max_quantity=s.max_quantity,
                price=s.price
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

    async def calculate_price(self, request: CalculatePriceRequest) -> CalculatePriceResponse:
        # 1. Validation - Quantity
        if request.quantity <= 0:
            raise DomainValidationError("Quantity must be a positive integer greater than zero.")

        # 2. Validation - Discount range (if using LINE_DISCOUNT)
        discount_percent = request.discount_percent
        if request.pricing_method == PricingMethod.LINE_DISCOUNT:
            if request.custom_markup_percent is not None:
                discount_percent = request.custom_markup_percent
            elif discount_percent is None or discount_percent == Decimal("0.00"):
                setting = await self.setting_repo.get_by_product_id(request.product_id)
                if setting and setting.pricing_method == PricingMethod.LINE_DISCOUNT.value:
                    discount_percent = Decimal(str(setting.markup_percent))
            if discount_percent is None:
                discount_percent = Decimal("0.00")
            if discount_percent < Decimal("0.00") or discount_percent > Decimal("100.00"):
                raise DomainValidationError("Discount percentage must be between 0 and 100.")
        else:
            discount_percent = Decimal("0.00")

        # 3. Retrieve Product from catalog
        product = await self.catalog_service.get_product(request.product_id)

        # 4. Load tiers if TIERED or BLOCK is requested
        tiers_list = []
        req_tiered_mode = None
        if request.pricing_method in (PricingMethod.TIERED, PricingMethod.BLOCK):
            if request.custom_tiers is not None:
                validated_sorted = validate_tiers(request.custom_tiers)
                tiers_list = [
                    ProductPricingTier(
                        product_id=request.product_id,
                        pricing_method=s.pricing_method.value,
                        tiered_mode=s.tiered_mode.value if s.tiered_mode else None,
                        min_quantity=s.min_quantity,
                        max_quantity=s.max_quantity,
                        price=s.price
                    ) for s in validated_sorted
                ]
            else:
                db_tiers = await self.tier_repo.get_by_product_id(request.product_id)
                if not db_tiers:
                    raise DomainValidationError(f"No pricing tiers configured for product {request.product_id}.")
                method_tiers = [t for t in db_tiers if t.pricing_method == request.pricing_method.value]
                if not method_tiers:
                    raise DomainValidationError(
                        f"Product has tiers configured, but none for pricing method: {request.pricing_method.value}"
                    )
                tiers_list = method_tiers
            
            if request.pricing_method == PricingMethod.TIERED:
                req_tiered_mode = request.tiered_mode
                if not req_tiered_mode:
                    config_mode = tiers_list[0].tiered_mode if tiers_list else None
                    if config_mode:
                        req_tiered_mode = TieredMode(config_mode)
                    else:
                        raise DomainValidationError("Tiered pricing mode (VOLUME or CUMULATIVE) must be specified.")

        # 5. Load Cost + Markup settings if requested
        cost_price = None
        markup_percent = None
        if request.pricing_method == PricingMethod.COST_PLUS_MARKUP:
            if product.cost_price is None or float(product.cost_price) < 0:
                raise DomainValidationError("Product must have a valid cost configured for Cost + Markup pricing.")
            
            cost_price = Decimal(str(product.cost_price))
            
            if request.custom_markup_percent is not None:
                markup_percent = request.custom_markup_percent
            else:
                setting = await self.setting_repo.get_by_product_id(request.product_id)
                markup_percent = Decimal(str(setting.markup_percent)) if setting else Decimal("0.00")
            if markup_percent < Decimal("0.00"):
                raise DomainValidationError("Markup percentage cannot be negative.")

        # 6. Resolve Base Price (standard fallback)
        base_price_float = await self.catalog_service.get_product_price(
            product_id=request.product_id,
            price_book_id=request.price_book_id
        )
        base_price = Decimal(str(base_price_float))

        # 7. Execute calculation via Domain Engine
        calc_dict = PricingEngine.calculate(
            product_id=product.id,
            sku=product.sku,
            name=product.name,
            billing_type=product.billing_type,
            currency=product.currency,
            base_price=base_price,
            quantity=request.quantity,
            pricing_method=request.pricing_method,
            discount_percent=discount_percent,
            tiers=tiers_list,
            tiered_mode=req_tiered_mode,
            cost_price=cost_price,
            markup_percent=markup_percent
        )

        return CalculatePriceResponse(**calc_dict)
