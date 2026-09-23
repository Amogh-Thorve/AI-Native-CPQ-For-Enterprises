from typing import List, Optional, Any
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.domains.pricing.models import ProductPricingTier, ProductPricingSetting

class ProductPricingTierRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_product_id(self, product_id: int) -> List[ProductPricingTier]:
        """
        Get all pricing tiers configured for a product, sorted by display_order and min_quantity.
        """
        result = await self.db.execute(
            select(ProductPricingTier)
            .where(ProductPricingTier.product_id == product_id)
            .order_by(ProductPricingTier.display_order, ProductPricingTier.min_quantity)
        )
        return list(result.scalars().all())

    async def delete_by_product_id(self, product_id: int) -> None:
        """
        Delete all tiers configured for a product.
        """
        await self.db.execute(
            delete(ProductPricingTier).where(ProductPricingTier.product_id == product_id)
        )

    async def create(self, tier: ProductPricingTier) -> ProductPricingTier:
        self.db.add(tier)
        await self.db.flush()
        return tier

class ProductPricingSettingRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_product_id(self, product_id: int) -> Optional[ProductPricingSetting]:
        result = await self.db.execute(
            select(ProductPricingSetting).where(ProductPricingSetting.product_id == product_id)
        )
        return result.scalars().first()

    async def create_or_update(
        self,
        product_id: int,
        method: str,
        markup_percent: float,
        status: str = "ACTIVE",
        effective_from: Optional[Any] = None,
        effective_until: Optional[Any] = None,
        discount_percent: float = 0.00
    ) -> ProductPricingSetting:
        existing = await self.get_by_product_id(product_id)
        if existing:
            existing.pricing_method = method
            existing.markup_percent = markup_percent
            existing.status = status
            existing.effective_from = effective_from
            existing.effective_until = effective_until
            existing.discount_percent = discount_percent
            self.db.add(existing)
            await self.db.flush()
            return existing
        else:
            new_setting = ProductPricingSetting(
                product_id=product_id,
                pricing_method=method,
                markup_percent=markup_percent,
                status=status,
                effective_from=effective_from,
                effective_until=effective_until,
                discount_percent=discount_percent
            )
            self.db.add(new_setting)
            await self.db.flush()
            return new_setting

