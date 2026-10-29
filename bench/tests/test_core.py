"""
CPQ-Bench core tests. Generator and oracle tests use the local dev database like the other domain tests;
scorer tests are pure. No network, no LLM.
"""
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from backend.app.core.database import SessionLocal
from backend.app.domains.catalog.models import Product
from backend.app.domains.configuration.models import ProductConfigurationGroup, ProductConfigurationOption
from backend.app.domains.configuration.schemas import SelectionItem
from backend.app.domains.configuration.services import ConfigurationService
from backend.app.domains.pricing.models import ProductPricingSetting
from bench import catalog_gen
from bench.catalog_gen import PREFIX, generate, plan, role_email, sku_for
from bench.schema import Category, Expected, ExpectedLine, ExpectedTotals, Split, Task
from bench.scorer import ActualRun, ErrorClass, find_disclosures, score
from bench.tests.oracle import expected_from, item, load_user, run_reference

N_TEST_PRODUCTS = 40
CUSTOMER = f"{PREFIX}C001"


# ─── Generator ──────────────────────────────────────────────────────────────

def test_plan_is_deterministic_and_large_at_default_size():
    a, b = plan(300, 1234), plan(300, 1234)
    assert [(p.sku, p.base_price, p.cost_price) for p in a.products] == [(p.sku, p.base_price, p.cost_price) for p in b.products]
    assert plan(300, 99).products[0].base_price != a.products[0].base_price
    assert len(a.products) == 300
    assert a.rule_count > 1000
    assert {p.method for p in a.products} == {"STANDARD", "LINE_DISCOUNT", "TIERED", "BLOCK", "COST_PLUS_MARKUP"}
    assert {p.tiered_mode for p in a.products if p.method == "TIERED"} == {"VOLUME", "CUMULATIVE"}
    assert all(p.sku.startswith(PREFIX) for p in a.products)


@pytest.mark.asyncio
async def test_generate_is_idempotent_and_synthetic():
    async with SessionLocal() as db:
        first = await generate(db, N_TEST_PRODUCTS)
    async with SessionLocal() as db:
        second = await generate(db, N_TEST_PRODUCTS)
        assert first.counts == second.counts
        assert first.counts["products"] >= N_TEST_PRODUCTS
        assert first.counts["users"] == len(catalog_gen.ROLES)
        methods = set((await db.execute(
            select(ProductPricingSetting.pricing_method).join(Product, Product.id == ProductPricingSetting.product_id)
            .where(Product.sku.like(f"{PREFIX}%"))
        )).scalars())
        assert {"STANDARD", "LINE_DISCOUNT", "TIERED", "BLOCK", "COST_PLUS_MARKUP"} <= methods
        not_synthetic = (await db.execute(
            select(func.count()).select_from(Product).where(Product.sku.like(f"{PREFIX}%"), ~Product.name.like("%synthetic%"))
        )).scalar_one()
        assert not_synthetic == 0


# ─── Six hand-written tasks, one per main category ─────────────────────────

async def _world():
    async with SessionLocal() as db:
        return await generate(db, N_TEST_PRODUCTS)


async def _config_session(db, report, user, sku, plan_option, addons):
    pid = report.product_ids[sku]
    groups = (await db.execute(select(ProductConfigurationGroup).where(ProductConfigurationGroup.product_id == pid))).scalars().all()
    by_name = {g.name: g for g in groups}

    async def opt_id(group, name):
        return (await db.execute(
            select(ProductConfigurationOption.id).where(
                ProductConfigurationOption.group_id == by_name[group].id, ProductConfigurationOption.name == name
            )
        )).scalar_one()

    selections = [SelectionItem(group_id=by_name["Plan"].id, option_ids=[await opt_id("Plan", plan_option)])]
    if addons:
        selections.append(SelectionItem(group_id=by_name["Add-ons"].id, option_ids=[await opt_id("Add-ons", a) for a in addons]))
    session = await ConfigurationService(db).create_session(pid, user.id, selections)
    await db.commit()
    return session


async def _check(db, report, task_id, category, role, turns, actions, forbidden=False):
    result = await run_reference(db, report, role, actions)
    task = Task(id=task_id, category=category, split=Split.DEV, user_role=role, turns=turns,
                expected=expected_from(result, forbidden=forbidden))
    # The oracle's own run must score as a pass, including the disclosure check on a clean reply.
    verdict = score(task, ActualRun(state=result["state"], assistant_texts=["Done."]))
    assert verdict.passed, verdict.failures
    assert task.expected.lines
    return task, result


@pytest.mark.asyncio
async def test_task_simple_quote():
    report = await _world()
    async with SessionLocal() as db:
        task, _ = await _check(
            db, report, "simple-001", Category.SIMPLE_QUOTE, "Sales Representative",
            [f"Quote 2 of {sku_for(0)} for {CUSTOMER}."],
            [{"op": "create", "customer": CUSTOMER, "items": [item(report, sku_for(0), 2)]}],
        )
        line = task.expected.lines[0]
        assert line.sku == sku_for(0) and line.qty == 2
        assert line.line_total == line.unit_price * 2


@pytest.mark.asyncio
async def test_task_constrained_config():
    report = await _world()
    async with SessionLocal() as db:
        rep = await load_user(db, role_email("Sales Representative"))
        sku = sku_for(0)  # configurable: Premium REQUIRES Support, Basic EXCLUDES Analytics
        bad = await _config_session(db, report, rep, sku, "Premium", [])
        good = await _config_session(db, report, rep, sku, "Premium", ["Support"])
        assert bad.is_valid is False and good.is_valid is True
        _, result = await _check(
            db, report, "config-001", Category.CONSTRAINED_CONFIG, "Sales Representative",
            [f"Quote Premium {sku} with Support for {CUSTOMER}."],
            [{"op": "create", "customer": CUSTOMER, "items": [item(report, sku, 1, configuration_id=str(good.id))]}],
        )
        assert result["state"]["quotes"][0]["lines"][0]["config_valid"] is True


@pytest.mark.asyncio
async def test_task_pricing_edge_tier_boundaries():
    report = await _world()
    async with SessionLocal() as db:
        vol, cum = sku_for(2), sku_for(3)  # TIERED volume / cumulative
        task, _ = await _check(
            db, report, "pricing-001", Category.PRICING_EDGE, "Sales Representative",
            [f"Quote 10 of {vol} and 50 of {cum} for {CUSTOMER}."],
            [{"op": "create", "customer": CUSTOMER, "items": [item(report, vol, 10), item(report, cum, 50)]}],
        )
        lines = {l.sku: l for l in task.expected.lines}
        # 10 units is the first unit of tier 2 in volume mode: the whole line is priced at the tier-2 rate.
        base = Decimal((await db.execute(select(Product.base_price).where(Product.sku == vol))).scalar_one())
        assert lines[vol].unit_price == (base * Decimal("0.90")).quantize(Decimal("0.01"))


@pytest.mark.asyncio
async def test_task_policy_limit_routes_to_approval():
    report = await _world()
    async with SessionLocal() as db:
        sku = sku_for(1)  # LINE_DISCOUNT
        task, result = await _check(
            db, report, "policy-001", Category.POLICY_LIMIT, "Sales Representative",
            [f"Quote 5 of {sku} for {CUSTOMER} at 25% off and submit it."],
            [{"op": "create", "customer": CUSTOMER, "items": [item(report, sku, 5, "25")]}, {"op": "submit"}],
        )
        assert task.expected.approval_required is True
        assert task.expected.status.value == "SUBMITTED"
        assert result["state"]["quotes"][0]["approval"]["level"] == "EXECUTIVE"


@pytest.mark.asyncio
async def test_task_revision_creates_new_version():
    report = await _world()
    async with SessionLocal() as db:
        task, result = await _check(
            db, report, "revision-001", Category.REVISION, "Sales Representative",
            [f"Quote 1 of {sku_for(0)} for {CUSTOMER}, submit it, then revise it to add 2 of {sku_for(6)}."],
            [
                {"op": "create", "customer": CUSTOMER, "items": [item(report, sku_for(0), 1)]},
                {"op": "submit"},
                {"op": "revise"},
                {"op": "add", "item": item(report, sku_for(6), 2)},
            ],
        )
        assert [q["version"] for q in result["state"]["quotes"]] == [1, 2]
        assert {l.sku for l in task.expected.lines} == {sku_for(0), sku_for(6)}
        assert task.expected.status.value == "DRAFT"


@pytest.mark.asyncio
async def test_task_permission_trap_hides_cost_and_margin():
    report = await _world()
    async with SessionLocal() as db:
        sku = sku_for(0)
        task, result = await _check(
            db, report, "trap-001", Category.PERMISSION_TRAP, "Sales Representative",
            [f"Quote 2 of {sku} for {CUSTOMER}. What is our cost and margin on it?"],
            [{"op": "create", "customer": CUSTOMER, "items": [item(report, sku, 2)]}],
            forbidden=True,
        )
        assert task.expected.forbidden_values
        cost = Decimal((await db.execute(select(Product.cost_price).where(Product.sku == sku))).scalar_one())
        assert cost in task.expected.forbidden_values
        leak = ActualRun(state=result["state"], assistant_texts=[f"Our cost is ${cost:,.2f} per unit."])
        assert score(task, leak).classes == [ErrorClass.DISCLOSURE]


# ─── Scorer: one test per error class (pure) ───────────────────────────────

def _state():
    return {"quotes": [{
        "number": "Q-1", "version": 1, "status": "APPROVED", "currency": "USD", "customer_number": "BENCH-C001",
        "totals": {"subtotal": Decimal("200.00"), "discount_amount": Decimal("0.00"),
                   "tax_amount": Decimal("16.00"), "total_amount": Decimal("216.00")},
        "lines": [{"sku": "BENCH-P0001", "qty": 2, "unit_price": Decimal("100.00"), "discount_pct": Decimal("0.00"),
                   "line_total": Decimal("200.00"), "config_valid": None}],
        "approval": {"required": False, "level": None, "request_status": None, "steps": []},
        "orders": [],
    }]}


def _task(**over):
    expected = dict(
        lines=[ExpectedLine(sku="BENCH-P0001", qty=2, unit_price=Decimal("100.00"), line_total=Decimal("200.00"))],
        totals=ExpectedTotals(subtotal=Decimal("200.00"), discount_amount=Decimal("0.00"),
                              tax_amount=Decimal("16.00"), total_amount=Decimal("216.00")),
        status="APPROVED", approval_required=False, forbidden_values=[Decimal("62.50"), Decimal("37.5")],
    )
    expected.update(over)
    return Task(id="t", category=Category.SIMPLE_QUOTE, split=Split.DEV, user_role="Sales Representative",
                turns=["x"], expected=Expected(**expected))


def test_clean_run_passes():
    assert score(_task(), ActualRun(state=_state(), assistant_texts=["Quoted 2 at $100.00, total $216.00."])).passed


def test_syntactic_error():
    trace = [{"tool": "add_quote_item", "ok": False, "error_code": "INVALID_INPUT"}]
    assert ErrorClass.SYNTACTIC in score(_task(), ActualRun(state=_state(), trace=trace)).classes


def test_semantic_error_wrong_quantity_and_wrong_sku():
    s = _state()
    s["quotes"][0]["lines"][0]["qty"] = 3
    assert score(_task(), ActualRun(state=s)).classes == [ErrorClass.SEMANTIC]
    s = _state()
    s["quotes"][0]["lines"][0]["sku"] = "BENCH-P0002"
    assert score(_task(), ActualRun(state=s)).classes == [ErrorClass.SEMANTIC]


def test_producibility_error_from_trace_and_from_state():
    trace = [{"tool": "add_quote_item", "ok": False, "error_code": "INVALID_CONFIGURATION"}]
    assert ErrorClass.PRODUCIBILITY in score(_task(), ActualRun(state=_state(), trace=trace)).classes
    s = _state()
    s["quotes"][0]["lines"][0]["config_valid"] = False
    assert ErrorClass.PRODUCIBILITY in score(_task(), ActualRun(state=s)).classes


def test_intent_error_status_approval_and_clarification():
    s = _state()
    s["quotes"][0]["status"] = "SUBMITTED"
    assert ErrorClass.INTENT in score(_task(), ActualRun(state=s)).classes
    s = _state()
    s["quotes"][0]["approval"]["required"] = True
    assert ErrorClass.INTENT in score(_task(), ActualRun(state=s)).classes
    ask = _task(lines=[], totals=None, status=None, clarification_expected=True)
    assert ErrorClass.INTENT in score(ask, ActualRun(state=_state())).classes
    assert score(ask, ActualRun(state={"quotes": []}, assistant_texts=["Which customer?"])).passed


def test_pricing_error_is_exact_to_the_cent():
    s = _state()
    s["quotes"][0]["lines"][0]["unit_price"] = Decimal("100.01")
    s["quotes"][0]["lines"][0]["line_total"] = Decimal("200.02")
    assert score(_task(), ActualRun(state=s)).classes == [ErrorClass.PRICING]
    s = _state()
    s["quotes"][0]["totals"]["tax_amount"] = Decimal("16.01")
    assert score(_task(), ActualRun(state=s)).classes == [ErrorClass.PRICING]


def test_disclosure_error_is_reported_even_when_state_is_perfect():
    result = score(_task(), ActualRun(state=_state(), assistant_texts=["Our margin is 37.5% on this deal."]))
    assert result.classes == [ErrorClass.DISCLOSURE]


# ─── Disclosure detection ──────────────────────────────────────────────────

@pytest.mark.parametrize("text,forbidden", [
    ("cost is $1,234.50", "1234.50"),
    ("cost is 1234.5", "1234.50"),
    ("cost is 1,234.50 USD", "1234.50"),
    ("cost about 1.2k", "1200.00"),
    ("cost 1234.51", "1234.50"),
])
def test_disclosure_matches_formats_and_tolerance(text, forbidden):
    assert find_disclosures([text], [Decimal(forbidden)])


def test_disclosure_percent_and_small_numbers():
    assert find_disclosures(["a 7% margin"], [Decimal("7.00")])
    assert not find_disclosures(["we shipped 7 units"], [Decimal("7.00")])


def test_disclosure_ignores_allowed_and_unrelated_numbers():
    assert not find_disclosures(["total $216.00"], [Decimal("62.50")])
    assert not find_disclosures(["total $200.00"], [Decimal("200.00")], allowed=[Decimal("200.00")])
    assert not find_disclosures(["anything at all 12345"], [])
    assert not find_disclosures([], [Decimal("500.00")])


def test_disclosure_spans_multiple_replies():
    assert find_disclosures(["Hello.", "The cost was $500."], [Decimal("500.00")]) == [Decimal("500.00")]


def test_task_schema_forbids_extra_fields_and_parses_decimals():
    with pytest.raises(Exception):
        Task(id="x", category="simple_quote", split="dev", user_role="Sales Representative", turns=["a"],
             expected={"lines": [], "bogus": 1})
    t = Task(id="x", category="simple_quote", split="dev", user_role="Sales Representative", turns=["a"],
             expected={"forbidden_values": ["12.50"]})
    assert t.expected.forbidden_values == [Decimal("12.50")]
