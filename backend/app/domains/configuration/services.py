from typing import List, Optional
import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.core.exceptions import EntityNotFoundError, DomainValidationError
from backend.app.domains.configuration.models import (
    ConfigRuleType, ConfigurationSession, Bundle, BundleComponent,
    BundleConfigurationSession, BundleAuditLog, ConfigurationVersion,
    ProductConfigurationGroup, ProductConfigurationOption, ConfigurationRule
)
from backend.app.domains.configuration.repositories import (
    ProductConfigurationGroupRepository,
    ProductConfigurationOptionRepository,
    ConfigurationRuleRepository,
    ConfigurationSessionRepository,
    BundleRepository,
    BundleComponentRepository,
    BundleConfigurationSessionRepository,
    BundleAuditLogRepository,
    ConfigurationVersionRepository
)
from backend.app.domains.configuration.schemas import (
    ValidateConfigurationRequest, ValidateConfigurationResponse, ConfigurationErrorDetail,
    ProductConfigurationGroupCreate, ProductConfigurationGroupUpdate,
    ProductConfigurationOptionCreate, ProductConfigurationOptionUpdate,
    ConfigurationRuleCreate, ConfigurationRuleUpdate, SelectionItem,
    ValidateBundleRequest, ValidateBundleResponse, BundleErrorDetail,
    BundleCreate, BundleUpdate, BundleComponentCreate, BundleComponentUpdate,
    ComponentSelectionItem, ConfigurationVersionCreate, ConfigurationVersionUpdate, ConfigurationVersionRead
)

class ConfigurationService:
    """
    Core configuration use-cases including constraint validation, dependency check,
    rules administration, and session tracking.
    """
    def __init__(self, db: AsyncSession):
        self.db = db
        self.group_repo = ProductConfigurationGroupRepository(db)
        self.option_repo = ProductConfigurationOptionRepository(db)
        self.config_repo = ConfigurationRuleRepository(db)
        self.session_repo = ConfigurationSessionRepository(db)
        self.bundle_repo = BundleRepository(db)
        self.comp_repo = BundleComponentRepository(db)
        self.bundle_sess_repo = BundleConfigurationSessionRepository(db)
        self.bundle_audit_repo = BundleAuditLogRepository(db)

    # --- Rule Administration ---

    async def create_rule(self, schema: ConfigurationRuleCreate) -> any:
        return await self.config_repo.create(schema)

    async def get_rule(self, rule_id: int) -> any:
        rule = await self.config_repo.get_by_id(rule_id)
        if not rule:
            raise EntityNotFoundError(f"Configuration rule {rule_id} not found.")
        return rule

    async def update_rule(self, rule_id: int, schema: ConfigurationRuleUpdate) -> any:
        rule = await self.get_rule(rule_id)
        return await self.config_repo.update(rule, schema)

    # --- Group & Option Administration ---

    async def create_group(self, schema: ProductConfigurationGroupCreate) -> any:
        return await self.group_repo.create(schema)

    async def update_group(self, group_id: int, schema: ProductConfigurationGroupUpdate) -> any:
        group = await self.group_repo.get_by_id(group_id)
        if not group:
            raise EntityNotFoundError(f"Configuration group {group_id} not found.")
        return await self.group_repo.update(group, schema)

    async def create_option(self, schema: ProductConfigurationOptionCreate) -> any:
        return await self.option_repo.create(schema)

    async def update_option(self, option_id: int, schema: ProductConfigurationOptionUpdate) -> any:
        opt = await self.option_repo.get_by_id(option_id)
        if not opt:
            raise EntityNotFoundError(f"Configuration option {option_id} not found.")
        return await self.option_repo.update(opt, schema)

    # --- Validation Core Logic ---

    async def validate_configuration(self, request: ValidateConfigurationRequest) -> ValidateConfigurationResponse:
        errors: List[ConfigurationErrorDetail] = []
        warnings: List[str] = []

        # Load active configuration groups
        groups = await self.group_repo.list_by_product_id(request.product_id)
        groups_by_id = {g.id: g for g in groups}
        options_by_id = {opt.id: opt for g in groups for opt in g.options if opt.is_active}

        selected_option_ids = set()
        selected_by_group_id = {g.id: [] for g in groups}
        option_quantities = {}

        # 1. Parse selections and run basic option/quantity boundaries checks
        for sel in request.selections:
            if sel.group_id not in groups_by_id:
                errors.append(ConfigurationErrorDetail(
                    rule_type="INVALID_OPTION",
                    message=f"Group ID {sel.group_id} is not defined or active for this product.",
                    group_id=sel.group_id
                ))
                continue

            group = groups_by_id[sel.group_id]

            for opt_id in sel.option_ids:
                if opt_id not in options_by_id:
                    errors.append(ConfigurationErrorDetail(
                        rule_type="INVALID_OPTION",
                        message=f"Option ID {opt_id} is invalid or inactive.",
                        group_id=sel.group_id,
                        option_id=opt_id
                    ))
                    continue

                option = options_by_id[opt_id]
                if option.group_id != group.id:
                    errors.append(ConfigurationErrorDetail(
                        rule_type="INVALID_OPTION",
                        message=f"Option ID {opt_id} does not belong to configuration group {group.name}.",
                        group_id=sel.group_id,
                        option_id=opt_id
                    ))
                    continue

                selected_option_ids.add(opt_id)
                selected_by_group_id[group.id].append(opt_id)

                # Fetch quantity bounds
                qty = 1
                if sel.quantities and str(opt_id) in sel.quantities:
                    qty = sel.quantities[str(opt_id)]

                if qty < 0:
                    errors.append(ConfigurationErrorDetail(
                        rule_type="QUANTITY",
                        message=f"Quantity for option {option.name} cannot be negative.",
                        group_id=group.id,
                        option_id=opt_id
                    ))
                    continue

                if option.min_quantity is not None and qty < option.min_quantity:
                    errors.append(ConfigurationErrorDetail(
                        rule_type="QUANTITY",
                        message=f"Quantity {qty} for option {option.name} is below minimum ({option.min_quantity}).",
                        group_id=group.id,
                        option_id=opt_id
                    ))
                elif option.max_quantity is not None and qty > option.max_quantity:
                    errors.append(ConfigurationErrorDetail(
                        rule_type="QUANTITY",
                        message=f"Quantity {qty} for option {option.name} is above maximum ({option.max_quantity}).",
                        group_id=group.id,
                        option_id=opt_id
                    ))

                option_quantities[opt_id] = qty

        # 2. Structural checks: Required groups and single vs multi-select constraints
        for group in groups:
            selected_ids = selected_by_group_id[group.id]
            if group.required and len(selected_ids) == 0:
                errors.append(ConfigurationErrorDetail(
                    rule_type="REQUIRED_GROUP",
                    message=f"Configuration group '{group.name}' requires a selection.",
                    group_id=group.id
                ))

            if group.selection_type == "SINGLE_SELECT" and len(selected_ids) > 1:
                errors.append(ConfigurationErrorDetail(
                    rule_type="SINGLE_SELECT",
                    message=f"Configuration group '{group.name}' only allows a single selection.",
                    group_id=group.id
                ))

        # 3. Logical checks: REQUIRES and EXCLUDES rules
        rules = await self.config_repo.get_rules_for_product(request.product_id)
        for rule in rules:
            if rule.source_option_id in selected_option_ids:
                if rule.rule_type == ConfigRuleType.REQUIRES:
                    if rule.target_option_id not in selected_option_ids:
                        errors.append(ConfigurationErrorDetail(
                            rule_type="REQUIRES",
                            message=rule.message,
                            group_id=None,
                            option_id=rule.source_option_id
                        ))
                elif rule.rule_type == ConfigRuleType.EXCLUDES:
                    if rule.target_option_id in selected_option_ids:
                        errors.append(ConfigurationErrorDetail(
                            rule_type="EXCLUDES",
                            message=rule.message,
                            group_id=None,
                            option_id=rule.source_option_id
                        ))

        # Return response object
        return ValidateConfigurationResponse(
            valid=(len(errors) == 0),
            errors=errors,
            warnings=warnings
        )

    # --- Session Workflow ---

    async def get_session(self, session_id: uuid.UUID) -> ConfigurationSession:
        session = await self.session_repo.get_by_id(session_id)
        if not session:
            raise EntityNotFoundError(f"Configuration session {session_id} not found.")
        return session

    async def create_session(self, product_id: int, user_id: Optional[uuid.UUID], selections: List[SelectionItem]) -> ConfigurationSession:
        req = ValidateConfigurationRequest(product_id=product_id, selections=selections)
        val_res = await self.validate_configuration(req)
        
        # Serialize selections to dict list
        serialized_selections = [s.model_dump() for s in selections]
        
        return await self.session_repo.create(
            product_id=product_id,
            user_id=user_id,
            selections=serialized_selections,
            is_valid=val_res.valid
        )

    async def update_session(self, session_id: uuid.UUID, selections: List[SelectionItem]) -> ConfigurationSession:
        session = await self.get_session(session_id)
        req = ValidateConfigurationRequest(product_id=session.product_id, selections=selections)
        val_res = await self.validate_configuration(req)

        serialized_selections = [s.model_dump() for s in selections]
        return await self.session_repo.update(session, serialized_selections, val_res.valid)

    # --- Backward Compatibility Helper (Legacy Quotes Flow) ---
    async def validate_selected_products(self, request: any) -> any:
        # Keep for legacy quotes pipeline signature
        selected_set = set(request.product_ids)
        triggered_rules = await self.config_repo.get_rules_for_products(request.product_ids)
        
        errors = []
        is_valid = True
        for rule in triggered_rules:
            # Replicate simplistic requires/excludes validations if legacy structures match
            pass
        from backend.app.domains.configuration.schemas import ValidateConfigurationResponse
        return ValidateConfigurationResponse(valid=is_valid, errors=errors)

    # --- Phase 2: Product Bundles & Components ---

    async def get_bundle(self, bundle_id: int) -> Bundle:
        bundle = await self.bundle_repo.get_by_id(bundle_id)
        if not bundle:
            raise EntityNotFoundError(f"Bundle {bundle_id} not found.")
        return bundle

    async def create_bundle(self, schema: BundleCreate, user_id: Optional[uuid.UUID] = None) -> Bundle:
        return await self.bundle_repo.create(schema, user_id)

    async def update_bundle(self, bundle_id: int, schema: BundleUpdate, user_id: Optional[uuid.UUID] = None) -> Bundle:
        bundle = await self.get_bundle(bundle_id)
        return await self.bundle_repo.update(bundle, schema, user_id)

    async def add_component(self, bundle_id: int, schema: BundleComponentCreate) -> BundleComponent:
        # Verify product exists in catalog
        from backend.app.domains.catalog.models import Product
        product_exists = (await self.db.execute(select(Product).where(Product.id == schema.product_id))).scalars().first()
        if not product_exists:
            raise EntityNotFoundError(f"Product ID {schema.product_id} not found in catalog.")
        return await self.comp_repo.create(bundle_id, schema)

    async def remove_component(self, component_id: int) -> None:
        comp = await self.comp_repo.get_by_id(component_id)
        if not comp:
            raise EntityNotFoundError(f"Bundle component {component_id} not found.")
        await self.db.delete(comp)

    # --- Bundle Validation ---

    async def validate_bundle(self, request: ValidateBundleRequest) -> ValidateBundleResponse:
        errors: List[BundleErrorDetail] = []
        warnings: List[str] = []

        bundle = await self.bundle_repo.get_by_id(request.bundle_id)
        if not bundle:
            raise EntityNotFoundError(f"Bundle {request.bundle_id} not found.")

        comps_by_id = {c.id: c for c in bundle.components if c.is_active}
        
        # Parse selections
        selections_by_comp_id = {sel.component_id: sel for sel in request.selections}

        # 1. Check required components
        for comp_id, comp in comps_by_id.items():
            sel = selections_by_comp_id.get(comp_id)
            is_selected = sel.selected if sel else False

            if comp.required and not is_selected:
                errors.append(BundleErrorDetail(
                    type="REQUIRED_COMPONENT",
                    message=f"Core Component '{comp.product.name}' is required.",
                    component_id=comp_id
                ))
                continue

            # 2. If selected, run quantity constraints and nested product configuration validation
            if is_selected and sel:
                product = comp.product

                if not product.is_active:
                    errors.append(BundleErrorDetail(
                        type="INACTIVE_PRODUCT",
                        message=f"Product '{product.name}' is inactive and cannot be selected.",
                        component_id=comp_id
                    ))
                    continue

                # Quantity boundary checks
                qty = sel.quantity
                if qty < 0:
                    errors.append(BundleErrorDetail(
                        type="QUANTITY",
                        message=f"Quantity for '{product.name}' cannot be negative.",
                        component_id=comp_id
                    ))
                    continue

                if qty < comp.min_quantity:
                    errors.append(BundleErrorDetail(
                        type="QUANTITY",
                        message=f"Quantity {qty} for '{product.name}' is below bundle minimum ({comp.min_quantity}).",
                        component_id=comp_id
                    ))
                elif comp.max_quantity is not None and qty > comp.max_quantity:
                    errors.append(BundleErrorDetail(
                        type="QUANTITY",
                        message=f"Quantity {qty} for '{product.name}' is above bundle maximum ({comp.max_quantity}).",
                        component_id=comp_id
                    ))

                # Check nested product configurations
                if sel.configuration:
                    val_res = await self.validate_configuration(sel.configuration)
                    if not val_res.valid:
                        for config_err in val_res.errors:
                            errors.append(BundleErrorDetail(
                                type="CONFIGURATION",
                                message=f"Product '{product.name}' configuration error: {config_err.message}",
                                component_id=comp_id
                            ))

        return ValidateBundleResponse(
            valid=(len(errors) == 0),
            errors=errors,
            warnings=warnings
        )

    # --- Bundle Session Flow ---

    async def get_bundle_session(self, session_id: uuid.UUID) -> BundleConfigurationSession:
        sess = await self.bundle_sess_repo.get_by_id(session_id)
        if not sess:
            raise EntityNotFoundError(f"Bundle session {session_id} not found.")
        return sess

    async def create_bundle_session(self, bundle_id: int, user_id: Optional[uuid.UUID], selections: List[ComponentSelectionItem]) -> BundleConfigurationSession:
        req = ValidateBundleRequest(bundle_id=bundle_id, selections=selections)
        val_res = await self.validate_bundle(req)

        serialized = [s.model_dump() for s in selections]
        return await self.bundle_sess_repo.create(
            bundle_id=bundle_id,
            user_id=user_id,
            selections=serialized,
            is_valid=val_res.valid
        )

    async def update_bundle_session(self, session_id: uuid.UUID, selections: List[ComponentSelectionItem]) -> BundleConfigurationSession:
        sess = await self.get_bundle_session(session_id)
        req = ValidateBundleRequest(bundle_id=sess.bundle_id, selections=selections)
        val_res = await self.validate_bundle(req)

        serialized = [s.model_dump() for s in selections]
        return await self.bundle_sess_repo.update(sess, serialized, val_res.valid)

    # --- Phase 3: Versioning & Lifecycle Management ---

    async def get_version(self, version_id: int) -> ConfigurationVersion:
        version = await self.bundle_audit_repo.db.execute(
            select(ConfigurationVersion).where(ConfigurationVersion.id == version_id)
        )
        db_v = version.scalars().first()
        if not db_v:
            raise EntityNotFoundError(f"Version {version_id} not found.")
        return db_v

    async def list_versions(self, entity_type: str, entity_id: int) -> List[ConfigurationVersion]:
        return await self.bundle_sess_repo.db.execute(
            select(ConfigurationVersion)
            .where(
                ConfigurationVersion.entity_type == entity_type,
                ConfigurationVersion.entity_id == entity_id
            )
            .order_by(ConfigurationVersion.version_number.desc())
        ).scalars().all() # type: ignore

    async def create_draft_version(
        self, entity_type: str, entity_id: int, change_summary: Optional[str] = None, user_id: Optional[uuid.UUID] = None
    ) -> ConfigurationVersion:
        repo = ConfigurationVersionRepository(self.db)
        
        # Check if draft already exists
        existing_draft = await repo.get_draft_version(entity_type, entity_id)
        if existing_draft:
            return existing_draft

        # Create new draft
        schema = ConfigurationVersionCreate(entity_type=entity_type, entity_id=entity_id, change_summary=change_summary)
        draft = await repo.create(schema, user_id)

        # Clone current active configuration elements to draft version
        active = await repo.get_active_version(entity_type, entity_id)
        if active:
            if entity_type == "PRODUCT":
                # Clone Groups and Options
                groups = await self.group_repo.list_by_product_id(entity_id, active.id)
                opt_map = {}
                for g in groups:
                    new_g = ProductConfigurationGroup(
                        product_id=entity_id,
                        version_id=draft.id,
                        name=g.name,
                        description=g.description,
                        required=g.required,
                        selection_type=g.selection_type,
                        display_order=g.display_order,
                        is_active=g.is_active
                    )
                    new_g.options = []
                    self.db.add(new_g)
                    await self.db.flush()

                    for opt in g.options:
                        new_opt = ProductConfigurationOption(
                            group_id=new_g.id,
                            name=opt.name,
                            description=opt.description,
                            value=opt.value,
                            min_quantity=opt.min_quantity,
                            max_quantity=opt.max_quantity,
                            display_order=opt.display_order,
                            is_active=opt.is_active
                        )
                        self.db.add(new_opt)
                        await self.db.flush()
                        opt_map[opt.id] = new_opt.id

                # Clone Rules
                rules = await self.config_repo.get_rules_for_product(entity_id, active.id)
                for r in rules:
                    new_r = ConfigurationRule(
                        product_id=entity_id,
                        version_id=draft.id,
                        rule_type=r.rule_type,
                        source_option_id=opt_map[r.source_option_id],
                        target_option_id=opt_map[r.target_option_id],
                        message=r.message,
                        is_active=r.is_active
                    )
                    self.db.add(new_r)
                    await self.db.flush()

            elif entity_type == "BUNDLE":
                # Clone Components
                bundle = await self.get_bundle(entity_id)
                # Ensure we load active version components
                res_comps = await self.db.execute(
                    select(BundleComponent).where(
                        BundleComponent.bundle_id == entity_id,
                        BundleComponent.version_id == active.id
                    )
                )
                comps = res_comps.scalars().all()
                for c in comps:
                    new_c = BundleComponent(
                        bundle_id=entity_id,
                        product_id=c.product_id,
                        version_id=draft.id,
                        required=c.required,
                        default_selected=c.default_selected,
                        min_quantity=c.min_quantity,
                        max_quantity=c.max_quantity,
                        default_quantity=c.default_quantity,
                        display_order=c.display_order,
                        is_active=c.is_active
                    )
                    self.db.add(new_c)
                    await self.db.flush()

        # Log audit log event
        action = "CONFIGURATION_VERSION_CREATED" if entity_type == "PRODUCT" else "BUNDLE_VERSION_CREATED"
        await self.bundle_audit_repo.log(
            user_id=user_id,
            user_role=None, # will be populated by endpoint caller if roles exist
            action=action,
            bundle_id=entity_id if entity_type == "BUNDLE" else None,
            after_value={"version_id": draft.id, "version_number": draft.version_number}
        )
        return draft

    async def activate_version(self, version_id: int, user_id: Optional[uuid.UUID] = None) -> ConfigurationVersion:
        repo = ConfigurationVersionRepository(self.db)
        version = await self.get_version(version_id)
        if version.status != "DRAFT":
            raise DomainValidationError(f"Only DRAFT versions can be activated. Current status is {version.status}.")

        # Perform activation structural validations
        if version.entity_type == "PRODUCT":
            groups = await self.group_repo.list_by_product_id(version.entity_id, version.id)
            if len(groups) == 0:
                raise DomainValidationError("Cannot activate product configuration with 0 groups defined.")
        elif version.entity_type == "BUNDLE":
            res_comps = await self.db.execute(
                select(BundleComponent).where(
                    BundleComponent.bundle_id == version.entity_id,
                    BundleComponent.version_id == version.id
                )
            )
            comps = res_comps.scalars().all()
            if len(comps) == 0:
                raise DomainValidationError("Cannot activate bundle configuration with 0 components defined.")
            if not any(c.required for c in comps):
                raise DomainValidationError("Bundle must have at least one required component.")

        # In a transaction, demote currently ACTIVE version and activate target draft
        active = await repo.get_active_version(version.entity_type, version.entity_id)
        if active:
            active.status = "ARCHIVED"
            self.db.add(active)

        version.status = "ACTIVE"
        self.db.add(version)
        await self.db.flush()
        await self.db.refresh(version)

        # Log audit log event
        action = "CONFIGURATION_VERSION_ACTIVATED" if version.entity_type == "PRODUCT" else "BUNDLE_VERSION_ACTIVATED"
        await self.bundle_audit_repo.log(
            user_id=user_id,
            user_role=None,
            action=action,
            bundle_id=version.entity_id if version.entity_type == "BUNDLE" else None,
            before_value={"archived_version_id": active.id} if active else None,
            after_value={"activated_version_id": version.id}
        )
        return version

    async def archive_version(self, version_id: int, user_id: Optional[uuid.UUID] = None) -> ConfigurationVersion:
        version = await self.get_version(version_id)
        before_status = version.status
        version.status = "ARCHIVED"
        self.db.add(version)
        await self.db.flush()
        await self.db.refresh(version)

        action = "CONFIGURATION_VERSION_ARCHIVED" if version.entity_type == "PRODUCT" else "BUNDLE_VERSION_ARCHIVED"
        await self.bundle_audit_repo.log(
            user_id=user_id,
            user_role=None,
            action=action,
            bundle_id=version.entity_id if version.entity_type == "BUNDLE" else None,
            before_value={"before_status": before_status},
            after_value={"after_status": "ARCHIVED"}
        )
        return version

    async def compare_versions(self, version_a_id: int, version_b_id: int) -> any:
        # Load both versions structure
        ver_a = await self.get_version(version_a_id)
        ver_b = await self.get_version(version_b_id)

        from backend.app.domains.configuration.schemas import VersionComparisonResponse
        res = VersionComparisonResponse(version_a=ver_a.version_number, version_b=ver_b.version_number)

        if ver_a.entity_type == "PRODUCT":
            groups_a = {g.name for g in await self.group_repo.list_by_product_id(ver_a.entity_id, ver_a.id)}
            groups_b = {g.name for g in await self.group_repo.list_by_product_id(ver_b.entity_id, ver_b.id)}
            res.added_groups = list(groups_b - groups_a)
            res.removed_groups = list(groups_a - groups_b)

            options_a = {o.name for g in await self.group_repo.list_by_product_id(ver_a.entity_id, ver_a.id) for o in g.options}
            options_b = {o.name for g in await self.group_repo.list_by_product_id(ver_b.entity_id, ver_b.id) for o in g.options}
            res.added_options = list(options_b - options_a)
            res.removed_options = list(options_a - options_b)

            rules_a = {r.message for r in await self.config_repo.get_rules_for_product(ver_a.entity_id, ver_a.id)}
            rules_b = {r.message for r in await self.config_repo.get_rules_for_product(ver_b.entity_id, ver_b.id)}
            res.added_rules = list(rules_b - rules_a)
            res.removed_rules = list(rules_a - rules_b)

        elif ver_a.entity_type == "BUNDLE":
            res_comps_a = await self.db.execute(select(BundleComponent).where(BundleComponent.bundle_id == ver_a.entity_id, BundleComponent.version_id == ver_a.id))
            comps_a = {c.product.name for c in res_comps_a.scalars().all()}

            res_comps_b = await self.db.execute(select(BundleComponent).where(BundleComponent.bundle_id == ver_b.entity_id, BundleComponent.version_id == ver_b.id))
            comps_b = {c.product.name for c in res_comps_b.scalars().all()}

            res.added_components = list(comps_b - comps_a)
            res.removed_components = list(comps_a - comps_b)

        return res


