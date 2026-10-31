"""
Pure port of ConfigurationService.validate_configuration and validate_bundle (services.py).

Behaviour is copied on purpose, including quirks, so the port can be compared with both the service and the solver.
Quirks kept as they are: MULTI_SELECT groups are never capped; REQUIRES is checked from the source side only.
Do not fix them here. Record them in docs/solver-findings.md. A repeated option id is one pick (F1, now fixed).
"""
from typing import List, Optional, Sequence, Set

from backend.app.domains.configuration.solver.protocol import (
    BundleModel, Conflict, ComponentSelection, Invalid, NestedCheck, ProductModel, Result, Selection, result_from,
)


def validate_selections(model: ProductModel, selections: Sequence[Selection]) -> List[Conflict]:
    errors: List[Conflict] = []
    groups = list(model.groups)
    groups_by_id = {g.id: g for g in groups}
    options_by_id = {o.id: o for g in groups for o in g.options if o.is_active}

    selected_option_ids: Set[int] = set()
    selected_by_group_id = {g.id: [] for g in groups}

    # 1. Parse selections: membership, group ownership and quantity bounds.
    for sel in selections:
        if sel.group_id not in groups_by_id:
            errors.append(Conflict("INVALID_OPTION", f"Group ID {sel.group_id} is not defined or active for this product.", group_id=sel.group_id))
            continue
        group = groups_by_id[sel.group_id]

        for opt_id in sel.option_ids:
            if opt_id not in options_by_id:
                errors.append(Conflict("INVALID_OPTION", f"Option ID {opt_id} is invalid or inactive.", group_id=sel.group_id, option_id=opt_id))
                continue
            option = options_by_id[opt_id]
            if option.group_id != group.id:
                errors.append(Conflict("INVALID_OPTION", f"Option ID {opt_id} does not belong to configuration group {group.name}.", group_id=sel.group_id, option_id=opt_id))
                continue

            selected_option_ids.add(opt_id)
            # A repeated id is one pick (F1 in docs/solver-findings.md). Keep the first occurrence's place.
            if opt_id not in selected_by_group_id[group.id]:
                selected_by_group_id[group.id].append(opt_id)

            qty = 1
            if sel.quantities and str(opt_id) in sel.quantities:
                qty = sel.quantities[str(opt_id)]

            if qty < 0:
                errors.append(Conflict("QUANTITY", f"Quantity for option {option.name} cannot be negative.", group_id=group.id, option_id=opt_id))
                continue
            if option.min_quantity is not None and qty < option.min_quantity:
                errors.append(Conflict("QUANTITY", f"Quantity {qty} for option {option.name} is below minimum ({option.min_quantity}).", group_id=group.id, option_id=opt_id))
            elif option.max_quantity is not None and qty > option.max_quantity:
                errors.append(Conflict("QUANTITY", f"Quantity {qty} for option {option.name} is above maximum ({option.max_quantity}).", group_id=group.id, option_id=opt_id))

    # 2. Structure: required groups and single-select caps.
    for group in groups:
        chosen = selected_by_group_id[group.id]
        if group.required and len(chosen) == 0:
            errors.append(Conflict("REQUIRED_GROUP", f"Configuration group '{group.name}' requires a selection.", group_id=group.id))
        if group.selection_type == "SINGLE_SELECT" and len(chosen) > 1:
            errors.append(Conflict("SINGLE_SELECT", f"Configuration group '{group.name}' only allows a single selection.", group_id=group.id))

    # 3. Logic: REQUIRES and EXCLUDES, checked from the source side.
    for rule in model.rules:
        if rule.source_option_id not in selected_option_ids:
            continue
        if rule.rule_type == "REQUIRES" and rule.target_option_id not in selected_option_ids:
            errors.append(Conflict("REQUIRES", rule.message, option_id=rule.source_option_id))
        elif rule.rule_type == "EXCLUDES" and rule.target_option_id in selected_option_ids:
            errors.append(Conflict("EXCLUDES", rule.message, option_id=rule.source_option_id))
    return errors


def validate_bundle_components(
    model: BundleModel, selections: Sequence[ComponentSelection], nested: Optional[NestedCheck] = None,
) -> List[Conflict]:
    errors: List[Conflict] = []
    comps = [c for c in model.components if c.is_active]
    by_id = {s.component_id: s for s in selections}

    for comp in comps:
        sel = by_id.get(comp.id)
        is_selected = bool(sel and sel.selected)

        if comp.required and not is_selected:
            errors.append(Conflict("REQUIRED_COMPONENT", f"Core Component '{comp.product_name}' is required.", option_id=comp.id))
            continue

        if is_selected and sel:
            if not comp.product_active:
                errors.append(Conflict("INACTIVE_PRODUCT", f"Product '{comp.product_name}' is inactive and cannot be selected.", option_id=comp.id))
                continue

            qty = sel.quantity
            if qty < 0:
                errors.append(Conflict("QUANTITY", f"Quantity for '{comp.product_name}' cannot be negative.", option_id=comp.id))
                continue
            if qty < comp.min_quantity:
                errors.append(Conflict("QUANTITY", f"Quantity {qty} for '{comp.product_name}' is below bundle minimum ({comp.min_quantity}).", option_id=comp.id))
            elif comp.max_quantity is not None and qty > comp.max_quantity:
                errors.append(Conflict("QUANTITY", f"Quantity {qty} for '{comp.product_name}' is above bundle maximum ({comp.max_quantity}).", option_id=comp.id))

            if sel.has_configuration and nested is not None:
                nested_result = nested(sel)
                if isinstance(nested_result, Invalid):
                    for conflict in nested_result.conflicts:
                        errors.append(Conflict("CONFIGURATION", f"Product '{comp.product_name}' configuration error: {conflict.message}", option_id=comp.id))
    return errors


class RulesValidator:
    name = "rules"

    def validate(self, model: ProductModel, selections: Sequence[Selection]) -> Result:
        return result_from(validate_selections(model, selections))

    def validate_bundle(self, model: BundleModel, selections: Sequence[ComponentSelection], nested: Optional[NestedCheck] = None) -> Result:
        return result_from(validate_bundle_components(model, selections, nested))
