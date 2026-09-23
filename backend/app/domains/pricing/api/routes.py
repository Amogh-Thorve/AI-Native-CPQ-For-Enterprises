from fastapi import APIRouter, Depends, status, HTTPException
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.core.database import get_db
from backend.app.domains.auth.dependencies import PermissionChecker
from backend.app.domains.auth.models import User
from backend.app.domains.pricing.api.schemas import (
    CalculatePriceRequest, CalculatePriceResponse, PricingTierCreate, PricingTierRead,
    PricingSettingRead, PricingSettingUpdate, EnrichedProductRead
)
from backend.app.domains.pricing.schemas import PricingRuleCreate, PricingRuleRead, PricingRuleUpdate
from backend.app.domains.pricing.repositories import PricingAuditLogRepository, PricingRuleRepository
from backend.app.domains.pricing.application.services import PricingApplicationService

router = APIRouter(prefix="/pricing", tags=["pricing-engine"])

@router.post("/calculate", response_model=CalculatePriceResponse, status_code=status.HTTP_200_OK)
async def calculate_price(
    request: CalculatePriceRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker("pricing.calculate"))
):
    """
    Evaluate pricing for a product line item based on selected method and quantity.
    Enforces server-side validation, lifecycle status, effective dates, and sensitive data masking.
    """
    user_permissions = {p.name for r in current_user.roles for p in r.permissions}
    role_name = current_user.roles[0].name if current_user.roles else "Unknown"
    service = PricingApplicationService(db)
    return await service.calculate_price(
        request=request,
        user_permissions=user_permissions,
        user_id=current_user.id,
        user_role=role_name
    )

@router.get("/products", response_model=List[EnrichedProductRead], status_code=status.HTTP_200_OK)
async def list_products_with_pricing(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker("pricing.calculate"))
):
    """
    Get all products from the catalog enriched with their active pricing configurations (method, markup, tiers status).
    Sensitive fields (cost_price) are filtered out if user lacks pricing.cost.view.
    """
    user_permissions = {p.name for r in current_user.roles for p in r.permissions}
    has_cost_view = "pricing.cost.view" in user_permissions
    has_margin_view = "pricing.margin.view" in user_permissions
    service = PricingApplicationService(db)
    return await service.list_enriched_products(has_cost_view=has_cost_view, has_margin_view=has_margin_view)

@router.get("/products/{product_id}/configuration", response_model=PricingSettingRead, status_code=status.HTTP_200_OK)
async def get_product_pricing_configuration(
    product_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker("pricing.config.view"))
):
    """
    Retrieve default pricing configuration (pricing method, markup percentage) for a product.
    """
    service = PricingApplicationService(db)
    return await service.get_or_create_pricing_setting(product_id)

@router.post("/products/{product_id}/configuration", response_model=PricingSettingRead, status_code=status.HTTP_200_OK)
async def configure_product_pricing(
    product_id: int,
    schema: PricingSettingUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker("pricing.config.update"))
):
    """
    Configure global pricing method and markup percentage for a catalog product.
    """
    service = PricingApplicationService(db)
    old_setting = await service.setting_repo.get_by_product_id(product_id)
    before_val = {
        "pricing_method": old_setting.pricing_method,
        "markup_percent": str(old_setting.markup_percent),
        "status": old_setting.status,
        "effective_from": str(old_setting.effective_from) if old_setting.effective_from else None,
        "effective_until": str(old_setting.effective_until) if old_setting.effective_until else None,
        "discount_percent": str(old_setting.discount_percent) if old_setting.discount_percent is not None else "0.00"
    } if old_setting else None
    
    updated_setting = await service.update_pricing_setting(product_id, schema)
    after_val = {
        "pricing_method": updated_setting.pricing_method,
        "markup_percent": str(updated_setting.markup_percent),
        "status": updated_setting.status,
        "effective_from": str(updated_setting.effective_from) if updated_setting.effective_from else None,
        "effective_until": str(updated_setting.effective_until) if updated_setting.effective_until else None,
        "discount_percent": str(updated_setting.discount_percent) if updated_setting.discount_percent is not None else "0.00"
    }

    # Log audit
    audit_repo = PricingAuditLogRepository(db)
    role_name = current_user.roles[0].name if current_user.roles else "Unknown"
    await audit_repo.log(
        user_id=current_user.id,
        user_role=role_name,
        action="PRICING_CONFIGURATION_UPDATED" if old_setting else "PRICING_CONFIGURATION_CREATED",
        pricing_config_id=updated_setting.id,
        product_id=product_id,
        before_value=before_val,
        after_value=after_val
    )
    await db.commit()
    return updated_setting

@router.post("/products/{product_id}/configuration/activate", response_model=PricingSettingRead, status_code=status.HTTP_200_OK)
@router.patch("/products/{product_id}/configuration/activate", response_model=PricingSettingRead, status_code=status.HTTP_200_OK)
async def activate_product_pricing_configuration(
    product_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker("pricing.config.update"))
):
    """
    Activate pricing configuration for a catalog product.
    """
    service = PricingApplicationService(db)
    old_setting = await service.setting_repo.get_by_product_id(product_id)
    before_val = {"status": old_setting.status} if old_setting else None
    
    updated_setting = await service.activate_pricing_setting(product_id)
    
    # Log audit
    audit_repo = PricingAuditLogRepository(db)
    role_name = current_user.roles[0].name if current_user.roles else "Unknown"
    await audit_repo.log(
        user_id=current_user.id,
        user_role=role_name,
        action="PRICING_CONFIGURATION_ACTIVATED",
        pricing_config_id=updated_setting.id,
        product_id=product_id,
        before_value=before_val,
        after_value={"status": "ACTIVE"}
    )
    await db.commit()
    return updated_setting

@router.post("/products/{product_id}/configuration/deactivate", response_model=PricingSettingRead, status_code=status.HTTP_200_OK)
@router.patch("/products/{product_id}/configuration/deactivate", response_model=PricingSettingRead, status_code=status.HTTP_200_OK)
async def deactivate_product_pricing_configuration(
    product_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker("pricing.config.deactivate"))
):
    """
    Deactivate pricing configuration for a catalog product.
    """
    service = PricingApplicationService(db)
    old_setting = await service.setting_repo.get_by_product_id(product_id)
    before_val = {"status": old_setting.status} if old_setting else None
    
    updated_setting = await service.deactivate_pricing_setting(product_id)
    
    # Log audit
    audit_repo = PricingAuditLogRepository(db)
    role_name = current_user.roles[0].name if current_user.roles else "Unknown"
    await audit_repo.log(
        user_id=current_user.id,
        user_role=role_name,
        action="PRICING_CONFIGURATION_DEACTIVATED",
        pricing_config_id=updated_setting.id,
        product_id=product_id,
        before_value=before_val,
        after_value={"status": "INACTIVE"}
    )
    await db.commit()
    return updated_setting

@router.post("/products/{product_id}/tiers", response_model=List[PricingTierRead], status_code=status.HTTP_201_CREATED)
async def create_product_pricing_tiers(
    product_id: int,
    tiers: List[PricingTierCreate],
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker("pricing.config.update"))
):
    """
    Configure pricing tiers/blocks for a specific product. Overwrites existing tier configurations.
    """
    service = PricingApplicationService(db)
    old_tiers = await service.get_pricing_tiers(product_id)
    before_val = {"tiers": [{"min_quantity": t.min_quantity, "max_quantity": t.max_quantity, "price": str(t.price)} for t in old_tiers]}
    
    new_tiers = await service.create_pricing_tiers(product_id, tiers)
    after_val = {"tiers": [{"min_quantity": t.min_quantity, "max_quantity": t.max_quantity, "price": str(t.price)} for t in new_tiers]}

    # Log audit
    audit_repo = PricingAuditLogRepository(db)
    role_name = current_user.roles[0].name if current_user.roles else "Unknown"
    await audit_repo.log(
        user_id=current_user.id,
        user_role=role_name,
        action="PRICING_CONFIGURATION_UPDATED",
        product_id=product_id,
        before_value=before_val,
        after_value=after_val
    )
    await db.commit()
    return new_tiers

@router.get("/products/{product_id}/tiers", response_model=List[PricingTierRead], status_code=status.HTTP_200_OK)
async def get_product_pricing_tiers(
    product_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker("pricing.config.view"))
):
    """
    Retrieve all configured pricing tiers/blocks for a specific product.
    """
    service = PricingApplicationService(db)
    return await service.get_pricing_tiers(product_id)

@router.delete("/products/{product_id}/tiers", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product_pricing_tiers(
    product_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker("pricing.config.deactivate"))
):
    """
    Delete all configured pricing tiers/blocks for a specific product.
    """
    service = PricingApplicationService(db)
    old_tiers = await service.get_pricing_tiers(product_id)
    before_val = {"tiers": [{"min_quantity": t.min_quantity, "max_quantity": t.max_quantity, "price": str(t.price)} for t in old_tiers]}

    await service.delete_pricing_tiers(product_id)

    # Log audit
    audit_repo = PricingAuditLogRepository(db)
    role_name = current_user.roles[0].name if current_user.roles else "Unknown"
    await audit_repo.log(
        user_id=current_user.id,
        user_role=role_name,
        action="PRICING_CONFIGURATION_DEACTIVATED",
        product_id=product_id,
        before_value=before_val,
        after_value=None
    )
    await db.commit()

# --- Pricing Rules Routes ---

@router.post("/rules", response_model=PricingRuleRead, status_code=status.HTTP_201_CREATED)
async def create_pricing_rule(
    schema: PricingRuleCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker("pricing.rule.create"))
):
    """
    Add a new dynamic pricing rule. Restricted to Executive/Admin.
    """
    rule_repo = PricingRuleRepository(db)
    rule = await rule_repo.create(schema, user_id=current_user.id)
    
    # Log audit
    audit_repo = PricingAuditLogRepository(db)
    role_name = current_user.roles[0].name if current_user.roles else "Unknown"
    await audit_repo.log(
        user_id=current_user.id,
        user_role=role_name,
        action="PRICING_RULE_CREATED",
        before_value=None,
        after_value={
            "name": rule.name,
            "rule_type": rule.rule_type,
            "is_active": rule.is_active,
            "conditions": rule.conditions,
            "actions": rule.actions,
            "status": rule.status
        }
    )
    await db.commit()
    return rule

@router.get("/rules", response_model=List[PricingRuleRead], status_code=status.HTTP_200_OK)
async def list_pricing_rules(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker("pricing.calculate"))
):
    """
    Get all active pricing configuration rules.
    """
    rule_repo = PricingRuleRepository(db)
    return await rule_repo.list_active()

@router.put("/rules/{rule_id}", response_model=PricingRuleRead, status_code=status.HTTP_200_OK)
async def update_pricing_rule(
    rule_id: int,
    schema: PricingRuleUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker("pricing.rule.update"))
):
    """
    Update an existing pricing rule. Restricted to Executive/Admin.
    """
    rule_repo = PricingRuleRepository(db)
    rule = await rule_repo.get_by_id(rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Pricing rule not found")
        
    before_val = {
        "name": rule.name,
        "rule_type": rule.rule_type,
        "is_active": rule.is_active,
        "conditions": rule.conditions,
        "actions": rule.actions,
        "status": rule.status
    }
    
    updated_rule = await rule_repo.update(rule, schema, user_id=current_user.id)
    
    # Log audit
    audit_repo = PricingAuditLogRepository(db)
    role_name = current_user.roles[0].name if current_user.roles else "Unknown"
    await audit_repo.log(
        user_id=current_user.id,
        user_role=role_name,
        action="PRICING_RULE_UPDATED",
        before_value=before_val,
        after_value={
            "name": updated_rule.name,
            "rule_type": updated_rule.rule_type,
            "is_active": updated_rule.is_active,
            "conditions": updated_rule.conditions,
            "actions": updated_rule.actions,
            "status": updated_rule.status
        }
    )
    await db.commit()
    return updated_rule

@router.delete("/rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_pricing_rule(
    rule_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker("pricing.rule.delete"))
):
    """
    Delete an existing pricing rule. Restricted to Executive/Admin.
    """
    rule_repo = PricingRuleRepository(db)
    rule = await rule_repo.get_by_id(rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Pricing rule not found")
        
    before_val = {
        "name": rule.name,
        "rule_type": rule.rule_type,
        "is_active": rule.is_active,
        "conditions": rule.conditions,
        "actions": rule.actions,
        "status": rule.status
    }
    
    await db.delete(rule)
    
    # Log audit
    audit_repo = PricingAuditLogRepository(db)
    role_name = current_user.roles[0].name if current_user.roles else "Unknown"
    await audit_repo.log(
        user_id=current_user.id,
        user_role=role_name,
        action="PRICING_RULE_DELETED",
        before_value=before_val,
        after_value=None
    )
    await db.commit()
