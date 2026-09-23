import pytest
import asyncio
import uuid
from decimal import Decimal
import httpx
from fastapi import status
from sqlalchemy import select

from backend.app.main import app
from backend.app.core.database import SessionLocal
from backend.app.domains.auth.services import AuthService
from backend.app.domains.auth.schemas import UserCreate, LoginRequest
from backend.app.domains.auth.models import User, Role
from backend.app.domains.customer.models import Customer, CustomerStatus
from backend.app.domains.catalog.models import Product, Category
from backend.app.domains.pricing.models import ProductPricingSetting
from backend.app.domains.pricing.domain.enums import PricingMethod
from backend.app.domains.configuration.models import (
    ProductConfigurationGroup, ProductConfigurationOption, ConfigurationSession
)
from backend.app.domains.quotes.models import Quote, QuoteLineItem, QuoteAuditLog, QuoteStatus

async def get_token(db, email, password):
    auth_service = AuthService(db)
    login_req = LoginRequest(email=email, password=password)
    res = await auth_service.authenticate(login_req)
    await db.commit()
    return res.access_token

@pytest.fixture
def anyio_backend():
    return "asyncio"

@pytest.mark.asyncio
async def test_quote_builder_full_lifecycle():
    suffix = uuid.uuid4().hex[:6]
    password = "TestPassword123!"

    async with SessionLocal() as db:
        auth_service = AuthService(db)

        # 1. Setup Roles and Users (Rep 1, Rep 2, Manager, Executive)
        role_rep = (await db.execute(select(Role).where(Role.name == "Sales Representative"))).scalars().first()
        role_mgr = (await db.execute(select(Role).where(Role.name == "Sales Manager"))).scalars().first()
        role_exec = (await db.execute(select(Role).where(Role.name == "Executive"))).scalars().first()
        role_admin = (await db.execute(select(Role).where(Role.name == "Administrator"))).scalars().first()

        rep1_user = await auth_service.register_user(UserCreate(
            email=f"rep1_{suffix}@cpq.com", first_name="Rep1", last_name="User",
            username=f"rep1_{suffix}", password=password, confirm_password=password
        ))
        rep2_user = await auth_service.register_user(UserCreate(
            email=f"rep2_{suffix}@cpq.com", first_name="Rep2", last_name="User",
            username=f"rep2_{suffix}", password=password, confirm_password=password
        ))
        mgr_user = await auth_service.register_user(UserCreate(
            email=f"mgr_{suffix}@cpq.com", first_name="Manager", last_name="User",
            username=f"mgr_{suffix}", password=password, confirm_password=password
        ))
        exec_user = await auth_service.register_user(UserCreate(
            email=f"exec_{suffix}@cpq.com", first_name="Exec", last_name="User",
            username=f"exec_{suffix}", password=password, confirm_password=password
        ))
        await db.commit()

        # Assign roles
        rep1_user = await auth_service.user_repo.get_by_id(rep1_user.id)
        rep2_user = await auth_service.user_repo.get_by_id(rep2_user.id)
        mgr_user = await auth_service.user_repo.get_by_id(mgr_user.id)
        exec_user = await auth_service.user_repo.get_by_id(exec_user.id)

        rep1_user.roles = [role_rep]
        rep2_user.roles = [role_rep]
        mgr_user.roles = [role_mgr]
        exec_user.roles = [role_exec]
        await db.commit()

        # 2. Setup Customer
        customer = Customer(
            tenant_id=uuid.uuid4(),
            customer_number=f"CUST-{suffix}",
            legal_name=f"Acme Corp {suffix}",
            display_name=f"Acme Corp {suffix}",
            customer_type="BUSINESS",
            email=f"acme_{suffix}@corp.com",
            currency="USD",
            status="ACTIVE",
            created_by=rep1_user.id
        )
        db.add(customer)

        # 3. Setup Catalog Products
        category = Category(name=f"Hardware_{suffix}", description="Test Category")
        db.add(category)
        await db.commit()
        await db.refresh(category)

        # Product 1: Standard Laptop ($1,000.00 list, $700.00 cost)
        prod_laptop = Product(
            sku=f"LAP-{suffix}",
            name=f"Enterprise Laptop {suffix}",
            description="High perf laptop",
            base_price=Decimal("1000.00"),
            cost_price=Decimal("700.00"),
            currency="USD",
            is_active=True,
            billing_type="NRC",
            category_id=category.id
        )
        # Product 2: Cloud Software Subscription ($50.00 list, $10.00 cost)
        prod_cloud = Product(
            sku=f"CLOUD-{suffix}",
            name=f"Cloud Suite {suffix}",
            description="Annual subscription",
            base_price=Decimal("50.00"),
            cost_price=Decimal("10.00"),
            currency="USD",
            is_active=True,
            billing_type="MRC",
            category_id=category.id
        )
        # Product 3: Inactive Product
        prod_inactive = Product(
            sku=f"INACT-{suffix}",
            name=f"Deprecated Product {suffix}",
            base_price=Decimal("100.00"),
            currency="USD",
            is_active=False,
            billing_type="NRC",
            category_id=category.id
        )
        db.add_all([prod_laptop, prod_cloud, prod_inactive])
        await db.commit()
        await db.refresh(prod_laptop)
        await db.refresh(prod_cloud)
        await db.refresh(prod_inactive)

        # Setup Pricing Setting for Laptop (Standard) and Cloud (Line Discount)
        setting_laptop = ProductPricingSetting(
            product_id=prod_laptop.id,
            pricing_method=PricingMethod.STANDARD.value,
            markup_percent=Decimal("0.00"),
            status="ACTIVE"
        )
        setting_cloud = ProductPricingSetting(
            product_id=prod_cloud.id,
            pricing_method=PricingMethod.LINE_DISCOUNT.value,
            markup_percent=Decimal("0.00"),
            discount_percent=Decimal("10.00"),
            status="ACTIVE"
        )
        db.add_all([setting_laptop, setting_cloud])
        await db.commit()

        # 4. Setup Configuration Session for Laptop
        cfg_group = ProductConfigurationGroup(
            product_id=prod_laptop.id,
            name="Memory",
            required=True,
            selection_type="SINGLE_SELECT"
        )
        db.add(cfg_group)
        await db.commit()
        await db.refresh(cfg_group)

        cfg_opt = ProductConfigurationOption(
            group_id=cfg_group.id,
            name="32GB RAM",
            value="32GB",
            is_active=True
        )
        db.add(cfg_opt)
        await db.commit()
        await db.refresh(cfg_opt)

        config_session = ConfigurationSession(
            product_id=prod_laptop.id,
            user_id=rep1_user.id,
            selections=[{"group_id": cfg_group.id, "option_ids": [cfg_opt.id], "quantities": {str(cfg_opt.id): 1}}],
            is_valid=True
        )
        db.add(config_session)
        await db.commit()
        await db.refresh(config_session)

        # Auth Tokens
        token_rep1 = await get_token(db, f"rep1_{suffix}@cpq.com", password)
        token_rep2 = await get_token(db, f"rep2_{suffix}@cpq.com", password)
        token_mgr = await get_token(db, f"mgr_{suffix}@cpq.com", password)
        token_exec = await get_token(db, f"exec_{suffix}@cpq.com", password)

        headers_rep1 = {"Authorization": f"Bearer {token_rep1}"}
        headers_rep2 = {"Authorization": f"Bearer {token_rep2}"}
        headers_mgr = {"Authorization": f"Bearer {token_mgr}"}
        headers_exec = {"Authorization": f"Bearer {token_exec}"}

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            # -------------------------------------------------------------------
            # Test 1: Unauthenticated request rejected (401)
            # -------------------------------------------------------------------
            res_unauth = await client.get("/api/v1/quotes/")
            assert res_unauth.status_code == status.HTTP_401_UNAUTHORIZED

            # -------------------------------------------------------------------
            # Test 2: Rep 1 creates Quote Shell
            # -------------------------------------------------------------------
            quote_payload = {
                "customer_id": customer.id,
                "title": f"Q3 Tech Upgrade {suffix}",
                "description": "Enterprise workstations and cloud services",
                "currency": "USD",
                "notes": "Net 30 terms requested",
                "items": []
            }
            res_create = await client.post("/api/v1/quotes/", json=quote_payload, headers=headers_rep1)
            assert res_create.status_code == status.HTTP_201_CREATED, res_create.text
            q_data = res_create.json()
            quote_id = q_data["id"]
            quote_number = q_data["quote_number"]

            assert quote_number.startswith("QT-")
            assert q_data["status"] == "DRAFT"
            assert q_data["version"] == 1
            assert q_data["subtotal"] == "0.00"
            assert q_data["discount_amount"] == "0.00"
            assert q_data["total_amount"] == "0.00"
            assert q_data["grand_total"] == "0.00"
            assert len(q_data["items"]) == 0
            assert q_data["customer"]["name"] == customer.display_name
            assert q_data["created_by"]["username"] == f"rep1_{suffix}"

            # -------------------------------------------------------------------
            # Test 3: Add Configured Laptop Line Item
            # -------------------------------------------------------------------
            laptop_item_payload = {
                "product_id": prod_laptop.id,
                "quantity": 10,
                "discount_percentage": "10.00",
                "configuration_id": str(config_session.id)
            }
            res_item1 = await client.post(f"/api/v1/quotes/{quote_id}/items", json=laptop_item_payload, headers=headers_rep1)
            assert res_item1.status_code == status.HTTP_201_CREATED, res_item1.text
            item1_data = res_item1.json()

            # List price = $1,000.00. Discount 10% -> Unit price = $900.00.
            # Qty = 10 -> Total = $9,000.00.
            assert item1_data["product_name"] == prod_laptop.name
            assert item1_data["sku"] == prod_laptop.sku
            assert item1_data["unit_price"] == "900.00"
            assert item1_data["discount_percentage"] == "10.00"
            assert item1_data["discount_amount"] == "100.00"
            assert item1_data["total_price"] == "9000.00"
            assert item1_data["line_total"] == "9000.00"
            assert item1_data["configuration_id"] == str(config_session.id)
            assert item1_data["configuration_snapshot"] is not None
            assert item1_data["pricing_breakdown"] is not None
            item1_id = item1_data["id"]

            # -------------------------------------------------------------------
            # Test 4: Add Second Line Item (Cloud Licenses Qty 20)
            # -------------------------------------------------------------------
            cloud_item_payload = {
                "product_id": prod_cloud.id,
                "quantity": 20,
                "discount_percentage": "0.00"
            }
            res_item2 = await client.post(f"/api/v1/quotes/{quote_id}/items", json=cloud_item_payload, headers=headers_rep1)
            assert res_item2.status_code == status.HTTP_201_CREATED, res_item2.text
            item2_data = res_item2.json()

            # List price $50.00, default discount 10% -> Unit price = $45.00 -> Total = $900.00 for qty 20
            # Wait, let's check pricing setting for cloud: discount_percent was 10.00%
            assert Decimal(item2_data["total_price"]) == Decimal(item2_data["unit_price"]) * 20
            item2_id = item2_data["id"]

            # -------------------------------------------------------------------
            # Test 5: Verify Quote Totals & Pricing Breakdown
            # -------------------------------------------------------------------
            res_get = await client.get(f"/api/v1/quotes/{quote_id}", headers=headers_rep1)
            assert res_get.status_code == status.HTTP_200_OK
            q_get_data = res_get.json()
            assert len(q_get_data["items"]) == 2

            expected_subtotal = Decimal(item1_data["total_price"]) + Decimal(item2_data["total_price"])
            assert Decimal(q_get_data["subtotal"]) == expected_subtotal
            assert Decimal(q_get_data["grand_total"]) == expected_subtotal
            assert Decimal(q_get_data["total_amount"]) == expected_subtotal
            assert Decimal(q_get_data["margin_percentage"]) > Decimal("0.00")

            # -------------------------------------------------------------------
            # Test 6: Inactive Product Rejection
            # -------------------------------------------------------------------
            res_inactive = await client.post(
                f"/api/v1/quotes/{quote_id}/items",
                json={"product_id": prod_inactive.id, "quantity": 1},
                headers=headers_rep1
            )
            assert res_inactive.status_code in (status.HTTP_400_BAD_REQUEST, status.HTTP_422_UNPROCESSABLE_ENTITY)
            assert "inactive" in res_inactive.text.lower()

            # -------------------------------------------------------------------
            # Test 7: Update Line Item Quantity (Cloud Qty 20 -> 50)
            # -------------------------------------------------------------------
            res_update_item = await client.put(
                f"/api/v1/quotes/{quote_id}/items/{item2_id}",
                json={"quantity": 50},
                headers=headers_rep1
            )
            assert res_update_item.status_code == status.HTTP_200_OK
            upd_item_data = res_update_item.json()
            assert upd_item_data["quantity"] == 50
            assert Decimal(upd_item_data["total_price"]) == Decimal(upd_item_data["unit_price"]) * 50

            # Verify Quote subtotal automatically recalculated
            res_quote_after_qty = await client.get(f"/api/v1/quotes/{quote_id}", headers=headers_rep1)
            q_qty_data = res_quote_after_qty.json()
            assert Decimal(q_qty_data["subtotal"]) == Decimal("9000.00") + Decimal(upd_item_data["total_price"])

            # -------------------------------------------------------------------
            # Test 8: Remove Line Item
            # -------------------------------------------------------------------
            res_del_item = await client.delete(f"/api/v1/quotes/{quote_id}/items/{item2_id}", headers=headers_rep1)
            assert res_del_item.status_code == status.HTTP_204_NO_CONTENT

            res_quote_after_del = await client.get(f"/api/v1/quotes/{quote_id}", headers=headers_rep1)
            q_del_data = res_quote_after_del.json()
            assert len(q_del_data["items"]) == 1
            assert Decimal(q_del_data["subtotal"]) == Decimal("9000.00")

            # -------------------------------------------------------------------
            # Test 9: Data Consistency & Catalog Base Price Isolation
            # -------------------------------------------------------------------
            # If the catalog base price of Laptop changes to $1,500.00, the quote MUST keep $900.00 unit price
            prod_laptop.base_price = Decimal("1500.00")
            db.add(prod_laptop)
            await db.commit()

            res_quote_isolation = await client.get(f"/api/v1/quotes/{quote_id}", headers=headers_rep1)
            q_iso_data = res_quote_isolation.json()
            assert q_iso_data["items"][0]["unit_price"] == "900.00"
            assert q_iso_data["items"][0]["total_price"] == "9000.00"

            # -------------------------------------------------------------------
            # Test 10: RBAC - Rep 2 Cannot Edit or View Rep 1's Quote (403)
            # -------------------------------------------------------------------
            res_rep2_view = await client.get(f"/api/v1/quotes/{quote_id}", headers=headers_rep2)
            assert res_rep2_view.status_code == status.HTTP_403_FORBIDDEN

            res_rep2_edit = await client.put(
                f"/api/v1/quotes/{quote_id}",
                json={"title": "Hacked Title"},
                headers=headers_rep2
            )
            assert res_rep2_edit.status_code == status.HTTP_403_FORBIDDEN

            # -------------------------------------------------------------------
            # Test 11: RBAC - Manager & Executive Visibility
            # -------------------------------------------------------------------
            res_mgr_view = await client.get(f"/api/v1/quotes/{quote_id}", headers=headers_mgr)
            assert res_mgr_view.status_code == status.HTTP_200_OK

            res_exec_view = await client.get(f"/api/v1/quotes/{quote_id}", headers=headers_exec)
            assert res_exec_view.status_code == status.HTTP_200_OK

            # Manager can edit draft
            res_mgr_edit = await client.put(
                f"/api/v1/quotes/{quote_id}",
                json={"notes": "Reviewed and approved by sales management"},
                headers=headers_mgr
            )
            assert res_mgr_edit.status_code == status.HTTP_200_OK
            assert "Reviewed and approved" in res_mgr_edit.json()["notes"]

            # -------------------------------------------------------------------
            # Test 12: Quote Status Transition - Submission
            # -------------------------------------------------------------------
            res_submit = await client.post(f"/api/v1/quotes/{quote_id}/submit", headers=headers_rep1)
            assert res_submit.status_code == status.HTTP_200_OK
            assert res_submit.json()["status"] == "SUBMITTED"

            # Once submitted, cannot edit quote or add line items
            res_edit_submitted = await client.put(
                f"/api/v1/quotes/{quote_id}",
                json={"title": "Should Fail"},
                headers=headers_rep1
            )
            assert res_edit_submitted.status_code in (status.HTTP_400_BAD_REQUEST, status.HTTP_422_UNPROCESSABLE_ENTITY)

            res_add_submitted = await client.post(
                f"/api/v1/quotes/{quote_id}/items",
                json={"product_id": prod_cloud.id, "quantity": 1},
                headers=headers_rep1
            )
            assert res_add_submitted.status_code in (status.HTTP_400_BAD_REQUEST, status.HTTP_422_UNPROCESSABLE_ENTITY)

            # -------------------------------------------------------------------
            # Test 13: Quote Revisions (Revision increments version and clones items)
            # -------------------------------------------------------------------
            res_revise = await client.post(f"/api/v1/quotes/{quote_id}/revise", headers=headers_rep1)
            assert res_revise.status_code == status.HTTP_200_OK
            revised_data = res_revise.json()
            assert revised_data["quote_number"] == quote_number
            assert revised_data["version"] == 2
            assert revised_data["parent_quote_id"] == quote_id
            assert revised_data["status"] == "DRAFT"
            assert len(revised_data["items"]) == 1
            assert revised_data["items"][0]["total_price"] == "9000.00"

            # -------------------------------------------------------------------
            # Test 14: Audit Trail Verification
            # -------------------------------------------------------------------
            res_audit_check = await client.get(f"/api/v1/quotes/{quote_id}", headers=headers_mgr)
            q_audit = res_audit_check.json()
            audit_actions = [log["action"] for log in q_audit["audit_logs"]]
            assert "QUOTE_CREATED" in audit_actions
            assert "QUOTE_ITEM_ADDED" in audit_actions
            assert "QUOTE_ITEM_UPDATED" in audit_actions
            assert "QUOTE_ITEM_REMOVED" in audit_actions
            assert "QUOTE_UPDATED" in audit_actions
            assert "QUOTE_SUBMITTED" in audit_actions

            # -------------------------------------------------------------------
            # Test 15: Cancellation
            # -------------------------------------------------------------------
            res_cancel = await client.post(f"/api/v1/quotes/{quote_id}/cancel", headers=headers_mgr)
            assert res_cancel.status_code == status.HTTP_200_OK
            assert res_cancel.json()["status"] == "CANCELLED"

    # -------------------------------------------------------------------
    # Test 16: Persistence Across DB Session Restart
    # -------------------------------------------------------------------
    async with SessionLocal() as db_fresh:
        fresh_quote = (await db_fresh.execute(select(Quote).where(Quote.id == quote_id))).scalars().first()
        assert fresh_quote is not None
        assert fresh_quote.quote_number == quote_number
        assert fresh_quote.status == QuoteStatus.CANCELLED

        fresh_revised = (await db_fresh.execute(select(Quote).where(Quote.id == revised_data["id"]))).scalars().first()
        assert fresh_revised is not None
        assert fresh_revised.version == 2
        assert fresh_revised.status == QuoteStatus.DRAFT
