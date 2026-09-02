from typing import List, Optional
import uuid
from sqlalchemy import select, or_
from sqlalchemy.orm import selectinload
from sqlalchemy.orm.attributes import set_committed_value
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.domains.configuration.models import (
    ProductConfigurationGroup,
    ProductConfigurationOption,
    ConfigurationRule,
    ConfigurationSession,
    Bundle,
    BundleComponent,
    BundleConfigurationSession,
    BundleAuditLog,
    ConfigurationVersion
)
from backend.app.domains.configuration.schemas import (
    ProductConfigurationGroupCreate, ProductConfigurationGroupUpdate,
    ProductConfigurationOptionCreate, ProductConfigurationOptionUpdate,
    ConfigurationRuleCreate, ConfigurationRuleUpdate,
    ConfigurationSessionCreate, BundleCreate, BundleUpdate,
    BundleComponentCreate, BundleComponentUpdate,
    ConfigurationVersionCreate, ConfigurationVersionUpdate
)
from backend.app.domains.catalog.models import Product

class ProductConfigurationGroupRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, group_id: int) -> Optional[ProductConfigurationGroup]:
        result = await self.db.execute(
            select(ProductConfigurationGroup)
            .where(ProductConfigurationGroup.id == group_id)
            .options(selectinload(ProductConfigurationGroup.options))
        )
        return result.scalars().first()

    async def list_by_product_id(self, product_id: int, version_id: Optional[int] = None) -> List[ProductConfigurationGroup]:
        if not version_id:
            res_v = await self.db.execute(
                select(ConfigurationVersion)
                .where(
                    ConfigurationVersion.entity_type == "PRODUCT",
                    ConfigurationVersion.entity_id == product_id,
                    ConfigurationVersion.status == "ACTIVE"
                )
            )
            act_v = res_v.scalars().first()
            version_id = act_v.id if act_v else None

        query = select(ProductConfigurationGroup).where(
            ProductConfigurationGroup.product_id == product_id,
            ProductConfigurationGroup.is_active == True
        )
        if version_id:
            query = query.where(ProductConfigurationGroup.version_id == version_id)
        else:
            query = query.where(ProductConfigurationGroup.version_id == None)

        result = await self.db.execute(
            query
            .options(selectinload(ProductConfigurationGroup.options))
            .order_by(ProductConfigurationGroup.display_order)
        )
        return list(result.scalars().all())

    async def create(self, schema: ProductConfigurationGroupCreate) -> ProductConfigurationGroup:
        db_group = ProductConfigurationGroup(**schema.model_dump())
        db_group.options = []
        self.db.add(db_group)
        await self.db.flush()
        return db_group

    async def update(self, db_group: ProductConfigurationGroup, schema: ProductConfigurationGroupUpdate) -> ProductConfigurationGroup:
        for field, value in schema.model_dump(exclude_unset=True).items():
            setattr(db_group, field, value)
        self.db.add(db_group)
        await self.db.flush()
        return db_group

class ProductConfigurationOptionRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, option_id: int) -> Optional[ProductConfigurationOption]:
        result = await self.db.execute(
            select(ProductConfigurationOption).where(ProductConfigurationOption.id == option_id)
        )
        return result.scalars().first()

    async def create(self, schema: ProductConfigurationOptionCreate) -> ProductConfigurationOption:
        db_option = ProductConfigurationOption(**schema.model_dump())
        self.db.add(db_option)
        await self.db.flush()
        return db_option

    async def update(self, db_option: ProductConfigurationOption, schema: ProductConfigurationOptionUpdate) -> ProductConfigurationOption:
        for field, value in schema.model_dump(exclude_unset=True).items():
            setattr(db_option, field, value)
        self.db.add(db_option)
        await self.db.flush()
        return db_option

class ConfigurationRuleRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, rule_id: int) -> Optional[ConfigurationRule]:
        result = await self.db.execute(select(ConfigurationRule).where(ConfigurationRule.id == rule_id))
        return result.scalars().first()

    async def list_active(self) -> List[ConfigurationRule]:
        result = await self.db.execute(
            select(ConfigurationRule).where(ConfigurationRule.is_active == True)
        )
        return list(result.scalars().all())

    async def get_rules_for_product(self, product_id: int, version_id: Optional[int] = None) -> List[ConfigurationRule]:
        if not version_id:
            res_v = await self.db.execute(
                select(ConfigurationVersion)
                .where(
                    ConfigurationVersion.entity_type == "PRODUCT",
                    ConfigurationVersion.entity_id == product_id,
                    ConfigurationVersion.status == "ACTIVE"
                )
            )
            act_v = res_v.scalars().first()
            version_id = act_v.id if act_v else None

        query = select(ConfigurationRule).where(
            ConfigurationRule.product_id == product_id,
            ConfigurationRule.is_active == True
        )
        if version_id:
            query = query.where(ConfigurationRule.version_id == version_id)
        else:
            query = query.where(ConfigurationRule.version_id == None)

        result = await self.db.execute(
            query
            .options(
                selectinload(ConfigurationRule.source_option),
                selectinload(ConfigurationRule.target_option)
            )
        )
        return list(result.scalars().all())

    async def get_rules_for_products(self, product_ids: List[int]) -> List[ConfigurationRule]:
        # Backward compatibility helper for legacy code calls
        result = await self.db.execute(
            select(ConfigurationRule)
            .where(
                ConfigurationRule.product_id.in_(product_ids),
                ConfigurationRule.is_active == True
            )
        )
        return list(result.scalars().all())

    async def create(self, schema: ConfigurationRuleCreate) -> ConfigurationRule:
        db_rule = ConfigurationRule(**schema.model_dump())
        self.db.add(db_rule)
        await self.db.flush()
        return db_rule

    async def update(self, db_rule: ConfigurationRule, schema: ConfigurationRuleUpdate) -> ConfigurationRule:
        for field, value in schema.model_dump(exclude_unset=True).items():
            setattr(db_rule, field, value)
        self.db.add(db_rule)
        await self.db.flush()
        return db_rule

class ConfigurationSessionRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, session_id: uuid.UUID) -> Optional[ConfigurationSession]:
        result = await self.db.execute(
            select(ConfigurationSession).where(ConfigurationSession.id == session_id)
        )
        return result.scalars().first()

    async def create(self, product_id: int, user_id: Optional[uuid.UUID], selections: List[dict], is_valid: bool) -> ConfigurationSession:
        db_session = ConfigurationSession(
            product_id=product_id,
            user_id=user_id,
            selections=selections,
            is_valid=is_valid
        )
        self.db.add(db_session)
        await self.db.flush()
        return db_session

    async def update(self, db_session: ConfigurationSession, selections: List[dict], is_valid: bool) -> ConfigurationSession:
        db_session.selections = selections
        db_session.is_valid = is_valid
        self.db.add(db_session)
        await self.db.flush()
        return db_session

class BundleRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, bundle_id: int, version_id: Optional[int] = None) -> Optional[Bundle]:
        if not version_id:
            res_v = await self.db.execute(
                select(ConfigurationVersion)
                .where(
                    ConfigurationVersion.entity_type == "BUNDLE",
                    ConfigurationVersion.entity_id == bundle_id,
                    ConfigurationVersion.status == "ACTIVE"
                )
            )
            act_v = res_v.scalars().first()
            version_id = act_v.id if act_v else None

        res = await self.db.execute(select(Bundle).where(Bundle.id == bundle_id))
        bundle = res.scalars().first()
        if not bundle:
            return None

        # Fetch active or specific version components
        comp_query = select(BundleComponent).where(
            BundleComponent.bundle_id == bundle_id,
            BundleComponent.is_active == True
        )
        if version_id:
            comp_query = comp_query.where(BundleComponent.version_id == version_id)
        else:
            comp_query = comp_query.where(BundleComponent.version_id == None)

        comp_res = await self.db.execute(
            comp_query.options(selectinload(BundleComponent.product).selectinload(Product.category))
        )
        set_committed_value(bundle, "components", list(comp_res.scalars().all()))
        return bundle

    async def list_active(self) -> List[Bundle]:
        # Lists all active bundles. Eager loads core active version components for each.
        result = await self.db.execute(
            select(Bundle).where(Bundle.is_active == True)
        )
        bundles = list(result.scalars().all())
        for b in bundles:
            res_v = await self.db.execute(
                select(ConfigurationVersion)
                .where(
                    ConfigurationVersion.entity_type == "BUNDLE",
                    ConfigurationVersion.entity_id == b.id,
                    ConfigurationVersion.status == "ACTIVE"
                )
            )
            act_v = res_v.scalars().first()
            v_id = act_v.id if act_v else None

            comp_query = select(BundleComponent).where(
                BundleComponent.bundle_id == b.id,
                BundleComponent.is_active == True
            )
            if v_id:
                comp_query = comp_query.where(BundleComponent.version_id == v_id)
            else:
                comp_query = comp_query.where(BundleComponent.version_id == None)

            comp_res = await self.db.execute(
                comp_query.options(selectinload(BundleComponent.product).selectinload(Product.category))
            )
            set_committed_value(b, "components", list(comp_res.scalars().all()))
        return bundles

    async def create(self, schema: BundleCreate, user_id: Optional[uuid.UUID] = None) -> Bundle:
        db_bundle = Bundle(**schema.model_dump())
        if user_id:
            db_bundle.created_by = user_id
            db_bundle.updated_by = user_id
        db_bundle.components = []
        self.db.add(db_bundle)
        await self.db.flush()
        return db_bundle

    async def update(self, db_bundle: Bundle, schema: BundleUpdate, user_id: Optional[uuid.UUID] = None) -> Bundle:
        for field, value in schema.model_dump(exclude_unset=True).items():
            setattr(db_bundle, field, value)
        if user_id:
            db_bundle.updated_by = user_id
        self.db.add(db_bundle)
        await self.db.flush()
        return db_bundle

class BundleComponentRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, component_id: int) -> Optional[BundleComponent]:
        result = await self.db.execute(
            select(BundleComponent)
            .where(BundleComponent.id == component_id)
            .options(selectinload(BundleComponent.product).selectinload(Product.category))
        )
        return result.scalars().first()

    async def create(self, bundle_id: int, schema: BundleComponentCreate) -> BundleComponent:
        db_comp = BundleComponent(bundle_id=bundle_id, **schema.model_dump())
        self.db.add(db_comp)
        await self.db.flush()
        return db_comp

    async def update(self, db_comp: BundleComponent, schema: BundleComponentUpdate) -> BundleComponent:
        for field, value in schema.model_dump(exclude_unset=True).items():
            setattr(db_comp, field, value)
        self.db.add(db_comp)
        await self.db.flush()
        return db_comp

class BundleConfigurationSessionRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, session_id: uuid.UUID) -> Optional[BundleConfigurationSession]:
        result = await self.db.execute(
            select(BundleConfigurationSession).where(BundleConfigurationSession.id == session_id)
        )
        return result.scalars().first()

    async def create(self, bundle_id: int, user_id: Optional[uuid.UUID], selections: List[dict], is_valid: bool) -> BundleConfigurationSession:
        db_sess = BundleConfigurationSession(
            bundle_id=bundle_id,
            user_id=user_id,
            selections=selections,
            is_valid=is_valid
        )
        self.db.add(db_sess)
        await self.db.flush()
        return db_sess

    async def update(self, db_sess: BundleConfigurationSession, selections: List[dict], is_valid: bool) -> BundleConfigurationSession:
        db_sess.selections = selections
        db_sess.is_valid = is_valid
        self.db.add(db_sess)
        await self.db.flush()
        return db_sess

class BundleAuditLogRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def log(
        self,
        user_id: Optional[uuid.UUID],
        user_role: Optional[str],
        action: str,
        bundle_id: Optional[int] = None,
        before_value: Optional[dict] = None,
        after_value: Optional[dict] = None
    ) -> BundleAuditLog:
        log_entry = BundleAuditLog(
            user_id=user_id,
            user_role=user_role,
            action=action,
            bundle_id=bundle_id,
            before_value=before_value,
            after_value=after_value
        )
        self.db.add(log_entry)
        await self.db.flush()
        return log_entry

class ConfigurationVersionRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, version_id: int) -> Optional[ConfigurationVersion]:
        result = await self.db.execute(select(ConfigurationVersion).where(ConfigurationVersion.id == version_id))
        return result.scalars().first()

    async def list_by_entity(self, entity_type: str, entity_id: int) -> List[ConfigurationVersion]:
        result = await self.db.execute(
            select(ConfigurationVersion)
            .where(
                ConfigurationVersion.entity_type == entity_type,
                ConfigurationVersion.entity_id == entity_id
            )
            .order_by(ConfigurationVersion.version_number.desc())
        )
        return list(result.scalars().all())

    async def get_active_version(self, entity_type: str, entity_id: int) -> Optional[ConfigurationVersion]:
        result = await self.db.execute(
            select(ConfigurationVersion)
            .where(
                ConfigurationVersion.entity_type == entity_type,
                ConfigurationVersion.entity_id == entity_id,
                ConfigurationVersion.status == "ACTIVE"
            )
        )
        return result.scalars().first()

    async def get_draft_version(self, entity_type: str, entity_id: int) -> Optional[ConfigurationVersion]:
        result = await self.db.execute(
            select(ConfigurationVersion)
            .where(
                ConfigurationVersion.entity_type == entity_type,
                ConfigurationVersion.entity_id == entity_id,
                ConfigurationVersion.status == "DRAFT"
            )
        )
        return result.scalars().first()

    async def create(self, schema: ConfigurationVersionCreate, user_id: Optional[uuid.UUID] = None) -> ConfigurationVersion:
        # Get next version number
        result = await self.db.execute(
            select(ConfigurationVersion.version_number)
            .where(
                ConfigurationVersion.entity_type == schema.entity_type,
                ConfigurationVersion.entity_id == schema.entity_id
            )
            .order_by(ConfigurationVersion.version_number.desc())
        )
        highest_v = result.scalars().first()
        next_v_num = (highest_v + 1) if highest_v else 1

        db_version = ConfigurationVersion(
            entity_type=schema.entity_type,
            entity_id=schema.entity_id,
            version_number=next_v_num,
            status="DRAFT",
            change_summary=schema.change_summary,
            created_by=user_id
        )
        self.db.add(db_version)
        await self.db.flush()
        await self.db.refresh(db_version)
        return db_version

    async def update(self, db_version: ConfigurationVersion, schema: ConfigurationVersionUpdate) -> ConfigurationVersion:
        for field, value in schema.model_dump(exclude_unset=True).items():
            setattr(db_version, field, value)
        self.db.add(db_version)
        await self.db.flush()
        await self.db.refresh(db_version)
        return db_version

