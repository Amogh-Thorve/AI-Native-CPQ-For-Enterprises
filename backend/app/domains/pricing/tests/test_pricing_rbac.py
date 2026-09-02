import pytest
import httpx
import uuid
from decimal import Decimal
from fastapi import status
from sqlalchemy import select, delete

from backend.app.main import app
from backend.app.core.database import SessionLocal
from backend.app.domains.auth.services import AuthService
from backend.app.domains.auth.schemas import UserCreate, LoginRequest
from backend.app.domains.auth.models import User, Role, UserRole
from backend.app.domains.catalog.models import Product, Category
from backend.app.domains.pricing.models import PricingAuditLog, PricingRule

async def get_token_for_user(db, email, password):
    auth_service = AuthService(db)
    login_req = LoginRequest(email=email, password=password)
    res = await auth_service.authenticate(login_req)
    await db.commit()
    return res.access_token

@pytest.mark.asyncio
async def test_pricing_rbac_permissions():
    suffix = uuid.uuid4().hex[:6]
    password = "Password123!"
    
    async with SessionLocal() as db:
        auth_service = AuthService(db)
        
        category = Category(name=f"RbacHardware_{suffix}", description="Category for RBAC pricing tests")
        db.add(category)
        await db.commit()
        await db.refresh(category)

        product = Product(
            sku=f"RBC-LAP-{suffix}",
            name="RBAC Dell Latitude",
            description="Laptop for testing RBAC",
            base_price=1000.00,
            cost_price=700.00,
            currency="USD",
            is_active=True,
            billing_type="MRC",
            category_id=category.id
        )
        db.add(product)
        await db.commit()
        await db.refresh(product)

        # Create Representative, Manager, and Executive
        rep_email = f"rep_rbac_{suffix}@cpq.com"
        user_rep = await auth_service.register_user(UserCreate(
            email=rep_email, first_name="Rep", last_name="Rbac", username=f"rep_rb_{suffix}", password=password, confirm_password=password
        ))
        
        mgr_email = f"mgr_rbac_{suffix}@cpq.com"
        user_mgr = await auth_service.register_user(UserCreate(
            email=mgr_email, first_name="Mgr", last_name="Rbac", username=f"mgr_rb_{suffix}", password=password, confirm_password=password
        ))

        exec_email = f"exec_rbac_{suffix}@cpq.com"
        user_exec = await auth_service.register_user(UserCreate(
            email=exec_email, first_name="Exec", last_name="Rbac", username=f"exec_rb_{suffix}", password=password, confirm_password=password
        ))
        await db.commit()

        user_rep = await auth_service.user_repo.get_by_id(user_rep.id)
        user_mgr = await auth_service.user_repo.get_by_id(user_mgr.id)
        user_exec = await auth_service.user_repo.get_by_id(user_exec.id)

        user_rep.roles = []
        user_mgr.roles = []
        user_exec.roles = []

        role_rep = (await db.execute(select(Role).where(Role.name == "Sales Representative"))).scalars().first()
        role_mgr = (await db.execute(select(Role).where(Role.name == "Sales Manager"))).scalars().first()
        role_exec = (await db.execute(select(Role).where(Role.name == "Executive"))).scalars().first()

        user_rep.roles.append(role_rep)
        user_mgr.roles.append(role_mgr)
        user_exec.roles.append(role_exec)
        await db.commit()

        token_rep = await get_token_for_user(db, rep_email, password)
        headers_rep = {"Authorization": f"Bearer {token_rep}"}

        token_mgr = await get_token_for_user(db, mgr_email, password)
        headers_mgr = {"Authorization": f"Bearer {token_mgr}"}

        token_exec = await get_token_for_user(db, exec_email, password)
        headers_exec = {"Authorization": f"Bearer {token_exec}"}

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            
            # --- 1. Sales Representative Access Validation ---
            
            # Rep can calculate price
            res = await client.post(
                "/api/v1/pricing/calculate",
                json={"product_id": product.id, "quantity": 2, "pricing_method": "STANDARD"},
                headers=headers_rep
            )
            assert res.status_code == status.HTTP_200_OK
            assert res.json()["total_price"] == "2000.00"

            # Rep lists products, but cost_price must be filtered out (None)
            res = await client.get("/api/v1/pricing/products", headers=headers_rep)
            assert res.status_code == status.HTTP_200_OK
            prods = {p["sku"]: p for p in res.json()}
            assert prods[product.sku]["cost_price"] is None

            # Rep cannot view pricing configuration
            res = await client.get(f"/api/v1/pricing/products/{product.id}/configuration", headers=headers_rep)
            assert res.status_code == status.HTTP_403_FORBIDDEN

            # Rep cannot configure pricing configuration
            res = await client.post(
                f"/api/v1/pricing/products/{product.id}/configuration",
                json={"pricing_method": "STANDARD", "markup_percent": 0.0},
                headers=headers_rep
            )
            assert res.status_code == status.HTTP_403_FORBIDDEN

            # --- 2. Sales Manager Access Validation ---

            # Manager lists products, but cost_price must be filtered out (None)
            res = await client.get("/api/v1/pricing/products", headers=headers_mgr)
            assert res.status_code == status.HTTP_200_OK
            prods_mgr = {p["sku"]: p for p in res.json()}
            assert prods_mgr[product.sku]["cost_price"] is None

            # Manager can view pricing configuration
            res = await client.get(f"/api/v1/pricing/products/{product.id}/configuration", headers=headers_mgr)
            assert res.status_code == status.HTTP_200_OK
            assert res.json()["pricing_method"] == "STANDARD"

            # Manager cannot edit/save pricing configuration
            res = await client.post(
                f"/api/v1/pricing/products/{product.id}/configuration",
                json={"pricing_method": "STANDARD", "markup_percent": 0.0},
                headers=headers_mgr
            )
            assert res.status_code == status.HTTP_403_FORBIDDEN

            # --- 3. Executive Access Validation ---

            # Executive lists products, and cost_price must be returned
            res = await client.get("/api/v1/pricing/products", headers=headers_exec)
            assert res.status_code == status.HTTP_200_OK
            prods_exec = {p["sku"]: p for p in res.json()}
            assert prods_exec[product.sku]["cost_price"] == "700.00"

            # Executive configures Cost+Markup successfully
            res = await client.post(
                f"/api/v1/pricing/products/{product.id}/configuration",
                json={"pricing_method": "COST_PLUS_MARKUP", "markup_percent": 20.0},
                headers=headers_exec
            )
            assert res.status_code == status.HTTP_200_OK
            assert res.json()["pricing_method"] == "COST_PLUS_MARKUP"

            # Verify audit log was created
            logs_res = await db.execute(
                select(PricingAuditLog)
                .where(PricingAuditLog.product_id == product.id)
                .order_by(PricingAuditLog.timestamp.desc())
            )
            audit_log = logs_res.scalars().first()
            assert audit_log is not None
            assert audit_log.action == "PRICING_CONFIGURATION_CREATED" or audit_log.action == "PRICING_CONFIGURATION_UPDATED"
            assert audit_log.user_role == "Executive"
            assert audit_log.after_value["pricing_method"] == "COST_PLUS_MARKUP"

        # Cleanup
        await db.delete(product)
        await db.delete(category)
        await db.execute(delete(UserRole).where(UserRole.user_id.in_([user_rep.id, user_mgr.id, user_exec.id])))
        await db.delete(user_rep)
        await db.delete(user_mgr)
        await db.delete(user_exec)
        await db.commit()

        from backend.app.core.database import engine
        await engine.dispose()
