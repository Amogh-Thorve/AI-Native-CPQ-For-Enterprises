from typing import List, Optional
import uuid
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.domains.pricing.models import PricingRule, PricingAuditLog
from backend.app.domains.pricing.schemas import PricingRuleCreate, PricingRuleUpdate

class PricingRuleRepository:
    """
    Handles persistence logic for Dynamic Pricing Rules.
    """
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, rule_id: int) -> Optional[PricingRule]:
        result = await self.db.execute(select(PricingRule).where(PricingRule.id == rule_id))
        return result.scalars().first()

    async def list_active(self) -> List[PricingRule]:
        """
        List all rules currently flagged as active.
        """
        result = await self.db.execute(
            select(PricingRule).where(PricingRule.is_active == True)
        )
        return list(result.scalars().all())

    async def create(self, schema: PricingRuleCreate, user_id: Optional[uuid.UUID] = None) -> PricingRule:
        db_rule = PricingRule(**schema.model_dump())
        if user_id:
            db_rule.created_by = user_id
            db_rule.updated_by = user_id
        db_rule.status = "ACTIVE" if schema.is_active else "INACTIVE"
        self.db.add(db_rule)
        await self.db.flush()
        return db_rule

    async def update(self, db_rule: PricingRule, schema: PricingRuleUpdate, user_id: Optional[uuid.UUID] = None) -> PricingRule:
        for field, value in schema.model_dump(exclude_unset=True).items():
            setattr(db_rule, field, value)
        if schema.is_active is not None:
            db_rule.status = "ACTIVE" if schema.is_active else "INACTIVE"
        if user_id:
            db_rule.updated_by = user_id
        db_rule.updated_at = func.now()
        self.db.add(db_rule)
        await self.db.flush()
        return db_rule

class PricingAuditLogRepository:
    """
    Handles logging for administrative pricing configuration edits.
    """
    def __init__(self, db: AsyncSession):
        self.db = db

    async def log(
        self,
        user_id: Optional[uuid.UUID],
        user_role: Optional[str],
        action: str,
        pricing_config_id: Optional[int] = None,
        product_id: Optional[int] = None,
        before_value: Optional[dict] = None,
        after_value: Optional[dict] = None
    ) -> PricingAuditLog:
        log_entry = PricingAuditLog(
            user_id=user_id,
            user_role=user_role,
            action=action,
            pricing_config_id=pricing_config_id,
            product_id=product_id,
            before_value=before_value,
            after_value=after_value
        )
        self.db.add(log_entry)
        await self.db.flush()
        return log_entry

