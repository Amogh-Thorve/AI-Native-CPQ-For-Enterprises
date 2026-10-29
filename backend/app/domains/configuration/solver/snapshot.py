"""
Builds in-memory models from the database using the same repository calls as ConfigurationService, so the snapshot
sees exactly what the service sees (active groups and version, active rules).
"""
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.exceptions import EntityNotFoundError
from backend.app.domains.configuration.services import ConfigurationService
from backend.app.domains.configuration.solver.protocol import (
    BundleModel, ComponentModel, GroupModel, OptionModel, ProductModel, RuleModel,
)


async def product_snapshot(db: AsyncSession, product_id: int) -> ProductModel:
    svc = ConfigurationService(db)
    groups = await svc.group_repo.list_by_product_id(product_id)
    rules = await svc.config_repo.get_rules_for_product(product_id)
    return ProductModel(
        product_id=product_id,
        groups=tuple(
            GroupModel(
                id=g.id, name=g.name, required=bool(g.required), selection_type=g.selection_type,
                options=tuple(
                    OptionModel(
                        id=o.id, group_id=o.group_id, name=o.name, min_quantity=o.min_quantity,
                        max_quantity=o.max_quantity, is_active=bool(o.is_active),
                    ) for o in g.options
                ),
            ) for g in groups
        ),
        rules=tuple(
            RuleModel(
                rule_type=str(r.rule_type), source_option_id=r.source_option_id,
                target_option_id=r.target_option_id, message=r.message,
            ) for r in rules
        ),
    )


async def bundle_snapshot(db: AsyncSession, bundle_id: int) -> BundleModel:
    bundle: Optional[object] = await ConfigurationService(db).bundle_repo.get_by_id(bundle_id)
    if bundle is None:
        raise EntityNotFoundError(f"Bundle {bundle_id} not found.")
    return BundleModel(
        bundle_id=bundle_id,
        components=tuple(
            ComponentModel(
                id=c.id, product_name=c.product.name, product_active=bool(c.product.is_active),
                required=bool(c.required), is_active=bool(c.is_active),
                min_quantity=c.min_quantity, max_quantity=c.max_quantity,
            ) for c in bundle.components
        ),
    )
