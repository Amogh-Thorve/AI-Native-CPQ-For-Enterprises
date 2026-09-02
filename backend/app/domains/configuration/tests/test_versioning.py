import pytest
import httpx
import uuid
from fastapi import status
from sqlalchemy import select, delete

from backend.app.main import app
from backend.app.core.database import SessionLocal, engine
from backend.app.domains.auth.services import AuthService
from backend.app.domains.auth.schemas import UserCreate, LoginRequest
from backend.app.domains.auth.models import User, Role, UserRole
from backend.app.domains.catalog.models import Product, Category
from backend.app.domains.configuration.models import (
    ProductConfigurationGroup, ProductConfigurationOption, ConfigurationRule,
    ConfigurationSession, ConfigurationVersion, BundleAuditLog
)

async def get_token_for_user(db, email, password):
    auth_service = AuthService(db)
    login_req = LoginRequest(email=email, password=password)
    res = await auth_service.authenticate(login_req)
    await db.commit()
    return res.access_token

@pytest.mark.asyncio
async def test_product_configuration_versioning_phase3():
    suffix = uuid.uuid4().hex[:6]
    password = "Password123!"
    
    async with SessionLocal() as db:
        auth_service = AuthService(db)
        
        # 1. Setup Category and Product
        category = Category(name=f"VersionHardware_{suffix}", description="Category for version tests")
        db.add(category)
        await db.commit()
        await db.refresh(category)

        product = Product(
            sku=f"VER-LAP-{suffix}", name="Versionable Laptop", description="Laptop for version testing",
            base_price=1500.00, currency="USD", is_active=True, billing_type="NRC", category_id=category.id
        )
        db.add(product)
        await db.commit()
        await db.refresh(product)

        # Create Representative and Executive for RBAC validation
        rep_email = f"rep_ver_{suffix}@cpq.com"
        user_rep = await auth_service.register_user(UserCreate(
            email=rep_email, first_name="Rep", last_name="Ver", username=f"rep_ve_{suffix}", password=password, confirm_password=password
        ))
        
        exec_email = f"exec_ver_{suffix}@cpq.com"
        user_exec = await auth_service.register_user(UserCreate(
            email=exec_email, first_name="Exec", last_name="Ver", username=f"exec_ve_{suffix}", password=password, confirm_password=password
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
            
            # --- STEP 1 & 2: Create Version 1 as DRAFT ---
            res_v1_draft = await client.post(
                f"/api/v1/configuration/products/{product.id}/versions/draft",
                json={"change_summary": "Initial setup"},
                headers=headers_exec
            )
            assert res_v1_draft.status_code == status.HTTP_201_CREATED
            v1_id = res_v1_draft.json()["id"]
            assert res_v1_draft.json()["status"] == "DRAFT"
            assert res_v1_draft.json()["version_number"] == 1

            # Populate structure for v1_id
            # Group: Ram
            res_g1 = await client.post(
                "/api/v1/configuration/groups",
                json={"product_id": product.id, "version_id": v1_id, "name": "Ram", "required": True, "selection_type": "SINGLE_SELECT"},
                headers=headers_exec
            )
            assert res_g1.status_code == status.HTTP_201_CREATED
            g1_id = res_g1.json()["id"]

            res_opt1 = await client.post(
                "/api/v1/configuration/options",
                json={"group_id": g1_id, "name": "16GB RAM", "value": "16gb"},
                headers=headers_exec
            )
            opt1_id = res_opt1.json()["id"]

            # --- STEP 3 & 4: Activate Version 1 ---
            res_act = await client.post(
                f"/api/v1/configuration/versions/{v1_id}/activate",
                headers=headers_exec
            )
            assert res_act.status_code == status.HTTP_200_OK
            assert res_act.json()["status"] == "ACTIVE"

            # Create session using active Version 1 (implicitly maps to V1 active)
            res_sess1 = await client.post(
                "/api/v1/configuration/sessions",
                json={
                    "product_id": product.id,
                    "selections": [
                        {"group_id": g1_id, "option_ids": [opt1_id]}
                    ]
                },
                headers=headers_rep
            )
            assert res_sess1.status_code == status.HTTP_201_CREATED
            sess1_id = res_sess1.json()["id"]

            # --- STEP 5: Create Version 2 as DRAFT ---
            res_v2_draft = await client.post(
                f"/api/v1/configuration/products/{product.id}/versions/draft",
                json={"change_summary": "Adding SSD custom tiers"},
                headers=headers_exec
            )
            assert res_v2_draft.status_code == status.HTTP_201_CREATED
            v2_id = res_v2_draft.json()["id"]
            assert res_v2_draft.json()["status"] == "DRAFT"
            assert res_v2_draft.json()["version_number"] == 2

            # --- STEP 6: Modify Version 2 ---
            # Create a new group inside Version 2 draft
            res_g2 = await client.post(
                "/api/v1/configuration/groups",
                json={"product_id": product.id, "version_id": v2_id, "name": "Storage Add-ons", "required": False, "selection_type": "SINGLE_SELECT"},
                headers=headers_exec
            )
            g2_id = res_g2.json()["id"]

            # --- STEP 7: Verify Version 1 is unaffected ---
            res_v1_groups = await client.get(
                f"/api/v1/configuration/products/{product.id}",
                headers=headers_rep
            )
            # Groups fetched from active configuration (V1) must only contain 1 group (Ram), not "Storage Add-ons"
            assert len(res_v1_groups.json()) == 1
            assert res_v1_groups.json()[0]["name"] == "Ram"

            # --- STEP 8 & 9: Activate Version 2 ---
            res_act2 = await client.post(
                f"/api/v1/configuration/versions/{v2_id}/activate",
                headers=headers_exec
            )
            assert res_act2.status_code == status.HTTP_200_OK
            assert res_act2.json()["status"] == "ACTIVE"

            # Check that Version 1 has become ARCHIVED
            res_v1_details = await client.get(f"/api/v1/configuration/versions/{v1_id}", headers=headers_rep)
            assert res_v1_details.json()["status"] == "ARCHIVED"

            # --- STEP 10: Verify new sessions use Version 2 ---
            # Active config groups must now include 2 groups (Ram and Storage Add-ons)
            res_v2_groups = await client.get(
                f"/api/v1/configuration/products/{product.id}",
                headers=headers_rep
            )
            assert len(res_v2_groups.json()) == 2

            # --- STEP 11: Compare versions differences ---
            res_diff = await client.get(
                f"/api/v1/configuration/versions/{v1_id}/compare/{v2_id}",
                headers=headers_rep
            )
            assert res_diff.status_code == status.HTTP_200_OK
            assert "Storage Add-ons" in res_diff.json()["added_groups"]

        # Clean DB
        async with SessionLocal() as db_clean:
            # Delete groups, options, rules, versions, sessions
            await db_clean.execute(delete(ProductConfigurationOption).where(ProductConfigurationOption.group_id.in_([g1_id, g2_id])))
            await db_clean.execute(delete(ProductConfigurationGroup).where(ProductConfigurationGroup.id.in_([g1_id, g2_id])))
            await db_clean.execute(delete(ConfigurationSession).where(ConfigurationSession.id == uuid.UUID(sess1_id)))
            await db_clean.execute(delete(ConfigurationVersion).where(ConfigurationVersion.id.in_([v1_id, v2_id])))
            await db_clean.delete(await db_clean.get(Product, product.id))
            await db_clean.delete(await db_clean.get(Category, category.id))
            await db_clean.execute(delete(UserRole).where(UserRole.user_id.in_([user_rep.id, user_exec.id])))
            await db_clean.delete(await db_clean.get(User, user_rep.id))
            await db_clean.delete(await db_clean.get(User, user_exec.id))
            await db_clean.commit()
