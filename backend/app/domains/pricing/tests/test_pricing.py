import pytest
import asyncio
import uuid
import httpx
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
from backend.app.domains.pricing.api.schemas import CalculatePriceRequest

# Mocking class for validate_tiers
class DummyTier:
    def __init__(self, min_qty, max_qty, price):
        self.min_quantity = min_qty
        self.max_quantity = max_qty
        self.price = price

# ----------------------------------------------------
# 1. Pure Unit / Domain Level Calculations Tests
# ----------------------------------------------------

def test_standard_pricing_strategy():
    strategy = StandardPricingStrategy()
    res = strategy.calculate(base_price=Decimal("100.00"), quantity=5)
    assert res["base_unit_price"] == Decimal("100.00")
    assert res["discount_percent"] == Decimal("0.00")
    assert res["discount_amount"] == Decimal("0.00")
    assert res["final_unit_price"] == Decimal("100.00")
    assert res["total_price"] == Decimal("500.00")

def test_line_discount_pricing_strategy():
    strategy = LineDiscountPricingStrategy()
    res1 = strategy.calculate(
        base_price=Decimal("100.00"),
        quantity=5,
        discount_percent=Decimal("10.00")
    )
    assert res1["base_unit_price"] == Decimal("100.00")
    assert res1["discount_percent"] == Decimal("10.00")
    assert res1["discount_amount"] == Decimal("10.00")
    assert res1["final_unit_price"] == Decimal("90.00")
    assert res1["total_price"] == Decimal("450.00")

def test_cost_plus_markup_strategy():
    strategy = CostPlusMarkupPricingStrategy()
    
    # Cost = 100, Markup = 30%, Qty = 5 -> Unit = 130, Total = 650
    res = strategy.calculate(
        base_price=Decimal("100.00"),
        quantity=5,
        cost_price=Decimal("100.00"),
        markup_percent=Decimal("30.00")
    )
    assert res["final_unit_price"] == Decimal("130.00")
    assert res["total_price"] == Decimal("650.00")

    # Invalid validations
    with pytest.raises(DomainValidationError):
        strategy.calculate(Decimal("100"), 5, cost_price=None, markup_percent=Decimal("30"))
    with pytest.raises(DomainValidationError):
        strategy.calculate(Decimal("100"), 5, cost_price=Decimal("-10"), markup_percent=Decimal("30"))
    with pytest.raises(DomainValidationError):
        strategy.calculate(Decimal("100"), 5, cost_price=Decimal("100"), markup_percent=Decimal("-5"))

def test_strategy_factory_rejections():
    with pytest.raises(DomainValidationError):
        LineDiscountPricingStrategy().calculate(Decimal("100"), 5, Decimal("-5"))

def test_engine_quantity_validation():
    with pytest.raises(DomainValidationError):
        PricingEngine.calculate(
            product_id=1,
            sku="SKU-1",
            name="Product 1",
            billing_type="MRC",
            currency="USD",
            base_price=Decimal("100"),
            quantity=0,
            pricing_method=PricingMethod.STANDARD
        )

# ----------------------------------------------------
# Phase 2: Domain Math Tests for Tiered & Block
# ----------------------------------------------------

def test_tiered_volume_calculation():
    strategy = TieredPricingStrategy()
    tiers = [
        DummyTier(1, 10, Decimal("100.00")),
        DummyTier(11, 50, Decimal("90.00")),
        DummyTier(51, None, Decimal("80.00"))
    ]
    res = strategy.calculate(
        base_price=Decimal("100.00"),
        quantity=20,
        tiers=tiers,
        tiered_mode=TieredMode.VOLUME
    )
    assert res["final_unit_price"] == Decimal("90.00")
    assert res["total_price"] == Decimal("1800.00")

def test_tiered_cumulative_calculation():
    strategy = TieredPricingStrategy()
    tiers = [
        DummyTier(1, 10, Decimal("100.00")),
        DummyTier(11, 50, Decimal("90.00")),
        DummyTier(51, None, Decimal("80.00"))
    ]
    res = strategy.calculate(
        base_price=Decimal("100.00"),
        quantity=20,
        tiers=tiers,
        tiered_mode=TieredMode.CUMULATIVE
    )
    assert res["total_price"] == Decimal("1900.00")
    assert res["final_unit_price"] == Decimal("95.00")

def test_block_pricing_calculation():
    strategy = BlockPricingStrategy()
    tiers = [
        DummyTier(1, 10, Decimal("500.00")),
        DummyTier(11, 50, Decimal("1500.00")),
        DummyTier(51, 100, Decimal("2500.00"))
    ]
    res = strategy.calculate(
        base_price=Decimal("100.00"),
        quantity=7,
        tiers=tiers
    )
    assert res["total_price"] == Decimal("500.00")

def test_invalid_overlapping_tiers():
    strategy = TieredPricingStrategy()
    tiers_overlap = [
        DummyTier(1, 10, Decimal("100.00")),
        DummyTier(5, 20, Decimal("90.00"))
    ]
    with pytest.raises(DomainValidationError):
        strategy.calculate(
            base_price=Decimal("100"),
            quantity=15,
            tiers=tiers_overlap,
            tiered_mode=TieredMode.VOLUME
        )

# ----------------------------------------------------
# 2. Async API Integration & Authorization Tests
# ----------------------------------------------------

async def get_token_for_user(db, email, password):
    auth_service = AuthService(db)
    login_req = LoginRequest(email=email, password=password)
    res = await auth_service.authenticate(login_req)
    await db.commit()
    return res.access_token

@pytest.mark.asyncio
async def test_pricing_api_endpoints():
    suffix = uuid.uuid4().hex[:6]
    password = "Password123!"
    
    async with SessionLocal() as db:
        auth_service = AuthService(db)
        
        category = Category(name=f"PricingHardware_{suffix}", description="Category for pricing tests")
        db.add(category)
        await db.commit()
        await db.refresh(category)

        product = Product(
            sku=f"PRC-LAP-{suffix}",
            name="Pricing Dell Latitude",
            description="Laptop for testing",
            base_price=100.00,
            cost_price=100.00,
            currency="USD",
            is_active=True,
            billing_type="MRC",
            category_id=category.id
        )
        db.add(product)
        await db.commit()
        await db.refresh(product)

        rep_email = f"rep_pricing_{suffix}@cpq.com"
        user_rep = await auth_service.register_user(UserCreate(
            email=rep_email, first_name="Rep", last_name="Pricing", username=f"rep_prc_{suffix}", password=password, confirm_password=password
        ))
        admin_email = f"admin_pricing_{suffix}@cpq.com"
        user_admin = await auth_service.register_user(UserCreate(
            email=admin_email, first_name="Admin", last_name="Pricing", username=f"admin_prc_{suffix}", password=password, confirm_password=password
        ))
        await db.commit()

        user_rep = await auth_service.user_repo.get_by_id(user_rep.id)
        user_admin = await auth_service.user_repo.get_by_id(user_admin.id)
        user_rep.roles = []
        user_admin.roles = []
        role_rep = (await db.execute(select(Role).where(Role.name == "Sales Representative"))).scalars().first()
        role_admin = (await db.execute(select(Role).where(Role.name == "Administrator"))).scalars().first()
        user_rep.roles.append(role_rep)
        user_admin.roles.append(role_admin)
        await db.commit()
        
        token_rep = await get_token_for_user(db, rep_email, password)
        headers_rep = {"Authorization": f"Bearer {token_rep}"}
        token_admin = await get_token_for_user(db, admin_email, password)
        headers_admin = {"Authorization": f"Bearer {token_admin}"}

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            
            # Rep cannot configure pricing configuration
            res_rep_config = await client.post(
                f"/api/v1/pricing/products/{product.id}/configuration",
                json={"pricing_method": "COST_PLUS_MARKUP", "markup_percent": 30.0},
                headers=headers_rep
            )
            assert res_rep_config.status_code == status.HTTP_403_FORBIDDEN

            # Admin configures successfully
            res_admin_config = await client.post(
                f"/api/v1/pricing/products/{product.id}/configuration",
                json={"pricing_method": "COST_PLUS_MARKUP", "markup_percent": 30.0},
                headers=headers_admin
            )
            assert res_admin_config.status_code == status.HTTP_200_OK
            assert res_admin_config.json()["pricing_method"] == "COST_PLUS_MARKUP"

            # Rep calculates pricing with Cost Plus Markup (Cost = 100.00, Markup = 30.00% -> Unit = 130.00 -> Total = 650.00 for qty 5)
            res_calc_markup = await client.post(
                "/api/v1/pricing/calculate",
                json={
                    "product_id": product.id,
                    "quantity": 5,
                    "pricing_method": "COST_PLUS_MARKUP"
                },
                headers=headers_rep
            )
            assert res_calc_markup.status_code == status.HTTP_200_OK
            data_markup = res_calc_markup.json()
            assert data_markup["final_unit_price"] == "130.00"
            assert data_markup["total_price"] == "650.00"

            # Check enriched list endpoint
            res_enriched = await client.get("/api/v1/pricing/products", headers=headers_rep)
            assert res_enriched.status_code == status.HTTP_200_OK
            enriched_products = {p["sku"]: p for p in res_enriched.json()}
            assert enriched_products[product.sku]["pricing_method"] == "COST_PLUS_MARKUP"
            assert enriched_products[product.sku]["markup_percent"] == "30.00"

        # Cleanup
        await db.delete(product)
        await db.delete(category)
        await db.execute(delete(UserRole).where(UserRole.user_id.in_([user_rep.id, user_admin.id])))
        await db.delete(user_rep)
        await db.delete(user_admin)
        await db.commit()
        
        from backend.app.core.database import engine
        await engine.dispose()
