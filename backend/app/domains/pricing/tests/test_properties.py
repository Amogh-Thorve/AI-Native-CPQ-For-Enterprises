"""
Property-based invariants for the pricing engine (hypothesis).

Pure properties call PricingEngine.calculate, the domain calculate path, with Decimal strategies. Properties that
depend on permissions, overrides and audit rows call PricingApplicationService.calculate_price, the same path the API
uses, against the local dev database. Those run inside one session that is rolled back, so nothing is left behind.
"""
import asyncio
import uuid
from decimal import Decimal
from types import SimpleNamespace

import pytest
from hypothesis import HealthCheck, given, settings, strategies as st
from sqlalchemy import func, select

from backend.app.core.database import SessionLocal
from backend.app.core.exceptions import DomainValidationError
from backend.app.domains.catalog.models import Product
from backend.app.domains.pricing.api.schemas import CalculatePriceRequest
from backend.app.domains.pricing.application.services import PricingApplicationService
from backend.app.domains.pricing.domain.engine import PricingEngine
from backend.app.domains.pricing.domain.enums import PricingMethod, TieredMode
from backend.app.domains.pricing.domain.strategies import validate_tiers
from backend.app.domains.pricing.models import PricingAuditLog

from fastapi import HTTPException

CENT = Decimal("0.01")
MONEY_FIELDS = (
    "base_unit_price", "discount_percent", "discount_amount", "final_unit_price", "total_price",
    "unit_cost", "total_cost", "margin_amount", "margin_percentage",
)

# Prices and costs with two places (what the catalog stores) and with more (which the engine must round).
MONEY_2DP = st.decimals(min_value=Decimal("0"), max_value=Decimal("100000"), places=2, allow_nan=False, allow_infinity=False)
MONEY_ANY = st.decimals(min_value=Decimal("0"), max_value=Decimal("100000"), allow_nan=False, allow_infinity=False)
PERCENT = st.decimals(min_value=Decimal("0"), max_value=Decimal("100"), places=2, allow_nan=False, allow_infinity=False)
QTY = st.integers(min_value=1, max_value=5000)
PURE = settings(max_examples=200, deadline=None, suppress_health_check=[HealthCheck.too_slow])
DB = settings(max_examples=12, deadline=None, suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture])


def calc(method, base, qty, **kwargs):
    return PricingEngine.calculate(
        product_id=1, sku="SKU", name="Name", billing_type="MRC", currency="USD",
        base_price=base, quantity=qty, pricing_method=method, **kwargs,
    )


def tier(min_q, max_q, price, mode=None):
    return SimpleNamespace(min_quantity=min_q, max_quantity=max_q, price=price, display_order=1, is_active=True, tiered_mode=mode)


@st.composite
def contiguous_tiers(draw):
    """Tiers starting at 1, contiguous, with only the last one unlimited. Prices are distinct so a wrong tier shows."""
    extra = draw(st.lists(st.integers(min_value=2, max_value=300), unique=True, max_size=4))
    mins = [1] + sorted(extra)
    prices = [draw(st.decimals(min_value=Decimal("1"), max_value=Decimal("5000"), places=2, allow_nan=False, allow_infinity=False)) for _ in mins]
    tiers = []
    for i, m in enumerate(mins):
        top = mins[i + 1] - 1 if i + 1 < len(mins) else None
        tiers.append(tier(m, top, prices[i]))
    return tiers


def brute_tier(tiers, q):
    hits = [t for t in tiers if t.min_quantity <= q and (t.max_quantity is None or q <= t.max_quantity)]
    assert len(hits) == 1, f"quantity {q} belongs to {len(hits)} tiers"
    return hits[0]


# ─── Quantisation and sign ──────────────────────────────────────────────────

@PURE
@given(base=MONEY_ANY, qty=QTY, pct=PERCENT)
def test_outputs_are_quantised_to_two_places(base, qty, pct):
    for result in (
        calc(PricingMethod.STANDARD, base, qty, cost_price=base / 2),
        calc(PricingMethod.LINE_DISCOUNT, base, qty, discount_percent=pct, cost_price=base / 3),
    ):
        for field in MONEY_FIELDS:
            value = result[field]
            if value is not None:
                assert value.as_tuple().exponent == -2, (field, value)


@PURE
@given(base=MONEY_ANY, qty=QTY, pct=PERCENT, cost=MONEY_ANY)
def test_prices_and_totals_are_never_negative(base, qty, pct, cost):
    for result in (
        calc(PricingMethod.STANDARD, base, qty),
        calc(PricingMethod.LINE_DISCOUNT, base, qty, discount_percent=pct),
        calc(PricingMethod.COST_PLUS_MARKUP, base, qty, cost_price=cost, markup_percent=Decimal("25")),
    ):
        assert result["base_unit_price"] >= 0
        assert result["final_unit_price"] >= 0
        assert result["total_price"] >= 0


# ─── STANDARD and LINE_DISCOUNT ─────────────────────────────────────────────

@PURE
@given(base=MONEY_2DP, qty=QTY)
def test_standard_total_is_unit_price_times_quantity(base, qty):
    result = calc(PricingMethod.STANDARD, base, qty)
    assert result["total_price"] == result["base_unit_price"] * qty
    assert result["final_unit_price"] == result["base_unit_price"]


@PURE
@given(base=MONEY_2DP, qty=QTY)
def test_line_discount_zero_percent_equals_standard(base, qty):
    standard = calc(PricingMethod.STANDARD, base, qty)
    zero = calc(PricingMethod.LINE_DISCOUNT, base, qty, discount_percent=Decimal("0"))
    for field in ("base_unit_price", "final_unit_price", "total_price", "discount_amount"):
        assert zero[field] == standard[field], field


@PURE
@given(base=MONEY_2DP, qty=QTY)
def test_line_discount_hundred_percent_gives_zero(base, qty):
    result = calc(PricingMethod.LINE_DISCOUNT, base, qty, discount_percent=Decimal("100"))
    assert result["final_unit_price"] == 0
    assert result["total_price"] == 0


@PURE
@given(base=MONEY_2DP, qty=QTY, bad=st.one_of(
    st.decimals(min_value=Decimal("-1000"), max_value=Decimal("-0.01"), places=2, allow_nan=False),
    st.decimals(min_value=Decimal("100.01"), max_value=Decimal("1000"), places=2, allow_nan=False),
))
def test_line_discount_outside_zero_to_hundred_is_rejected(base, qty, bad):
    with pytest.raises(DomainValidationError):
        calc(PricingMethod.LINE_DISCOUNT, base, qty, discount_percent=bad)


# ─── COST_PLUS_MARKUP ───────────────────────────────────────────────────────

@PURE
@given(cost=MONEY_2DP, qty=QTY)
def test_cost_plus_zero_markup_equals_cost(cost, qty):
    result = calc(PricingMethod.COST_PLUS_MARKUP, cost, qty, cost_price=cost, markup_percent=Decimal("0"))
    assert result["final_unit_price"] == cost.quantize(CENT)
    assert result["total_price"] == cost.quantize(CENT) * qty


@PURE
@given(cost=MONEY_2DP, qty=QTY, markup=PERCENT, negative=st.decimals(min_value=Decimal("-1000"), max_value=Decimal("-0.01"), places=2, allow_nan=False))
def test_cost_plus_rejects_negative_cost_or_markup(cost, qty, markup, negative):
    with pytest.raises(DomainValidationError):
        calc(PricingMethod.COST_PLUS_MARKUP, cost, qty, cost_price=negative, markup_percent=markup)
    with pytest.raises(DomainValidationError):
        calc(PricingMethod.COST_PLUS_MARKUP, cost, qty, cost_price=cost, markup_percent=negative)


# ─── Tiers ──────────────────────────────────────────────────────────────────

@PURE
@given(tiers=contiguous_tiers())
def test_valid_tiers_are_accepted(tiers):
    assert [t.min_quantity for t in validate_tiers(tiers)] == [t.min_quantity for t in tiers]


@PURE
@given(tiers=contiguous_tiers().filter(lambda t: len(t) >= 2), shift=st.sampled_from([-1, 1]))
def test_gap_or_overlap_between_tiers_is_rejected(tiers, shift):
    tiers = [tier(t.min_quantity, t.max_quantity, t.price) for t in tiers]
    second = tiers[1]
    second.min_quantity += shift  # starts one too late (gap) or one too early (overlap)
    with pytest.raises(DomainValidationError):
        validate_tiers(tiers)


@PURE
@given(tiers=contiguous_tiers().filter(lambda t: len(t) >= 2))
def test_duplicate_tier_start_is_rejected(tiers):
    dup = tier(tiers[1].min_quantity, tiers[1].max_quantity, Decimal("1.00"))
    with pytest.raises(DomainValidationError):
        validate_tiers(tiers + [dup])


@PURE
@given(top=st.integers(min_value=1, max_value=500), inversion=st.integers(min_value=1, max_value=50))
def test_inverted_range_is_rejected(top, inversion):
    # Second tier starts at top+1 but ends below its own start, so its max is less than its min.
    tiers = [tier(1, top, Decimal("1.00")), tier(top + 1, top + 1 - inversion, Decimal("2.00"))]
    with pytest.raises(DomainValidationError):
        validate_tiers(tiers)


@PURE
@given(tiers=contiguous_tiers(), q=st.integers(min_value=1, max_value=400))
def test_boundary_quantity_belongs_to_exactly_one_tier(tiers, q):
    owner = brute_tier(tiers, q)  # asserts exactly one tier contains q
    result = calc(PricingMethod.BLOCK, Decimal("1.00"), q, tiers=tiers)
    assert result["total_price"] == owner.price.quantize(CENT)


@PURE
@given(tiers=contiguous_tiers(), q=st.integers(min_value=1, max_value=400))
def test_volume_mode_prices_the_whole_quantity_at_one_tier_price(tiers, q):
    owner = brute_tier(tiers, q)
    result = calc(PricingMethod.TIERED, Decimal("1.00"), q, tiers=tiers, tiered_mode=TieredMode.VOLUME)
    assert result["final_unit_price"] == owner.price.quantize(CENT)
    assert result["total_price"] == owner.price.quantize(CENT) * q


@PURE
@given(tiers=contiguous_tiers(), q=st.integers(min_value=1, max_value=400))
def test_cumulative_total_is_the_sum_over_slabs(tiers, q):
    expected = Decimal("0.00")
    remaining = q
    for t in tiers:
        capacity = remaining if t.max_quantity is None else t.max_quantity - t.min_quantity + 1
        in_slab = min(remaining, capacity)
        if in_slab > 0:
            expected += (in_slab * t.price).quantize(CENT)
            remaining -= in_slab
    result = calc(PricingMethod.TIERED, Decimal("1.00"), q, tiers=tiers, tiered_mode=TieredMode.CUMULATIVE)
    assert result["total_price"] == expected
    assert result["total_price"] == sum(
        (Decimal(b["amount"]) for b in result["calculation_breakdown"]), Decimal("0.00")
    )


# ─── Margin ─────────────────────────────────────────────────────────────────

@PURE
@given(base=MONEY_2DP, cost=MONEY_2DP, qty=QTY)
def test_margin_percent_is_none_exactly_when_selling_price_is_zero(base, cost, qty):
    # Scoped to a known cost. Without a cost, margin is undefined and the engine returns None for every margin field.
    result = calc(PricingMethod.STANDARD, base, qty, cost_price=cost)
    assert (result["margin_percentage"] is None) == (result["total_price"] == 0)


# ─── Through the service: permissions, overrides, audit ─────────────────────

def _run(coro):
    return asyncio.run(coro)


async def _product(db, *, price: Decimal, cost: Decimal):
    suffix = uuid.uuid4().hex[:8]
    product = Product(
        sku=f"PROP-{suffix}", name=f"Property Product {suffix}", base_price=price, cost_price=cost,
        currency="USD", is_active=True, billing_type="MRC",
    )
    db.add(product)
    await db.flush()
    return product


@DB
@given(
    price=MONEY_2DP.filter(lambda d: d > 0), cost=MONEY_2DP, qty=st.integers(min_value=1, max_value=50),
    method=st.sampled_from([PricingMethod.STANDARD, PricingMethod.LINE_DISCOUNT, PricingMethod.COST_PLUS_MARKUP]),
    perms=st.sets(st.sampled_from(["pricing.cost.view", "pricing.margin.view", "quotes.read"])),
)
def test_users_without_view_permissions_receive_none(price, cost, qty, method, perms):
    async def go():
        async with SessionLocal() as db:
            product = await _product(db, price=price, cost=cost)
            request = CalculatePriceRequest(
                product_id=product.id, quantity=qty, pricing_method=method, discount_percent=Decimal("5"),
            )
            out = await PricingApplicationService(db).calculate_price(request, user_permissions=set(perms))
            await db.rollback()
            return out

    out = _run(go())
    if "pricing.cost.view" not in perms:
        assert out.unit_cost is None and out.total_cost is None
    if "pricing.margin.view" not in perms:
        assert out.margin_amount is None and out.margin_percentage is None
    if "pricing.cost.view" in perms:
        assert out.unit_cost is not None


def _override_request(product_id, unit, reason):
    return CalculatePriceRequest(
        product_id=product_id, quantity=3, pricing_method=PricingMethod.STANDARD,
        override_unit_price=unit, override_reason=reason,
    )


@DB
@given(unit=st.decimals(min_value=Decimal("0"), max_value=Decimal("9999"), places=2, allow_nan=False, allow_infinity=False))
def test_override_without_reason_is_rejected(unit):
    async def go():
        async with SessionLocal() as db:
            product = await _product(db, price=Decimal("100.00"), cost=Decimal("40.00"))
            audits_before = (await db.execute(select(func.count()).select_from(PricingAuditLog)
                                              .where(PricingAuditLog.product_id == product.id))).scalar_one()
            with pytest.raises(DomainValidationError):
                await PricingApplicationService(db).calculate_price(
                    _override_request(product.id, unit, None),
                    user_permissions={"pricing.override", "pricing.cost.view", "pricing.margin.view"},
                    user_id=None, user_role="Administrator",
                )
            audits_after = (await db.execute(select(func.count()).select_from(PricingAuditLog)
                                             .where(PricingAuditLog.product_id == product.id))).scalar_one()
            await db.rollback()
            return audits_before, audits_after

    before, after = _run(go())
    assert before == after == 0


@DB
@given(unit=st.decimals(min_value=Decimal("0"), max_value=Decimal("9999"), places=2, allow_nan=False, allow_infinity=False),
       reason=st.text(min_size=3, max_size=80, alphabet=st.characters(whitelist_categories=("L", "N"))))
def test_override_with_reason_is_audited(unit, reason):
    async def go():
        async with SessionLocal() as db:
            product = await _product(db, price=Decimal("100.00"), cost=Decimal("40.00"))
            out = await PricingApplicationService(db).calculate_price(
                _override_request(product.id, unit, reason),
                user_permissions={"pricing.override", "pricing.cost.view", "pricing.margin.view"},
                user_id=None, user_role="Administrator",
            )
            # Copy the values out before the rollback expires the ORM rows.
            rows = [
                {"action": r.action, "product_id": r.product_id, "after": dict(r.after_value or {})}
                for r in (await db.execute(select(PricingAuditLog).where(
                    PricingAuditLog.product_id == product.id, PricingAuditLog.action == "PRICING_OVERRIDE_USED"
                ))).scalars().all()
            ]
            await db.rollback()
            return out, rows

    out, rows = _run(go())
    assert out.final_unit_price == unit.quantize(CENT)
    assert len(rows) == 1
    assert rows[0]["after"]["reason"] == reason
    assert rows[0]["after"]["final_unit_price"] == str(unit.quantize(CENT))


@DB
@given(unit=st.decimals(min_value=Decimal("0"), max_value=Decimal("9999"), places=2, allow_nan=False, allow_infinity=False))
def test_override_without_permission_is_refused_even_with_a_reason(unit):
    async def go():
        async with SessionLocal() as db:
            product = await _product(db, price=Decimal("100.00"), cost=Decimal("40.00"))
            with pytest.raises(HTTPException):
                await PricingApplicationService(db).calculate_price(
                    _override_request(product.id, unit, "reason given"),
                    user_permissions={"pricing.cost.view"}, user_id=None, user_role="Sales Representative",
                )
            await db.rollback()

    _run(go())
