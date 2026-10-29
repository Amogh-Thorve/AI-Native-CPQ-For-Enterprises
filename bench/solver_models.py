"""
In-memory configuration models built from bench/catalog_gen.plan(). No database: used by the solver equivalence tests
and by bench/solver_bench.py, so only the solver is timed.
"""
import random
from typing import Dict, List, Tuple

from backend.app.domains.configuration.solver.protocol import (
    GroupModel, OptionModel, ProductModel, RuleModel, Selection,
)
from bench.catalog_gen import Plan

MISSING_OPTION_ID = 10**9
VALID_SPINE = [("Basic", []), ("Standard", []), ("Standard", ["Analytics"]), ("Premium", ["Support"]), ("Premium", ["Support", "Backup"])]


def plan_models(plan: Plan) -> Dict[str, ProductModel]:
    """One ProductModel per configurable product, keyed by SKU. Ids are unique across the whole plan."""
    models: Dict[str, ProductModel] = {}
    next_group, next_option, next_product = 1, 1, 1
    for p in plan.products:
        if not p.groups:
            continue
        group_ids: List[int] = []
        option_ids: Dict[Tuple[int, int], int] = {}
        groups = []
        for gi, g in enumerate(p.groups):
            gid = next_group
            next_group += 1
            group_ids.append(gid)
            options = []
            for oi, name in enumerate(g.options):
                oid = next_option
                next_option += 1
                option_ids[(gi, oi)] = oid
                options.append(OptionModel(id=oid, group_id=gid, name=name, min_quantity=None, max_quantity=None, is_active=True))
            groups.append(GroupModel(id=gid, name=g.name, required=g.required, selection_type=g.selection_type, options=tuple(options)))
        rules = tuple(
            RuleModel(rule_type=t, source_option_id=option_ids[s], target_option_id=option_ids[d], message=f"{t} rule")
            for t, s, d in p.rules
        )
        models[p.sku] = ProductModel(product_id=next_product, groups=tuple(groups), rules=rules)
        next_product += 1
    return models


def constraint_count(model: ProductModel) -> int:
    """Rules plus one per required group and one per single-select group: what the solver encodes."""
    return len(model.rules) + sum(1 for g in model.groups if g.required) + sum(1 for g in model.groups if g.selection_type == "SINGLE_SELECT")


def random_selection(model: ProductModel, rng: random.Random, valid_bias: float = 0.5) -> List[Selection]:
    """Mostly random picks, with a share of spine-shaped picks so valid configurations are common enough to test."""
    if rng.random() < valid_bias and len(model.groups) >= 3:
        plan_name, addons = rng.choice(VALID_SPINE)
        selections = []
        by_name = {g.name: g for g in model.groups}
        plan_group = by_name.get("Plan")
        if plan_group:
            pick = next(o for o in plan_group.options if o.name == plan_name)
            selections.append(Selection(group_id=plan_group.id, option_ids=(pick.id,)))
        addon_group = by_name.get("Add-ons")
        if addon_group and addons:
            ids = tuple(o.id for o in addon_group.options if o.name in addons)
            selections.append(Selection(group_id=addon_group.id, option_ids=ids))
        return selections
    selections = []
    for g in model.groups:
        if rng.random() < 0.3:
            continue
        k = 1 if g.selection_type == "SINGLE_SELECT" else rng.randint(0, len(g.options))
        chosen = rng.sample(list(g.options), min(k, len(g.options)))
        ids = [o.id for o in chosen]
        if rng.random() < 0.05:
            ids.append(MISSING_OPTION_ID)
        selections.append(Selection(group_id=g.id, option_ids=tuple(ids)))
    return selections
