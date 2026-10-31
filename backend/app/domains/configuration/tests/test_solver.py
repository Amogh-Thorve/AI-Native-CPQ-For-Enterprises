"""
Solver tests: hand-built models, bundles, random equivalence on bench models, and equivalence with the real service
on bench products in the dev database. The former rules-versus-solver difference (F1, repeated option ids) is fixed
and covered by a normal test; see docs/solver-findings.md.
"""
import asyncio
import random
from collections import Counter

import pytest

from backend.app.core.config import settings
from backend.app.core.database import SessionLocal
from backend.app.domains.configuration.schemas import SelectionItem, ValidateConfigurationRequest
from backend.app.domains.configuration.services import ConfigurationService
from backend.app.domains.configuration.solver import (
    BundleModel, ComponentModel, ComponentSelection, GroupModel, Invalid, OptionModel, ProductModel, RuleModel, Selection,
    Valid, get_solver,
)
from backend.app.domains.configuration.solver.cpsat_solver import CpSatSolver
from backend.app.domains.configuration.solver.rules_validator import RulesValidator
from backend.app.domains.configuration.solver.snapshot import product_snapshot
from bench.catalog_gen import generate, plan
from bench.solver_models import constraint_count, plan_models, random_selection

RULES, CPSAT = RulesValidator(), CpSatSolver()


# ─── Hand-built spine: Plan (single, required), Add-ons (multi), Premium needs Support, Basic excludes Analytics ─────

def spine() -> ProductModel:
    plan_opts = (OptionModel(1, 10, "Basic", None, None, True), OptionModel(2, 10, "Premium", None, None, True))
    addon_opts = (
        OptionModel(3, 11, "Support", 1, 3, True),
        OptionModel(4, 11, "Analytics", None, None, True),
        OptionModel(5, 11, "Retired", None, None, False),
    )
    return ProductModel(
        product_id=1,
        groups=(
            GroupModel(10, "Plan", True, "SINGLE_SELECT", plan_opts),
            GroupModel(11, "Add-ons", False, "MULTI_SELECT", addon_opts),
        ),
        rules=(
            RuleModel("REQUIRES", 2, 3, "Premium requires Support"),
            RuleModel("EXCLUDES", 1, 4, "Basic excludes Analytics"),
        ),
    )


def sel(group, *opts, quantities=None):
    return Selection(group_id=group, option_ids=tuple(opts), quantities=quantities)


def rule_types(result):
    return Counter(c.rule_type for c in result.conflicts) if isinstance(result, Invalid) else Counter()


SPINE_CASES = {
    "valid premium with support": [sel(10, 2), sel(11, 3)],
    "valid basic alone": [sel(10, 1)],
    "premium without support (requires)": [sel(10, 2)],
    "basic with analytics (excludes)": [sel(10, 1), sel(11, 4)],
    "missing required plan": [sel(11, 4)],
    "two plans (single select)": [sel(10, 1, 2)],
    "support above maximum": [sel(10, 2), sel(11, 3, quantities={"3": 5})],
    "support below minimum": [sel(10, 2), sel(11, 3, quantities={"3": 0})],
    "negative quantity": [sel(10, 2), sel(11, 3, quantities={"3": -1})],
    "unknown option": [sel(10, 1), sel(11, 999)],
    "option from another group": [sel(10, 1), sel(11, 1)],
    "inactive option": [sel(10, 2), sel(11, 3), sel(11, 5)],
    "unknown group": [sel(10, 1), sel(99, 3)],
    "two independent violations": [sel(10, 1), sel(11, 4, 3, quantities={"3": 0})],
}


@pytest.mark.parametrize("name", list(SPINE_CASES))
def test_both_implementations_agree_on_spine_cases(name):
    model, selections = spine(), SPINE_CASES[name]
    a, b = RULES.validate(model, selections), CPSAT.validate(model, selections)
    assert isinstance(a, Invalid) == isinstance(b, Invalid), (a, b)
    assert rule_types(a) == rule_types(b), (a, b)


def test_premium_without_support_gives_one_minimal_conflict():
    result = CPSAT.validate(spine(), SPINE_CASES["premium without support (requires)"])
    assert isinstance(result, Invalid)
    assert [(c.rule_type, c.message) for c in result.conflicts] == [("REQUIRES", "Premium requires Support")]


def test_independent_violations_are_all_reported():
    result = CPSAT.validate(spine(), SPINE_CASES["two independent violations"])
    assert rule_types(result) == Counter({"EXCLUDES": 1, "QUANTITY": 1})


def test_valid_selection_is_valid():
    assert isinstance(CPSAT.validate(spine(), SPINE_CASES["valid premium with support"]), Valid)


def test_conflict_messages_are_human_readable():
    result = CPSAT.validate(spine(), SPINE_CASES["two plans (single select)"])
    assert result.conflicts[0].message == "Configuration group 'Plan' only allows a single selection."
    assert result.conflicts[0].group_id == 10


def test_unknown_implementation_name_is_rejected():
    with pytest.raises(ValueError):
        get_solver("gurobi")
    assert get_solver("rules").name == "rules" and get_solver("cpsat").name == "cpsat"


def test_duplicate_option_id_divergence_is_recorded():
    """F1, fixed: a repeated option id is one pick, so both implementations accept it."""
    assert isinstance(RULES.validate(spine(), [sel(10, 1, 1)]), Valid)
    assert isinstance(CPSAT.validate(spine(), [sel(10, 1, 1)]), Valid)
    # A repeated id does not hide a real second pick: 1 and 2 are still two plans. Premium also needs Support, which
    # is not selected here, so REQUIRES fires as well.
    expected = Counter({"SINGLE_SELECT": 1, "REQUIRES": 1})
    assert rule_types(RULES.validate(spine(), [sel(10, 1, 1, 2)])) == expected
    assert rule_types(CPSAT.validate(spine(), [sel(10, 1, 1, 2)])) == expected


# ─── Bundles ────────────────────────────────────────────────────────────────

def bundle() -> BundleModel:
    return BundleModel(bundle_id=1, components=(
        ComponentModel(1, "Core Server", True, True, True, 1, 1),
        ComponentModel(2, "Add-on Disk", True, False, True, 1, 4),
        ComponentModel(3, "Retired Part", True, False, False, 1, 1),
        ComponentModel(4, "Old Product", True, False, True, 1, None),
    ))


BUNDLE_CASES = {
    "valid": [ComponentSelection(1, True, 1), ComponentSelection(2, True, 3)],
    "missing required component": [ComponentSelection(2, True, 1)],
    "required component not selected": [ComponentSelection(1, False, 1)],
    "quantity above maximum": [ComponentSelection(1, True, 1), ComponentSelection(2, True, 9)],
    "quantity below minimum": [ComponentSelection(1, True, 1), ComponentSelection(2, True, 0)],
    "negative quantity": [ComponentSelection(1, True, 1), ComponentSelection(2, True, -2)],
    "inactive product selected": [ComponentSelection(1, True, 1), ComponentSelection(4, True, 1)],
}


@pytest.mark.parametrize("name", list(BUNDLE_CASES))
def test_bundles_agree(name):
    a = RULES.validate_bundle(bundle(), BUNDLE_CASES[name])
    b = CPSAT.validate_bundle(bundle(), BUNDLE_CASES[name])
    assert isinstance(a, Invalid) == isinstance(b, Invalid), (a, b)
    assert rule_types(a) == rule_types(b), (a, b)


def test_bundle_missing_required_component_is_one_minimal_conflict():
    result = CPSAT.validate_bundle(bundle(), BUNDLE_CASES["required component not selected"])
    assert [c.rule_type for c in result.conflicts] == ["REQUIRED_COMPONENT"]


def test_nested_configuration_result_is_wrapped_as_configuration_error():
    def nested_fail(_):
        return Invalid((RULES.validate(spine(), [sel(10, 2)]).conflicts[0],))

    selections = [ComponentSelection(1, True, 1, has_configuration=True), ComponentSelection(2, True, 1)]
    for solver in (RULES, CPSAT):
        result = solver.validate_bundle(bundle(), selections, nested=nested_fail)
        assert [c.rule_type for c in result.conflicts] == ["CONFIGURATION"], solver.name


# ─── Random equivalence on bench models (pure) ──────────────────────────────

def test_random_selections_on_bench_models_agree():
    models = list(plan_models(plan(40, 1234)).values())
    rng = random.Random(7)
    disagreements = []
    runs = 0
    for model in models:
        for _ in range(60):
            selections = random_selection(model, rng)
            a, b = RULES.validate(model, selections), CPSAT.validate(model, selections)
            runs += 1
            if isinstance(a, Invalid) != isinstance(b, Invalid) or rule_types(a) != rule_types(b):
                disagreements.append((model.product_id, selections, a, b))
    assert runs >= 900
    assert not disagreements, disagreements[:3]


def test_constraint_counts_scale_with_plan_size():
    small = sum(constraint_count(m) for m in plan_models(plan(40, 1234)).values())
    large = sum(constraint_count(m) for m in plan_models(plan(300, 1234)).values())
    assert large > 1000 > small


# ─── Equivalence with the real service on bench products in the dev database ───

async def _service_and_snapshots(db_products: int = 40):
    async with SessionLocal() as db:
        report = await generate(db, db_products)
        catalog = plan(db_products, 1234)
        rows = []
        for p in catalog.products:
            if not p.groups:
                continue
            pid = report.product_ids[p.sku]
            snapshot = await product_snapshot(db, pid)
            rows.append((pid, snapshot))
        return rows


def test_rules_port_and_cpsat_match_service_on_bench_products_in_database():
    rows = asyncio.run(_service_and_snapshots())
    rng = random.Random(11)
    mismatches = []

    async def check(pid, snapshot, selections):
        async with SessionLocal() as db:
            service = await ConfigurationService(db).validate_configuration(ValidateConfigurationRequest(
                product_id=pid,
                selections=[SelectionItem(group_id=s.group_id, option_ids=list(s.option_ids), quantities=None) for s in selections],
            ))
            await db.rollback()
        return service

    for pid, snapshot in rows:
        for _ in range(8):
            selections = random_selection(snapshot, rng)
            port, solver = RULES.validate(snapshot, selections), CPSAT.validate(snapshot, selections)
            service = asyncio.run(check(pid, snapshot, selections))
            service_types = Counter(e.rule_type for e in service.errors)
            if service.valid != isinstance(port, Valid) or service_types != rule_types(port):
                mismatches.append(("rules-port vs service", pid, selections))
            if isinstance(solver, Invalid) != isinstance(port, Invalid):
                mismatches.append(("cpsat vs rules-port", pid, selections))
    assert not mismatches, mismatches[:3]


def test_config_flag_routes_service_to_the_solver(monkeypatch):
    rows = asyncio.run(_service_and_snapshots())
    pid, snapshot = rows[0]
    selections = [SelectionItem(group_id=snapshot.groups[0].id, option_ids=[snapshot.groups[0].options[0].id], quantities=None)]

    async def run(flag):
        monkeypatch.setattr(settings, "CONFIG_SOLVER", flag)
        async with SessionLocal() as db:
            out = await ConfigurationService(db).validate_configuration(ValidateConfigurationRequest(product_id=pid, selections=selections))
            await db.rollback()
            return out

    default = asyncio.run(run("rules"))
    via_solver = asyncio.run(run("cpsat"))
    assert default.valid == via_solver.valid
