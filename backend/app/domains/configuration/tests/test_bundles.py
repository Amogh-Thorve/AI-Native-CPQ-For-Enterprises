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
    Bundle, BundleComponent, BundleConfigurationSession, BundleAuditLog
)

async def get_token_for_user(db, email, password):
    auth_service = AuthService(db)
    login_req = LoginRequest(email=email, password=password)
    res = await auth_service.authenticate(login_req)
    await db.commit()
    return res.access_token

@pytest.mark.asyncio
async def test_product_bundles_module_phase2():
    suffix = uuid.uuid4().hex[:6]
    password = "Password123!"
    
    async with SessionLocal() as db:
        auth_service = AuthService(db)
        
        # 1. Setup Catalog details
        category = Category(name=f"BundleHardware_{suffix}", description="Category for bundle tests")
        db.add(category)
        await db.commit()
        await db.refresh(category)

        # Standard non-configurable product: Server Core Platform
        prod_core = Product(
            sku=f"CORE-SVR-{suffix}", name="Core Platform Svr", description="Base hardware server core platform",
            base_price=5000.00, currency="USD", is_active=True, billing_type="NRC", category_id=category.id
        )
        # Configurable product: Software Subscription Tier (we will configure it)
        prod_software = Product(
            sku=f"SOFT-SUB-{suffix}", name="Configurable SaaS Core", description="SaaS subscription layer with options",
            base_price=100.00, currency="USD", is_active=True, billing_type="MRC", category_id=category.id
        )
        # Optional product: Analytics add-on
        prod_analytics = Product(
            sku=f"ANL-ADD-{suffix}", name="Analytics Add-on", description="Analytics plugin",
            base_price=500.00, currency="USD", is_active=True, billing_type="MRC", category_id=category.id
        )
        # Inactive product: Obsolete database connector
        prod_obsolete = Product(
            sku=f"OBS-DB-{suffix}", name="Obsolete DB Connector", description="Obsolete database connector",
            base_price=300.00, currency="USD", is_active=False, billing_type="NRC", category_id=category.id
        )

        db.add_all([prod_core, prod_software, prod_analytics, prod_obsolete])
        await db.commit()
        await db.refresh(prod_core)
        await db.refresh(prod_software)
        await db.refresh(prod_analytics)
        await db.refresh(prod_obsolete)

        # 2. Setup Configuration Groups and Options for the Configurable SaaS product (prod_software)
        config_group = ProductConfigurationGroup(
            product_id=prod_software.id, name="SaaS Tier", required=True, selection_type="SINGLE_SELECT"
        )
        db.add(config_group)
        await db.commit()
        await db.refresh(config_group)

        opt_basic = ProductConfigurationOption(
            group_id=config_group.id, name="Basic Tier", value="basic", is_active=True
        )
        opt_enterprise = ProductConfigurationOption(
            group_id=config_group.id, name="Enterprise Tier", value="enterprise", is_active=True
        )
        db.add_all([opt_basic, opt_enterprise])
        await db.commit()
        await db.refresh(opt_basic)
        await db.refresh(opt_enterprise)

        # 3. Define Bundle & Components
        bundle = Bundle(
            name="Enterprise IT Platform Bundle",
            description="Complete hardware server and software tier package",
            sku=f"BNDL-ENT-IT-{suffix}",
            is_active=True
        )
        db.add(bundle)
        await db.commit()
        await db.refresh(bundle)

        # Core Server component: Required
        comp_core = BundleComponent(
            bundle_id=bundle.id, product_id=prod_core.id, required=True, default_selected=True,
            min_quantity=1, max_quantity=2, default_quantity=1, display_order=1
        )
        # Configurable SaaS Component: Required
        comp_soft = BundleComponent(
            bundle_id=bundle.id, product_id=prod_software.id, required=True, default_selected=True,
            min_quantity=1, max_quantity=5, default_quantity=1, display_order=2
        )
        # Optional Analytics Component: Optional
        comp_anl = BundleComponent(
            bundle_id=bundle.id, product_id=prod_analytics.id, required=False, default_selected=False,
            min_quantity=1, max_quantity=10, default_quantity=1, display_order=3
        )
        # Inactive Component: Optional
        comp_obs = BundleComponent(
            bundle_id=bundle.id, product_id=prod_obsolete.id, required=False, default_selected=False,
            min_quantity=1, max_quantity=10, default_quantity=1, display_order=4
        )

        db.add_all([comp_core, comp_soft, comp_anl, comp_obs])
        await db.commit()
        await db.refresh(comp_core)
        await db.refresh(comp_soft)
        await db.refresh(comp_anl)
        await db.refresh(comp_obs)

        # Create Representative and Executive for RBAC validation
        rep_email = f"rep_bnd_{suffix}@cpq.com"
        user_rep = await auth_service.register_user(UserCreate(
            email=rep_email, first_name="Rep", last_name="Bndl", username=f"rep_bn_{suffix}", password=password, confirm_password=password
        ))
        
        exec_email = f"exec_bnd_{suffix}@cpq.com"
        user_exec = await auth_service.register_user(UserCreate(
            email=exec_email, first_name="Exec", last_name="Bndl", username=f"exec_bn_{suffix}", password=password, confirm_password=password
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
            
            # --- 1. GET Bundle Details ---
            res = await client.get(f"/api/v1/configuration/bundles/{bundle.id}", headers=headers_rep)
            assert res.status_code == status.HTTP_200_OK
            bndl_data = res.json()
            assert len(bndl_data["components"]) == 4

            # --- 2. VALIDATION TESTING ---

            # A. REQUIRED COMPONENT: Core component not selected must fail
            res_val = await client.post(
                f"/api/v1/configuration/bundles/{bundle.id}/validate",
                json={
                    "bundle_id": bundle.id,
                    "selections": [
                        {"component_id": comp_core.id, "selected": False, "quantity": 1},
                        {"component_id": comp_soft.id, "selected": True, "quantity": 1, "configuration": {
                            "product_id": prod_software.id, "selections": [{"group_id": config_group.id, "option_ids": [opt_basic.id]}]
                        }}
                    ]
                },
                headers=headers_rep
            )
            assert res_val.status_code == status.HTTP_200_OK
            assert res_val.json()["valid"] is False
            err_types = [e["type"] for e in res_val.json()["errors"]]
            assert "REQUIRED_COMPONENT" in err_types

            # B. QUANTITY: Below min or above max must fail
            res_val = await client.post(
                f"/api/v1/configuration/bundles/{bundle.id}/validate",
                json={
                    "bundle_id": bundle.id,
                    "selections": [
                        {"component_id": comp_core.id, "selected": True, "quantity": 5}, # max: 2
                        {"component_id": comp_soft.id, "selected": True, "quantity": 1, "configuration": {
                            "product_id": prod_software.id, "selections": [{"group_id": config_group.id, "option_ids": [opt_basic.id]}]
                        }}
                    ]
                },
                headers=headers_rep
            )
            assert res_val.json()["valid"] is False
            err_types = [e["type"] for e in res_val.json()["errors"]]
            assert "QUANTITY" in err_types

            # C. CONFIGURABLE PRODUCT: Configurable product with invalid nested config must fail
            res_val = await client.post(
                f"/api/v1/configuration/bundles/{bundle.id}/validate",
                json={
                    "bundle_id": bundle.id,
                    "selections": [
                        {"component_id": comp_core.id, "selected": True, "quantity": 1},
                        {"component_id": comp_soft.id, "selected": True, "quantity": 1, "configuration": {
                            "product_id": prod_software.id, "selections": [] # missing SaaS tier selection (which is required)
                        }}
                    ]
                },
                headers=headers_rep
            )
            assert res_val.json()["valid"] is False
            err_types = [e["type"] for e in res_val.json()["errors"]]
            assert "CONFIGURATION" in err_types

            # D. INACTIVE PRODUCT: Fails if obsolete product selected
            res_val = await client.post(
                f"/api/v1/configuration/bundles/{bundle.id}/validate",
                json={
                    "bundle_id": bundle.id,
                    "selections": [
                        {"component_id": comp_core.id, "selected": True, "quantity": 1},
                        {"component_id": comp_soft.id, "selected": True, "quantity": 1, "configuration": {
                            "product_id": prod_software.id, "selections": [{"group_id": config_group.id, "option_ids": [opt_basic.id]}]
                        }},
                        {"component_id": comp_obs.id, "selected": True, "quantity": 1}
                    ]
                },
                headers=headers_rep
            )
            assert res_val.json()["valid"] is False
            err_types = [e["type"] for e in res_val.json()["errors"]]
            assert "INACTIVE_PRODUCT" in err_types

            # E. VALID BUNDLE: Core selection and valid config passes
            res_val = await client.post(
                f"/api/v1/configuration/bundles/{bundle.id}/validate",
                json={
                    "bundle_id": bundle.id,
                    "selections": [
                        {"component_id": comp_core.id, "selected": True, "quantity": 1},
                        {"component_id": comp_soft.id, "selected": True, "quantity": 1, "configuration": {
                            "product_id": prod_software.id, "selections": [{"group_id": config_group.id, "option_ids": [opt_basic.id]}]
                        }}
                    ]
                },
                headers=headers_rep
            )
            assert res_val.json()["valid"] is True

            # --- 3. SESSION CRUD WORKFLOW ---
            res_sess = await client.post(
                "/api/v1/configuration/bundles/sessions",
                json={
                    "bundle_id": bundle.id,
                    "selections": [
                        {"component_id": comp_core.id, "selected": True, "quantity": 1},
                        {"component_id": comp_soft.id, "selected": True, "quantity": 1, "configuration": {
                            "product_id": prod_software.id, "selections": [{"group_id": config_group.id, "option_ids": [opt_basic.id]}]
                        }}
                    ]
                },
                headers=headers_rep
            )
            assert res_sess.status_code == status.HTTP_201_CREATED
            sess_id = res_sess.json()["id"]

            res_get_sess = await client.get(f"/api/v1/configuration/bundles/sessions/{sess_id}", headers=headers_rep)
            assert res_get_sess.status_code == status.HTTP_200_OK
            assert res_get_sess.json()["is_valid"] is True

            # --- 4. RBAC CHECKS ---
            
            # Rep cannot create bundles
            res_rbac_err = await client.post(
                "/api/v1/configuration/bundles",
                json={"name": "Rep Obstructive Bundle", "sku": f"BNDL-REP-{suffix}"},
                headers=headers_rep
            )
            assert res_rbac_err.status_code == status.HTTP_403_FORBIDDEN

            # Executive can create bundles
            res_rbac_ok = await client.post(
                "/api/v1/configuration/bundles",
                json={"name": "Exec Validated Bundle", "sku": f"BNDL-EXC-{suffix}"},
                headers=headers_exec
            )
            assert res_rbac_ok.status_code == status.HTTP_201_CREATED
            new_bundle_id = res_rbac_ok.json()["id"]

            # Executive can add bundle component
            res_add_comp = await client.post(
                f"/api/v1/configuration/bundles/{new_bundle_id}/components",
                json={
                    "product_id": prod_analytics.id, "required": False, "default_selected": False,
                    "min_quantity": 1, "default_quantity": 1
                },
                headers=headers_exec
            )
            assert res_add_comp.status_code == status.HTTP_201_CREATED

            # Executive can delete bundle component
            res_del_comp = await client.delete(
                f"/api/v1/configuration/bundles/{new_bundle_id}/components/{res_add_comp.json()['id']}",
                headers=headers_exec
            )
            assert res_del_comp.status_code == status.HTTP_204_NO_CONTENT

            # Clean created bundle
            new_bundle_db = await db.get(Bundle, new_bundle_id)
            if new_bundle_db:
                await db.delete(new_bundle_db)
                await db.commit()

        # Audit persistence check
        audit_log = (await db.execute(
            select(BundleAuditLog).where(BundleAuditLog.bundle_id == bundle.id)
        )).scalars().first()
        # Since audit logging is triggered on session/bundle modifications
        # Let's confirm it tracks logs
        assert audit_log is not None

        # Clean DB
        await db.delete(comp_core)
        await db.delete(comp_soft)
        await db.delete(comp_anl)
        await db.delete(comp_obs)
        await db.delete(bundle)
        await db.delete(opt_basic)
        await db.delete(opt_enterprise)
        await db.delete(config_group)
        await db.delete(prod_core)
        await db.delete(prod_software)
        await db.delete(prod_analytics)
        await db.delete(prod_obsolete)
        await db.delete(category)
        await db.execute(delete(UserRole).where(UserRole.user_id.in_([user_rep.id, user_exec.id])))
        await db.delete(user_rep)
        await db.delete(user_exec)
        await db.commit()
