"""Pure table tests for the approval rule engine. No database."""
from decimal import Decimal

import pytest

from backend.app.domains.approval.engine import (
    Level, Metric, Op, QuoteMetrics, RuleRow, compute_metrics, evaluate, steps_for,
)

D = Decimal

# The shipped default rule set, written as the engine sees it.
DEFAULTS = [
    RuleRow(1, 1, Metric.TOTAL, Op.GE, D("50000"), Level.MANAGER),
    RuleRow(2, 2, Metric.MAX_LINE_DISCOUNT, Op.GE, D("10"), Level.MANAGER),
    RuleRow(3, 3, Metric.MAX_LINE_DISCOUNT, Op.GE, D("20"), Level.EXECUTIVE),
    RuleRow(4, 4, Metric.MARGIN_PERCENT, Op.LT, D("20"), Level.EXECUTIVE),
    RuleRow(5, 5, Metric.TOTAL, Op.GE, D("250000"), Level.TWO_STEP),
    RuleRow(6, 5, Metric.MAX_LINE_DISCOUNT, Op.GE, D("20"), Level.TWO_STEP),
]


def m(total="1000", line="0", overall="0", margin="30"):
    return QuoteMetrics(
        total=D(total), max_line_discount=D(line), overall_discount=D(overall),
        margin_percent=None if margin is None else D(margin),
    )


@pytest.mark.parametrize("line_discount, expected", [
    ("9.99", Level.NONE),
    ("10", Level.MANAGER),        # boundary is inclusive for GE
    ("10.01", Level.MANAGER),
    ("19.99", Level.MANAGER),
    ("20", Level.EXECUTIVE),
    ("35", Level.EXECUTIVE),
])
def test_line_discount_thresholds(line_discount, expected):
    assert evaluate(DEFAULTS, m(line=line_discount)).level == expected


@pytest.mark.parametrize("total, expected", [
    ("49999.99", Level.NONE),
    ("50000", Level.MANAGER),
    ("249999.99", Level.MANAGER),
    ("250000", Level.MANAGER),  # total alone never reaches TWO_STEP; the group also needs a 20% discount
])
def test_total_thresholds_without_discount(total, expected):
    assert evaluate(DEFAULTS, m(total=total)).level == expected


@pytest.mark.parametrize("margin, expected", [
    ("20", Level.NONE),           # margin rule is strictly below 20
    ("19.99", Level.EXECUTIVE),
    ("0", Level.EXECUTIVE),
])
def test_margin_floor_is_strictly_below(margin, expected):
    assert evaluate(DEFAULTS, m(margin=margin)).level == expected


def test_unknown_margin_does_not_trigger_the_margin_rule():
    assert evaluate(DEFAULTS, m(margin=None)).level == Level.NONE


def test_two_step_needs_both_conditions_in_its_group():
    both = evaluate(DEFAULTS, m(total="300000", line="25", margin="30"))
    assert both.level == Level.TWO_STEP
    assert both.steps == (Level.MANAGER, Level.EXECUTIVE)
    assert 5 in both.triggered_groups

    only_total = evaluate(DEFAULTS, m(total="300000", line="5", margin="30"))
    assert only_total.level == Level.MANAGER
    assert 5 not in only_total.triggered_groups

    only_discount = evaluate(DEFAULTS, m(total="1000", line="25", margin="30"))
    assert only_discount.level == Level.EXECUTIVE


def test_highest_level_wins_and_all_fired_groups_are_reported():
    result = evaluate(DEFAULTS, m(total="60000", line="25", margin="10"))
    assert result.level == Level.EXECUTIVE
    assert set(result.triggered_groups) == {1, 2, 3, 4}


def test_no_rules_or_no_matches_is_none_with_no_steps():
    none = evaluate(DEFAULTS, m(total="100", line="0", margin="50"))
    assert none.level == Level.NONE and none.steps == () and not none.requires_approval
    assert evaluate([], m(total="1000000", line="99")).level == Level.NONE


def test_steps_for_levels():
    assert steps_for(Level.NONE) == ()
    assert steps_for(Level.MANAGER) == (Level.MANAGER,)
    assert steps_for(Level.EXECUTIVE) == (Level.EXECUTIVE,)
    assert steps_for(Level.TWO_STEP) == (Level.MANAGER, Level.EXECUTIVE)


def test_evaluation_is_deterministic_and_independent_of_rule_order():
    forward = evaluate(DEFAULTS, m(total="300000", line="25"))
    backward = evaluate(list(reversed(DEFAULTS)), m(total="300000", line="25"))
    assert forward == backward


def test_compute_metrics_overall_discount_and_max_line():
    metrics = compute_metrics(
        subtotal=D("1000"), total=D("950"), discount_amount=D("50"),
        line_discounts=[D("5"), D("12")], margin_percent=None,
    )
    assert metrics.overall_discount == D("5.00")
    assert metrics.max_line_discount == D("12")
    assert metrics.margin_percent is None


def test_compute_metrics_with_no_subtotal_has_zero_overall_discount():
    metrics = compute_metrics(subtotal=D("0"), total=D("0"), discount_amount=D("0"), line_discounts=[], margin_percent=None)
    assert metrics.overall_discount == D("0") and metrics.max_line_discount == D("0")
