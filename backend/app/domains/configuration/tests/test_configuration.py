import pytest
import httpx
import uuid
from fastapi import status
from sqlalchemy import select, delete

from backend.app.main import app
from backend.app.core.database import SessionLocal
from backend.app.domains.auth.services import AuthService
from backend.app.domains.auth.schemas import UserCreate, LoginRequest
from backend.app.domains.auth.models import User, Role, UserRole
from backend.app.domains.catalog.models import Product, Category
from backend.app.domains.configuration.models import (
    ProductConfigurationGroup, ProductConfigurationOption, ConfigurationRule, ConfigurationSession
)

async def get_token_for_user(db, email, password):
    auth_service = AuthService(db)
    login_req = LoginRequest(email=email, password=password)
    res = await auth_service.authenticate(login_req)
    await db.commit()
    return res.access_token

@pytest.mark.asyncio
async def test_product_configuration_module_phase1():
    suffix = uuid.uuid4().hex[:6]
    password = "Password123!"
    
    async with SessionLocal() as db:
        auth_service = AuthService(db)
        
        # Setup Catalog details
        category = Category(name=f"ConfigHardware_{suffix}", description="Category for config tests")
        db.add(category)
        await db.commit()
        await db.refresh(category)

        product = Product(
            sku=f"CFG-LAP-{suffix}",
            name="Configurable Laptop",
            description="Laptop for testing configuration",
            base_price=1000.00,
            cost_price=700.00,
            currency="USD",
            is_active=True,
            billing_type="NRC",
            category_id=category.id
        )
        db.add(product)
        await db.commit()
        await db.refresh(product)

        # Setup Configuration structure in database
        # 1. Group: Plan (Required, SINGLE_SELECT)
        group_plan = ProductConfigurationGroup(
            product_id=product.id,
            name="Plan",
            description="Software subscription plan",
            required=True,
            selection_type="SINGLE_SELECT",
            display_order=1,
            is_active=True
        )
        # 2. Group: Support (Optional, SINGLE_SELECT)
        group_support = ProductConfigurationGroup(
            product_id=product.id,
            name="Support",
            description="Tech support plans",
            required=False,
            selection_type="SINGLE_SELECT",
            display_order=2,
            is_active=True
        )
        # 3. Group: Add-ons (Optional, MULTI_SELECT)
        group_addons = ProductConfigurationGroup(
            product_id=product.id,
            name="Add-ons",
            description="Optional software add-ons",
            required=False,
            selection_type="MULTI_SELECT",
            display_order=3,
            is_active=True
        )
        db.add_all([group_plan, group_support, group_addons])
        await db.commit()
        await db.refresh(group_plan)
        await db.refresh(group_support)
        await db.refresh(group_addons)

        # Populate Options
        # Plans
        opt_basic = ProductConfigurationOption(
            group_id=group_plan.id, name="Basic", value="basic", display_order=1, is_active=True
        )
        opt_enterprise = ProductConfigurationOption(
            group_id=group_plan.id, name="Enterprise", value="enterprise", display_order=2, is_active=True
        )
        opt_inactive = ProductConfigurationOption(
            group_id=group_plan.id, name="Inactive Plan", value="inactive", display_order=3, is_active=False
        )
        # Support
        opt_standard = ProductConfigurationOption(
            group_id=group_support.id, name="Standard Support", value="standard", display_order=1, is_active=True
        )
        # Add-ons
        opt_analytics = ProductConfigurationOption(
            group_id=group_addons.id, name="AI Analytics", value="analytics", display_order=1, is_active=True
        )
        opt_users = ProductConfigurationOption(
            group_id=group_addons.id, name="Users", value="users", min_quantity=10, max_quantity=100, display_order=2, is_active=True
        )
        db.add_all([opt_basic, opt_enterprise, opt_inactive, opt_standard, opt_analytics, opt_users])
        await db.commit()
        await db.refresh(opt_basic)
        await db.refresh(opt_enterprise)
        await db.refresh(opt_inactive)
        await db.refresh(opt_standard)
        await db.refresh(opt_analytics)
        await db.refresh(opt_users)

        # Populate Rules
        # 1. AI Analytics REQUIRES Enterprise Plan
        rule_requires = ConfigurationRule(
            product_id=product.id,
            rule_type="REQUIRES",
            source_option_id=opt_analytics.id,
            target_option_id=opt_enterprise.id,
            message="AI Analytics requires Enterprise Plan.",
            is_active=True
        )
        # 2. Basic Plan EXCLUDES Standard Support
        rule_excludes = ConfigurationRule(
            product_id=product.id,
            rule_type="EXCLUDES",
            source_option_id=opt_basic.id,
            target_option_id=opt_standard.id,
            message="Standard Support is not compatible with Basic Plan.",
            is_active=True
        )
        db.add_all([rule_requires, rule_excludes])
        await db.commit()

        # Create Representative and Executive for RBAC validation
        rep_email = f"rep_cfg_{suffix}@cpq.com"
        user_rep = await auth_service.register_user(UserCreate(
            email=rep_email, first_name="Rep", last_name="Cfg", username=f"rep_cf_{suffix}", password=password, confirm_password=password
        ))
        
        exec_email = f"exec_cfg_{suffix}@cpq.com"
        user_exec = await auth_service.register_user(UserCreate(
            email=exec_email, first_name="Exec", last_name="Cfg", username=f"exec_cf_{suffix}", password=password, confirm_password=password
        ))
        await db.commit()

        user_rep = await auth_service.user_repo.get_by_id(user_rep.id)
        user_exec = await auth_service.user_repo.get_by_id(user_exec.id)

        user_rep.roles = []
        user_exec.roles = []

        role_rep = (await db.execute(select(Role).where(Role.name == "Sales Representative"))).scalars().first()
        role_exec = (await db.execute(select(Role).where(Role.name == "Executive"))).scalars().first()

        user_rep.roles.append(role_rep)
        user_exec.roles.append(role_exec)
        await db.commit()

        token_rep = await get_token_for_user(db, rep_email, password)
        headers_rep = {"Authorization": f"Bearer {token_rep}"}

        token_exec = await get_token_for_user(db, exec_email, password)
        headers_exec = {"Authorization": f"Bearer {token_exec}"}

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            
            # --- 1. GET Product Configuration Structure ---
            res = await client.get(f"/api/v1/configuration/products/{product.id}", headers=headers_rep)
            assert res.status_code == status.HTTP_200_OK
            structure = res.json()
            assert len(structure) == 3  # Plan, Support, Add-ons
            
            # --- 2. Validation Checks ---

            # A. REQUIRED GROUP: A required group (Plan) without selection must fail validation
            res_val = await client.post(
                "/api/v1/configuration/validate",
                json={
                    "product_id": product.id,
                    "selections": [
                        {"group_id": group_support.id, "option_ids": [opt_standard.id]}
                    ]
                },
                headers=headers_rep
            )
            assert res_val.status_code == status.HTTP_200_OK
            assert res_val.json()["valid"] is False
            errors = {e["rule_type"]: e for e in res_val.json()["errors"]}
            assert "REQUIRED_GROUP" in errors

            # B. SINGLE SELECT: Multiple selections in a single-select group must fail
            res_val = await client.post(
                "/api/v1/configuration/validate",
                json={
                    "product_id": product.id,
                    "selections": [
                        {"group_id": group_plan.id, "option_ids": [opt_basic.id, opt_enterprise.id]}
                    ]
                },
                headers=headers_rep
            )
            assert res_val.json()["valid"] is False
            errors = {e["rule_type"]: e for e in res_val.json()["errors"]}
            assert "SINGLE_SELECT" in errors

            # C. REQUIRES RULE: AI Analytics requires Enterprise Plan. Fail if Basic is selected.
            res_val = await client.post(
                "/api/v1/configuration/validate",
                json={
                    "product_id": product.id,
                    "selections": [
                        {"group_id": group_plan.id, "option_ids": [opt_basic.id]},
                        {"group_id": group_addons.id, "option_ids": [opt_analytics.id]}
                    ]
                },
                headers=headers_rep
            )
            assert res_val.json()["valid"] is False
            errors = {e["rule_type"]: e for e in res_val.json()["errors"]}
            assert "REQUIRES" in errors
            assert errors["REQUIRES"]["message"] == "AI Analytics requires Enterprise Plan."

            # D. EXCLUDES RULE: Basic Plan excludes Standard Support. Fail if both selected.
            res_val = await client.post(
                "/api/v1/configuration/validate",
                json={
                    "product_id": product.id,
                    "selections": [
                        {"group_id": group_plan.id, "option_ids": [opt_basic.id]},
                        {"group_id": group_support.id, "option_ids": [opt_standard.id]}
                    ]
                },
                headers=headers_rep
            )
            assert res_val.json()["valid"] is False
            errors = {e["rule_type"]: e for e in res_val.json()["errors"]}
            assert "EXCLUDES" in errors

            # E. VALID CONFIGURATION: Enterprise Plan + Standard Support + AI Analytics. Must pass.
            res_val = await client.post(
                "/api/v1/configuration/validate",
                json={
                    "product_id": product.id,
                    "selections": [
                        {"group_id": group_plan.id, "option_ids": [opt_enterprise.id]},
                        {"group_id": group_support.id, "option_ids": [opt_standard.id]},
                        {"group_id": group_addons.id, "option_ids": [opt_analytics.id]}
                    ]
                },
                headers=headers_rep
            )
            assert res_val.json()["valid"] is True

            # F. INACTIVE OPTION: Selecting an inactive option must fail
            res_val = await client.post(
                "/api/v1/configuration/validate",
                json={
                    "product_id": product.id,
                    "selections": [
                        {"group_id": group_plan.id, "option_ids": [opt_inactive.id]}
                    ]
                },
                headers=headers_rep
            )
            assert res_val.json()["valid"] is False
            errors = {e["rule_type"]: e for e in res_val.json()["errors"]}
            assert "INACTIVE_OPTION" in errors or "INVALID_OPTION" in errors

            # G. QUANTITY: Below minimum, above maximum, and negative quantity checks
            # Below minimum (Users min: 10, select 5)
            res_val = await client.post(
                "/api/v1/configuration/validate",
                json={
                    "product_id": product.id,
                    "selections": [
                        {"group_id": group_plan.id, "option_ids": [opt_enterprise.id]},
                        {"group_id": group_addons.id, "option_ids": [opt_users.id], "quantities": {str(opt_users.id): 5}}
                    ]
                },
                headers=headers_rep
            )
            assert res_val.json()["valid"] is False
            errors = {e["rule_type"]: e for e in res_val.json()["errors"]}
            assert "QUANTITY" in errors

            # Above maximum (Users max: 100, select 150)
            res_val = await client.post(
                "/api/v1/configuration/validate",
                json={
                    "product_id": product.id,
                    "selections": [
                        {"group_id": group_plan.id, "option_ids": [opt_enterprise.id]},
                        {"group_id": group_addons.id, "option_ids": [opt_users.id], "quantities": {str(opt_users.id): 150}}
                    ]
                },
                headers=headers_rep
            )
            assert res_val.json()["valid"] is False
            
            # Negative quantity (select -1)
            res_val = await client.post(
                "/api/v1/configuration/validate",
                json={
                    "product_id": product.id,
                    "selections": [
                        {"group_id": group_plan.id, "option_ids": [opt_enterprise.id]},
                        {"group_id": group_addons.id, "option_ids": [opt_users.id], "quantities": {str(opt_users.id): -1}}
                    ]
                },
                headers=headers_rep
            )
            assert res_val.json()["valid"] is False

            # --- 3. Sessions Validation ---
            res_sess = await client.post(
                "/api/v1/configuration/sessions",
                json={
                    "product_id": product.id,
                    "selections": [
                        {"group_id": group_plan.id, "option_ids": [opt_enterprise.id]}
                    ]
                },
                headers=headers_rep
            )
            assert res_sess.status_code == status.HTTP_201_CREATED
            sess_id = res_sess.json()["id"]

            # Retrieve session
            res_get_sess = await client.get(f"/api/v1/configuration/sessions/{sess_id}", headers=headers_rep)
            assert res_get_sess.status_code == status.HTTP_200_OK
            assert res_get_sess.json()["is_valid"] is True

            # --- 4. RBAC Administration Checks ---

            # Sales Rep cannot create configuration groups
            res_admin_err = await client.post(
                "/api/v1/configuration/groups",
                json={"product_id": product.id, "name": "New Admin Group", "required": True, "selection_type": "SINGLE_SELECT"},
                headers=headers_rep
            )
            assert res_admin_err.status_code == status.HTTP_403_FORBIDDEN

            # Executive can create configuration groups
            res_admin_ok = await client.post(
                "/api/v1/configuration/groups",
                json={"product_id": product.id, "name": "Admin Option Group", "required": False, "selection_type": "SINGLE_SELECT"},
                headers=headers_exec
            )
            assert res_admin_ok.status_code == status.HTTP_201_CREATED
            assert res_admin_ok.json()["name"] == "Admin Option Group"

        # Cleanup
        await db.delete(rule_requires)
        await db.delete(rule_excludes)
        await db.delete(opt_basic)
        await db.delete(opt_enterprise)
        await db.delete(opt_inactive)
        await db.delete(opt_standard)
        await db.delete(opt_analytics)
        await db.delete(opt_users)
        await db.delete(group_plan)
        await db.delete(group_support)
        await db.delete(group_addons)
        await db.delete(product)
        await db.delete(category)
        await db.execute(delete(UserRole).where(UserRole.user_id.in_([user_rep.id, user_exec.id])))
        await db.delete(user_rep)
        await db.delete(user_exec)
        await db.commit()
