from fastapi import APIRouter, Depends, status, HTTPException
from typing import List, Optional
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.core.database import get_db
from backend.app.domains.auth.dependencies import PermissionChecker
from backend.app.domains.auth.models import User
from backend.app.domains.configuration.schemas import (
    ValidateConfigurationRequest, ValidateConfigurationResponse,
    ProductConfigurationGroupRead, ProductConfigurationGroupCreate, ProductConfigurationGroupUpdate,
    ProductConfigurationOptionRead, ProductConfigurationOptionCreate, ProductConfigurationOptionUpdate,
    ConfigurationRuleRead, ConfigurationRuleCreate, ConfigurationRuleUpdate,
    ConfigurationSessionRead, ConfigurationSessionCreate, SelectionItem,
    BundleRead, BundleCreate, BundleUpdate, BundleComponentRead, BundleComponentCreate, BundleComponentUpdate,
    ValidateBundleRequest, ValidateBundleResponse, BundleConfigurationSessionRead, BundleConfigurationSessionCreate,
    ComponentSelectionItem, ConfigurationVersionRead, ConfigurationVersionCreate, ConfigurationVersionUpdate,
    VersionComparisonResponse
)
from backend.app.domains.configuration.services import ConfigurationService

router = APIRouter(prefix="/configuration", tags=["configuration-engine"])

# --- Client Configuration Workflows ---

@router.get("/products/{product_id}", response_model=List[ProductConfigurationGroupRead])
async def get_product_configuration_structure(
    product_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker("configuration.configure"))
):
    """
    Get all configuration groups and options mapped for a specific product.
    """
    service = ConfigurationService(db)
    return await service.group_repo.list_by_product_id(product_id)

@router.post("/validate", response_model=ValidateConfigurationResponse)
async def validate_configuration(
    request: ValidateConfigurationRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker("configuration.configure"))
):
    """
    Evaluate selections, quantities, dependency, and exclusivity constraints on the backend.
    """
    service = ConfigurationService(db)
    return await service.validate_configuration(request)

@router.post("/sessions", response_model=ConfigurationSessionRead, status_code=status.HTTP_201_CREATED)
async def create_configuration_session(
    request: ConfigurationSessionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker("configuration.configure"))
):
    """
    Start or save a configuration session.
    """
    service = ConfigurationService(db)
    session = await service.create_session(
        product_id=request.product_id,
        user_id=current_user.id,
        selections=request.selections
    )
    await db.commit()
    return session

@router.get("/sessions/{session_id}", response_model=ConfigurationSessionRead)
async def get_configuration_session(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker("configuration.configure"))
):
    """
    Retrieve an active configuration session status.
    """
    service = ConfigurationService(db)
    return await service.get_session(session_id)

@router.put("/sessions/{session_id}", response_model=ConfigurationSessionRead)
async def update_configuration_session(
    session_id: uuid.UUID,
    selections: List[SelectionItem],
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker("configuration.configure"))
):
    """
    Update choices and state in an active session.
    """
    service = ConfigurationService(db)
    session = await service.update_session(session_id, selections)
    await db.commit()
    return session

# --- Configuration Administration ---

@router.post("/groups", response_model=ProductConfigurationGroupRead, status_code=status.HTTP_201_CREATED)
async def create_group(
    schema: ProductConfigurationGroupCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker("configuration.admin"))
):
    service = ConfigurationService(db)
    res = await service.create_group(schema)
    await db.commit()
    return res

@router.put("/groups/{group_id}", response_model=ProductConfigurationGroupRead)
async def update_group(
    group_id: int,
    schema: ProductConfigurationGroupUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker("configuration.admin"))
):
    service = ConfigurationService(db)
    res = await service.update_group(group_id, schema)
    await db.commit()
    return res

@router.post("/options", response_model=ProductConfigurationOptionRead, status_code=status.HTTP_201_CREATED)
async def create_option(
    schema: ProductConfigurationOptionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker("configuration.admin"))
):
    service = ConfigurationService(db)
    res = await service.create_option(schema)
    await db.commit()
    return res

@router.put("/options/{option_id}", response_model=ProductConfigurationOptionRead)
async def update_option(
    option_id: int,
    schema: ProductConfigurationOptionUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker("configuration.admin"))
):
    service = ConfigurationService(db)
    res = await service.update_option(option_id, schema)
    await db.commit()
    return res

@router.post("/rules", response_model=ConfigurationRuleRead, status_code=status.HTTP_201_CREATED)
async def create_rule(
    schema: ConfigurationRuleCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker("configuration.admin"))
):
    service = ConfigurationService(db)
    res = await service.create_rule(schema)
    await db.commit()
    return res

@router.put("/rules/{rule_id}", response_model=ConfigurationRuleRead)
async def update_rule(
    rule_id: int,
    schema: ConfigurationRuleUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker("configuration.admin"))
):
    service = ConfigurationService(db)
    res = await service.update_rule(rule_id, schema)
    await db.commit()
    return res

# --- Phase 2: Product Bundles Endpoints ---

@router.get("/bundles", response_model=List[BundleRead])
async def list_active_bundles(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker("configuration.configure"))
):
    """
    List all active bundles configured in the CPQ system.
    """
    service = ConfigurationService(db)
    return await service.bundle_repo.list_active()

@router.get("/bundles/{bundle_id}", response_model=BundleRead)
async def get_bundle_by_id(
    bundle_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker("configuration.configure"))
):
    """
    Retrieve bundle components and structural rules.
    """
    service = ConfigurationService(db)
    return await service.get_bundle(bundle_id)

@router.post("/bundles/{bundle_id}/validate", response_model=ValidateBundleResponse)
async def validate_bundle_selections(
    bundle_id: int,
    request: ValidateBundleRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker("configuration.configure"))
):
    """
    Run backend bundle validation checks (required elements, quantity constraints, nested product options checks).
    """
    if request.bundle_id != bundle_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Path bundle_id does not match body bundle_id.")
    service = ConfigurationService(db)
    return await service.validate_bundle(request)

@router.post("/bundles/sessions", response_model=BundleConfigurationSessionRead, status_code=status.HTTP_201_CREATED)
async def create_bundle_session(
    request: BundleConfigurationSessionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker("configuration.configure"))
):
    """
    Save draft selections as a bundle configuration session.
    """
    service = ConfigurationService(db)
    session = await service.create_bundle_session(
        bundle_id=request.bundle_id,
        user_id=current_user.id,
        selections=request.selections
    )
    # Log Audit BUNDLE_SESSION_CREATED or similar
    await service.bundle_audit_repo.log(
        user_id=current_user.id,
        user_role=current_user.roles[0].name if current_user.roles else None,
        action="BUNDLE_SESSION_CREATED",
        bundle_id=request.bundle_id,
        after_value={"session_id": str(session.id)}
    )
    await db.commit()
    return session

@router.get("/bundles/sessions/{session_id}", response_model=BundleConfigurationSessionRead)
async def get_bundle_session(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker("configuration.configure"))
):
    """
    Retrieve an active bundle configuration session state.
    """
    service = ConfigurationService(db)
    return await service.get_bundle_session(session_id)

@router.put("/bundles/sessions/{session_id}", response_model=BundleConfigurationSessionRead)
async def update_bundle_session(
    session_id: uuid.UUID,
    selections: List[ComponentSelectionItem],
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker("configuration.configure"))
):
    """
    Update selections and quantities in a draft bundle configuration session.
    """
    service = ConfigurationService(db)
    session = await service.update_bundle_session(session_id, selections)
    await db.commit()
    return session

# --- Bundle Administration (Executive & Admin Only) ---

@router.post("/bundles", response_model=BundleRead, status_code=status.HTTP_201_CREATED)
async def create_bundle(
    schema: BundleCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker("configuration.admin"))
):
    service = ConfigurationService(db)
    bundle = await service.create_bundle(schema, current_user.id)
    await service.bundle_audit_repo.log(
        user_id=current_user.id,
        user_role=current_user.roles[0].name if current_user.roles else None,
        action="BUNDLE_CREATED",
        bundle_id=bundle.id,
        after_value=schema.model_dump()
    )
    await db.commit()
    # Refresh to load components
    return await service.get_bundle(bundle.id)

@router.put("/bundles/{bundle_id}", response_model=BundleRead)
async def update_bundle(
    bundle_id: int,
    schema: BundleUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker("configuration.admin"))
):
    service = ConfigurationService(db)
    bundle = await service.get_bundle(bundle_id)
    before_val = {"name": bundle.name, "description": bundle.description, "sku": bundle.sku, "is_active": bundle.is_active}
    
    updated_bundle = await service.update_bundle(bundle_id, schema, current_user.id)
    
    action = "BUNDLE_UPDATED"
    if schema.is_active is not None:
        if schema.is_active and not bundle.is_active:
            action = "BUNDLE_ACTIVATED"
        elif not schema.is_active and bundle.is_active:
            action = "BUNDLE_DEACTIVATED"

    await service.bundle_audit_repo.log(
        user_id=current_user.id,
        user_role=current_user.roles[0].name if current_user.roles else None,
        action=action,
        bundle_id=bundle_id,
        before_value=before_val,
        after_value=schema.model_dump(exclude_unset=True)
    )
    await db.commit()
    return await service.get_bundle(bundle_id)

@router.post("/bundles/{bundle_id}/components", response_model=BundleComponentRead, status_code=status.HTTP_201_CREATED)
async def add_bundle_component(
    bundle_id: int,
    schema: BundleComponentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker("configuration.admin"))
):
    service = ConfigurationService(db)
    comp = await service.add_component(bundle_id, schema)
    await service.bundle_audit_repo.log(
        user_id=current_user.id,
        user_role=current_user.roles[0].name if current_user.roles else None,
        action="BUNDLE_COMPONENT_ADDED",
        bundle_id=bundle_id,
        after_value=schema.model_dump()
    )
    await db.commit()
    # Refresh/preload product info
    return await service.comp_repo.get_by_id(comp.id)

@router.delete("/bundles/{bundle_id}/components/{component_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_bundle_component(
    bundle_id: int,
    component_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker("configuration.admin"))
):
    service = ConfigurationService(db)
    comp = await service.comp_repo.get_by_id(component_id)
    if not comp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Component {component_id} not found.")
    
    before_val = {"id": comp.id, "product_id": comp.product_id}
    await service.remove_component(component_id)
    await service.bundle_audit_repo.log(
        user_id=current_user.id,
        user_role=current_user.roles[0].name if current_user.roles else None,
        action="BUNDLE_COMPONENT_REMOVED",
        bundle_id=bundle_id,
        before_value=before_val
    )
    await db.commit()

# --- Phase 3: Versioning & Lifecycle Endpoints ---

@router.get("/products/{product_id}/versions", response_model=List[ConfigurationVersionRead])
async def list_product_configuration_versions(
    product_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker("configuration.configure"))
):
    """
    Get all blueprints versions list for a product.
    """
    service = ConfigurationService(db)
    return await service.list_versions("PRODUCT", product_id)

@router.post("/products/{product_id}/versions/draft", response_model=ConfigurationVersionRead, status_code=status.HTTP_201_CREATED)
async def create_product_configuration_draft(
    product_id: int,
    change_summary: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker("configuration.admin"))
):
    """
    Copy active product configuration blueprints to a new editable DRAFT.
    """
    service = ConfigurationService(db)
    draft = await service.create_draft_version("PRODUCT", product_id, change_summary, current_user.id)
    await db.commit()
    return draft

@router.get("/bundles/{bundle_id}/versions", response_model=List[ConfigurationVersionRead])
async def list_bundle_configuration_versions(
    bundle_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker("configuration.configure"))
):
    """
    Get all blueprints versions list for a bundle.
    """
    service = ConfigurationService(db)
    return await service.list_versions("BUNDLE", bundle_id)

@router.post("/bundles/{bundle_id}/versions/draft", response_model=ConfigurationVersionRead, status_code=status.HTTP_201_CREATED)
async def create_bundle_configuration_draft(
    bundle_id: int,
    change_summary: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker("configuration.admin"))
):
    """
    Copy active bundle components blueprints to a new editable DRAFT.
    """
    service = ConfigurationService(db)
    draft = await service.create_draft_version("BUNDLE", bundle_id, change_summary, current_user.id)
    await db.commit()
    return draft

@router.get("/versions/{version_id}", response_model=ConfigurationVersionRead)
async def get_version_details(
    version_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker("configuration.configure"))
):
    """
    Retrieve details of a configuration version.
    """
    service = ConfigurationService(db)
    return await service.get_version(version_id)

@router.post("/versions/{version_id}/activate", response_model=ConfigurationVersionRead)
async def activate_configuration_version(
    version_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker("configuration.admin"))
):
    """
    Promote a DRAFT version to ACTIVE.
    """
    service = ConfigurationService(db)
    version = await service.activate_version(version_id, current_user.id)
    await db.commit()
    return version

@router.post("/versions/{version_id}/archive", response_model=ConfigurationVersionRead)
async def archive_configuration_version(
    version_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker("configuration.admin"))
):
    """
    Demote/archive a configuration version.
    """
    service = ConfigurationService(db)
    version = await service.archive_version(version_id, current_user.id)
    await db.commit()
    return version

@router.get("/versions/{version_id}/compare/{other_version_id}", response_model=VersionComparisonResponse)
async def compare_configuration_versions(
    version_id: int,
    other_version_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker("configuration.configure"))
):
    """
    Compare differences in attribute groups or options between two versions.
    """
    service = ConfigurationService(db)
    return await service.compare_versions(version_id, other_version_id)


