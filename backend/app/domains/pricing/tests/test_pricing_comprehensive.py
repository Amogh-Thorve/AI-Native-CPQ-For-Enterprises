import pytest
import uuid
import httpx
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from fastapi import status
from sqlalchemy import select, delete

from backend.app.main import app
from backend.app.core.database import SessionLocal
from backend.app.core.exceptions import DomainValidationError, EntityNotFoundError
from backend.app.domains.auth.services import AuthService
from backend.app.domains.auth.schemas import UserCreate, LoginRequest
from backend.app.domains.auth.models import User, Role, UserRole
from backend.app.domains.catalog.models import Product, Category
from backend.app.domains.pricing.domain.enums import PricingMethod, TieredMode
from backend.app.domains.pricing.domain.engine import PricingEngine
from backend.app.domains.pricing.domain.strategies import (
    StandardPricingStrategy,
    LineDiscountPricingStrategy,
    TieredPricingStrategy,
    BlockPricingStrategy,
    CostPlusMarkupPricingStrategy,
    get_pricing_strategy
)
from backend.app.domains.pricing.models import (
    ProductPricingSetting,
    ProductPricingTier,
    PricingRule,
    PricingAuditLog
)

class MockTier:
    def __init__(self, min_qty, max_qty, price, display_order=0, is_active=True):
        self.min_quantity = min_qty
        self.max_quantity = max_qty
        self.price = price
        self.display_order = display_order
        self.is_active = is_active

# ==============================================================================
# 1. SPECIFICATION MATHEMATICAL FORMULA TESTS
# ==============================================================================

def test_standard_pricing_spec():
    """
    Spec: Base Price = $1,000, Quantity = 5
    Unit Price = $1,000, Total = $5,000
    """
    strategy = StandardPricingStrategy()
    res = strategy.calculate(base_price=Decimal("1000.00"), quantity=5)
    assert res["base_unit_price"] == Decimal("1000.00")
    assert res["discount_percent"] == Decimal("0.00")
    assert res["discount_amount"] == Decimal("0.00")
    assert res["final_unit_price"] == Decimal("1000.00")
    assert res["total_price"] == Decimal("5000.00")

def test_line_discount_spec():
    """
    Spec: Base Price = $1,000, Discount = 10%, Quantity = 5
    Discount Amount per Unit = $100, Final Unit Price = $900, Total = $4,500
    """
    strategy = LineDiscountPricingStrategy()
    res = strategy.calculate(
        base_price=Decimal("1000.00"),
        quantity=5,
        discount_percent=Decimal("10.00")
    )
    assert res["base_unit_price"] == Decimal("1000.00")
    assert res["discount_percent"] == Decimal("10.00")
    assert res["discount_amount"] == Decimal("100.00")
    assert res["final_unit_price"] == Decimal("900.00")
    assert res["total_price"] == Decimal("4500.00")

def test_tiered_volume_spec():
    """
    Spec: 1-10 -> $100/unit, 11-50 -> $90/unit, 51+ -> $80/unit
    Quantity = 20 -> 20 * $90 = $1,800
    """
    strategy = TieredPricingStrategy()
    tiers = [
        MockTier(1, 10, Decimal("100.00")),
        MockTier(11, 50, Decimal("90.00")),
        MockTier(51, None, Decimal("80.00")),
    ]
    res = strategy.calculate(
        base_price=Decimal("100.00"),
        quantity=20,
        tiers=tiers,
        tiered_mode=TieredMode.VOLUME
    )
    assert res["final_unit_price"] == Decimal("90.00")
    assert res["total_price"] == Decimal("1800.00")

def test_tiered_cumulative_spec():
    """
    Spec: 1-10 = $100, 11-50 = $90
    Quantity = 20 -> First 10 * 100 = 1000, Next 10 * 90 = 900 -> Total = $1,900
    """
    strategy = TieredPricingStrategy()
    tiers = [
        MockTier(1, 10, Decimal("100.00")),
        MockTier(11, 50, Decimal("90.00")),
        MockTier(51, None, Decimal("80.00")),
    ]
    res = strategy.calculate(
        base_price=Decimal("100.00"),
        quantity=20,
        tiers=tiers,
        tiered_mode=TieredMode.CUMULATIVE
    )
    assert res["total_price"] == Decimal("1900.00")
    assert res["final_unit_price"] == Decimal("95.00")

def test_block_pricing_spec():
    """
    Spec: 1-10 -> $500, 11-50 -> $1,500, 51-100 -> $2,500
    Quantity = 7 -> Total = $500
    Quantity = 30 -> Total = $1,500
    Do NOT multiply block price by quantity.
    """
    strategy = BlockPricingStrategy()
    tiers = [
        MockTier(1, 10, Decimal("500.00")),
        MockTier(11, 50, Decimal("1500.00")),
        MockTier(51, 100, Decimal("2500.00")),
    ]
    res7 = strategy.calculate(base_price=Decimal("100.00"), quantity=7, tiers=tiers)
    assert res7["total_price"] == Decimal("500.00")
    assert res7["final_unit_price"] == (Decimal("500.00") / Decimal(7)).quantize(Decimal("0.01"))

    res30 = strategy.calculate(base_price=Decimal("100.00"), quantity=30, tiers=tiers)
    assert res30["total_price"] == Decimal("1500.00")
    assert res30["final_unit_price"] == (Decimal("1500.00") / Decimal(30)).quantize(Decimal("0.01"))

def test_cost_plus_markup_spec():
    """
    Spec: Cost = $800, Markup = 25% -> Selling Price: $800 * 1.25 = $1,000
    """
    strategy = CostPlusMarkupPricingStrategy()
    res = strategy.calculate(
        base_price=Decimal("100.00"),
        quantity=1,
        cost_price=Decimal("800.00"),
        markup_percent=Decimal("25.00")
    )
    assert res["final_unit_price"] == Decimal("1000.00")
    assert res["total_price"] == Decimal("1000.00")

# ==============================================================================
# 2. MARGIN CALCULATION SPECIFICATION TESTS
# ==============================================================================

def test_margin_positive_spec():
    """
    Spec: Selling Price = $1,000, Cost = $700
    Margin Amount = $300, Margin Percentage = 30%
    """
    result = PricingEngine.calculate(
        product_id=1,
        sku="TEST-SKU",
        name="Test Product",
        billing_type="MRC",
        currency="USD",
        base_price=Decimal("1000.00"),
        quantity=1,
        pricing_method=PricingMethod.STANDARD,
        cost_price=Decimal("700.00")
    )
    assert result["total_price"] == Decimal("1000.00")
    assert result["margin_amount"] == Decimal("300.00")
    assert result["margin_percentage"] == Decimal("30.00")

def test_margin_negative_spec():
    """
    Spec: Selling Price = $800, Cost = $1,000
    Margin = -$200, Margin % = -25%
    """
    result = PricingEngine.calculate(
        product_id=1,
        sku="TEST-SKU",
        name="Test Product",
        billing_type="NRC",
        currency="USD",
        base_price=Decimal("800.00"),
        quantity=1,
        pricing_method=PricingMethod.STANDARD,
        cost_price=Decimal("1000.00")
    )
    assert result["total_price"] == Decimal("800.00")
    assert result["margin_amount"] == Decimal("-200.00")
    assert result["margin_percentage"] == Decimal("-25.00")

def test_margin_zero_price_division_guard():
    """
    Spec: Selling Price = $0.00
    Do NOT divide by zero. Return margin_percentage = null.
    """
    result = PricingEngine.calculate(
        product_id=1,
        sku="TEST-FREE",
        name="Free Tier",
        billing_type="USAGE",
        currency="USD",
        base_price=Decimal("0.00"),
        quantity=1,
        pricing_method=PricingMethod.STANDARD,
        cost_price=Decimal("50.00")
    )
    assert result["total_price"] == Decimal("0.00")
    assert result["margin_amount"] == Decimal("-50.00")
    assert result["margin_percentage"] is None

# ==============================================================================
# 3. BILLING TYPES PRESERVATION TESTS
# ==============================================================================

@pytest.mark.parametrize("billing_type", ["MRC", "NRC", "USAGE"])
def test_billing_type_preservation(billing_type):
    result = PricingEngine.calculate(
        product_id=1,
        sku=f"SKU-{billing_type}",
        name=f"Product {billing_type}",
        billing_type=billing_type,
        currency="USD",
        base_price=Decimal("500.00"),
        quantity=3,
        pricing_method=PricingMethod.STANDARD
    )
    assert result["billing_type"] == billing_type
    assert result["currency"] == "USD"

# ==============================================================================
# 4. EDGE CASE VALIDATION TESTS
# ==============================================================================

def test_edge_case_negative_and_zero_quantity():
    with pytest.raises(DomainValidationError, match="Invalid quantity."):
        PricingEngine.calculate(
            product_id=1, sku="SKU-1", name="P1", billing_type="MRC", currency="USD",
            base_price=Decimal("100.00"), quantity=0, pricing_method=PricingMethod.STANDARD
        )
    with pytest.raises(DomainValidationError, match="Invalid quantity."):
        PricingEngine.calculate(
            product_id=1, sku="SKU-1", name="P1", billing_type="MRC", currency="USD",
            base_price=Decimal("100.00"), quantity=-5, pricing_method=PricingMethod.STANDARD
        )

def test_edge_case_discount_bounds():
    strategy = LineDiscountPricingStrategy()
    with pytest.raises(DomainValidationError, match="Discount must be between 0 and 100"):
        strategy.calculate(Decimal("100.00"), 1, discount_percent=Decimal("-1.00"))
    with pytest.raises(DomainValidationError, match="Discount must be between 0 and 100"):
        strategy.calculate(Decimal("100.00"), 1, discount_percent=Decimal("105.00"))

def test_edge_case_cost_and_markup_bounds():
    strategy = CostPlusMarkupPricingStrategy()
    with pytest.raises(DomainValidationError, match="Product cost cannot be negative"):
        strategy.calculate(Decimal("100.00"), 1, cost_price=Decimal("-10.00"), markup_percent=Decimal("20.00"))
    with pytest.raises(DomainValidationError, match="Markup percentage cannot be negative"):
        strategy.calculate(Decimal("100.00"), 1, cost_price=Decimal("100.00"), markup_percent=Decimal("-5.00"))

def test_edge_case_tier_overlaps_and_gaps():
    strategy = TieredPricingStrategy()
    overlapping_tiers = [
        MockTier(1, 10, Decimal("100.00")),
        MockTier(5, 20, Decimal("90.00"))
    ]
    with pytest.raises(DomainValidationError, match="Gaps or overlaps detected"):
        strategy.calculate(Decimal("100.00"), 8, tiers=overlapping_tiers, tiered_mode=TieredMode.VOLUME)

    no_match_tiers = [
        MockTier(1, 10, Decimal("100.00")),
        MockTier(20, 50, Decimal("90.00"))
    ]
    with pytest.raises(DomainValidationError, match="Gaps or overlaps detected"):
        strategy.calculate(Decimal("100.00"), 15, tiers=no_match_tiers, tiered_mode=TieredMode.VOLUME)

# ==============================================================================
# 5. ASYNC API, LIFECYCLE, RBAC, PERSISTENCE & OVERRIDE INTEGRATION TESTS
# ==============================================================================

async def get_token_for_user(db, email, password):
    auth_service = AuthService(db)
    login_req = LoginRequest(email=email, password=password)
    res = await auth_service.authenticate(login_req)
    await db.commit()
    return res.access_token

@pytest.mark.asyncio
async def test_pricing_lifecycle_and_effective_dates():
    suffix = uuid.uuid4().hex[:6]
    password = "Password123!"

    async with SessionLocal() as db:
        auth_service = AuthService(db)

        category = Category(name=f"CatLifecycle_{suffix}", description="Test Category")
        db.add(category)
        await db.commit()
        await db.refresh(category)

        product = Product(
            sku=f"LIFECYCLE-{suffix}",
            name="Lifecycle Product",
            description="Lifecycle Test",
            base_price=500.00,
            cost_price=300.00,
            currency="USD",
            is_active=True,
            billing_type="MRC",
            category_id=category.id
        )
        db.add(product)
        await db.commit()
        await db.refresh(product)

        # Admin user
        admin_email = f"admin_life_{suffix}@cpq.com"
        admin = await auth_service.register_user(UserCreate(
            email=admin_email, first_name="Admin", last_name="Life", username=f"adm_lf_{suffix}", password=password, confirm_password=password
        ))
        await db.commit()
        admin = await auth_service.user_repo.get_by_id(admin.id)
        admin.roles = []
        role_admin = (await db.execute(select(Role).where(Role.name == "Administrator"))).scalars().first()
        admin.roles.append(role_admin)
        await db.commit()

        token = await get_token_for_user(db, admin_email, password)
        headers = {"Authorization": f"Bearer {token}"}

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            
            # 1. Create a DRAFT configuration
            res_draft = await client.post(
                f"/api/v1/pricing/products/{product.id}/configuration",
                json={
                    "pricing_method": "LINE_DISCOUNT",
                    "discount_percent": 15.0,
                    "status": "DRAFT"
                },
                headers=headers
            )
            assert res_draft.status_code == status.HTTP_200_OK
            assert res_draft.json()["status"] == "DRAFT"

            # Calculating with draft config must reject
            res_calc_draft = await client.post(
                "/api/v1/pricing/calculate",
                json={"product_id": product.id, "quantity": 2},
                headers=headers
            )
            assert res_calc_draft.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
            assert "Pricing configuration is in draft status" in res_calc_draft.json()["detail"]

            # 2. Activate the configuration
            res_act = await client.post(
                f"/api/v1/pricing/products/{product.id}/configuration/activate",
                headers=headers
            )
            assert res_act.status_code == status.HTTP_200_OK
            assert res_act.json()["status"] == "ACTIVE"

            # Calculation now succeeds with 15% discount
            res_calc_act = await client.post(
                "/api/v1/pricing/calculate",
                json={"product_id": product.id, "quantity": 2},
                headers=headers
            )
            assert res_calc_act.status_code == status.HTTP_200_OK
            assert res_calc_act.json()["final_unit_price"] == "425.00"
            assert res_calc_act.json()["total_price"] == "850.00"

            # 3. Test expired effective date
            past_date = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
            res_exp = await client.post(
                f"/api/v1/pricing/products/{product.id}/configuration",
                json={
                    "pricing_method": "LINE_DISCOUNT",
                    "discount_percent": 15.0,
                    "status": "ACTIVE",
                    "effective_until": past_date
                },
                headers=headers
            )
            assert res_exp.status_code == status.HTTP_200_OK
            res_calc_exp = await client.post(
                "/api/v1/pricing/calculate",
                json={"product_id": product.id, "quantity": 2},
                headers=headers
            )
            assert res_calc_exp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
            assert "Pricing configuration has expired." in res_calc_exp.json()["detail"]

        # Cleanup
        await db.delete(product)
        await db.delete(category)
        await db.execute(delete(UserRole).where(UserRole.user_id == admin.id))
        await db.delete(admin)
        await db.commit()

        from backend.app.core.database import engine
        await engine.dispose()

@pytest.mark.asyncio
async def test_manual_price_override_and_audit():
    suffix = uuid.uuid4().hex[:6]
    password = "Password123!"

    async with SessionLocal() as db:
        auth_service = AuthService(db)

        category = Category(name=f"CatOverride_{suffix}", description="Test Category")
        db.add(category)
        await db.commit()
        await db.refresh(category)

        product = Product(
            sku=f"OVERRIDE-{suffix}",
            name="Override Product",
            description="Override Test",
            base_price=1000.00,
            cost_price=600.00,
            currency="USD",
            is_active=True,
            billing_type="NRC",
            category_id=category.id
        )
        db.add(product)
        await db.commit()
        await db.refresh(product)

        # Rep user (cannot override)
        rep_email = f"rep_ov_{suffix}@cpq.com"
        rep = await auth_service.register_user(UserCreate(
            email=rep_email, first_name="Rep", last_name="Ov", username=f"rep_ov_{suffix}", password=password, confirm_password=password
        ))
        # Admin user (can override)
        admin_email = f"adm_ov_{suffix}@cpq.com"
        admin = await auth_service.register_user(UserCreate(
            email=admin_email, first_name="Adm", last_name="Ov", username=f"adm_ov_{suffix}", password=password, confirm_password=password
        ))
        await db.commit()

        rep = await auth_service.user_repo.get_by_id(rep.id)
        admin = await auth_service.user_repo.get_by_id(admin.id)
        rep.roles = []
        admin.roles = []
        role_rep = (await db.execute(select(Role).where(Role.name == "Sales Representative"))).scalars().first()
        role_admin = (await db.execute(select(Role).where(Role.name == "Administrator"))).scalars().first()
        rep.roles.append(role_rep)
        admin.roles.append(role_admin)
        await db.commit()

        token_rep = await get_token_for_user(db, rep_email, password)
        token_admin = await get_token_for_user(db, admin_email, password)
        headers_rep = {"Authorization": f"Bearer {token_rep}"}
        headers_admin = {"Authorization": f"Bearer {token_admin}"}

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            
            # Rep attempts manual price override -> 403 Forbidden
            res_rep_override = await client.post(
                "/api/v1/pricing/calculate",
                json={
                    "product_id": product.id,
                    "quantity": 1,
                    "override_unit_price": 750.0,
                    "override_reason": "Executive VIP deal"
                },
                headers=headers_rep
            )
            assert res_rep_override.status_code == status.HTTP_403_FORBIDDEN

            # Admin performs price override -> 200 OK
            res_adm_override = await client.post(
                "/api/v1/pricing/calculate",
                json={
                    "product_id": product.id,
                    "quantity": 2,
                    "override_unit_price": 750.0,
                    "override_reason": "Executive VIP deal"
                },
                headers=headers_admin
            )
            assert res_adm_override.status_code == status.HTTP_200_OK
            data = res_adm_override.json()
            assert data["final_unit_price"] == "750.00"
            assert data["total_price"] == "1500.00"

            # Verify audit log was recorded for PRICING_OVERRIDE_USED
            audit_res = await db.execute(
                select(PricingAuditLog)
                .where(PricingAuditLog.product_id == product.id)
                .where(PricingAuditLog.action == "PRICING_OVERRIDE_USED")
            )
            log = audit_res.scalars().first()
            assert log is not None
            assert log.after_value["final_unit_price"] == "750.00"
            assert log.after_value["reason"] == "Executive VIP deal"

        # Cleanup
        await db.delete(product)
        await db.delete(category)
        await db.execute(delete(UserRole).where(UserRole.user_id.in_([rep.id, admin.id])))
        await db.delete(rep)
        await db.delete(admin)
        await db.commit()

        from backend.app.core.database import engine
        await engine.dispose()

@pytest.mark.asyncio
async def test_pricing_rules_crud_and_evaluation():
    suffix = uuid.uuid4().hex[:6]
    password = "Password123!"

    async with SessionLocal() as db:
        auth_service = AuthService(db)

        # Admin user
        admin_email = f"adm_rule_{suffix}@cpq.com"
        admin = await auth_service.register_user(UserCreate(
            email=admin_email, first_name="Adm", last_name="Rule", username=f"adm_rl_{suffix}", password=password, confirm_password=password
        ))
        await db.commit()
        admin = await auth_service.user_repo.get_by_id(admin.id)
        admin.roles = []
        role_admin = (await db.execute(select(Role).where(Role.name == "Administrator"))).scalars().first()
        admin.roles.append(role_admin)
        await db.commit()

        token = await get_token_for_user(db, admin_email, password)
        headers = {"Authorization": f"Bearer {token}"}

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            
            # Create a pricing rule
            res_create = await client.post(
                "/api/v1/pricing/rules",
                json={
                    "name": f"Enterprise Global Rule {suffix}",
                    "rule_type": "volume_discount",
                    "conditions": {"min_total": 5000},
                    "actions": {"discount_percent": 5}
                },
                headers=headers
            )
            assert res_create.status_code == status.HTTP_201_CREATED
            rule_id = res_create.json()["id"]

            # List rules
            res_list = await client.get("/api/v1/pricing/rules", headers=headers)
            assert res_list.status_code == status.HTTP_200_OK
            assert any(r["id"] == rule_id for r in res_list.json())

            # Delete rule
            res_del = await client.delete(f"/api/v1/pricing/rules/{rule_id}", headers=headers)
            assert res_del.status_code == status.HTTP_204_NO_CONTENT

        # Cleanup
        await db.execute(delete(UserRole).where(UserRole.user_id == admin.id))
        await db.delete(admin)
        await db.commit()

        from backend.app.core.database import engine
        await engine.dispose()
