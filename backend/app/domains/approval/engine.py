"""
Deterministic approval rules. No I/O: the same rules and metrics always give the same answer.

A rule row is one condition. Rows that share a `group` must all hold for the group to fire (AND). A fired
group sets its required level. The quote's requirement is the highest level among the fired groups, and
that level decides who must sign off (see `steps_for`).
"""
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum, IntEnum
from typing import Iterable, Optional, Sequence, Tuple


class Level(IntEnum):
    NONE = 0
    MANAGER = 1
    EXECUTIVE = 2
    TWO_STEP = 3  # manager, then executive


class Metric(str, Enum):
    TOTAL = "TOTAL"
    MAX_LINE_DISCOUNT = "MAX_LINE_DISCOUNT"
    OVERALL_DISCOUNT = "OVERALL_DISCOUNT"
    MARGIN_PERCENT = "MARGIN_PERCENT"


class Op(str, Enum):
    GE = "GE"  # metric >= threshold
    LT = "LT"  # metric <  threshold


STEP_ROLES = {Level.MANAGER: "Sales Manager", Level.EXECUTIVE: "Executive"}


@dataclass(frozen=True)
class RuleRow:
    rule_id: int
    group: int
    metric: Metric
    op: Op
    threshold: Decimal
    level: Level


@dataclass(frozen=True)
class QuoteMetrics:
    total: Decimal
    max_line_discount: Decimal
    overall_discount: Decimal
    margin_percent: Optional[Decimal]  # None when cost is unknown; a margin rule then cannot fire


@dataclass(frozen=True)
class RequiredApproval:
    level: Level
    steps: Tuple[Level, ...]
    triggered_groups: Tuple[int, ...]

    @property
    def requires_approval(self) -> bool:
        return self.level != Level.NONE


def steps_for(level: Level) -> Tuple[Level, ...]:
    if level == Level.NONE:
        return ()
    if level == Level.TWO_STEP:
        return (Level.MANAGER, Level.EXECUTIVE)
    return (level,)


def _value(metric: Metric, m: QuoteMetrics) -> Optional[Decimal]:
    return {
        Metric.TOTAL: m.total,
        Metric.MAX_LINE_DISCOUNT: m.max_line_discount,
        Metric.OVERALL_DISCOUNT: m.overall_discount,
        Metric.MARGIN_PERCENT: m.margin_percent,
    }[metric]


def _holds(row: RuleRow, m: QuoteMetrics) -> bool:
    value = _value(row.metric, m)
    if value is None:
        return False
    return value >= row.threshold if row.op is Op.GE else value < row.threshold


def evaluate(rules: Iterable[RuleRow], metrics: QuoteMetrics) -> RequiredApproval:
    groups: dict[int, list[RuleRow]] = {}
    for row in rules:
        groups.setdefault(row.group, []).append(row)

    top = Level.NONE
    fired = []
    for group_id in sorted(groups):
        rows = groups[group_id]
        if all(_holds(r, metrics) for r in rows):
            fired.append(group_id)
            top = max(top, max(r.level for r in rows))
    return RequiredApproval(level=top, steps=steps_for(top), triggered_groups=tuple(fired))


def compute_metrics(
    subtotal: Decimal, total: Decimal, discount_amount: Decimal,
    line_discounts: Sequence[Decimal], margin_percent: Optional[Decimal],
) -> QuoteMetrics:
    """Builds the metrics the rules read. Overall discount is the quote-level discount over the subtotal."""
    overall = (discount_amount / subtotal * Decimal("100")) if subtotal > 0 else Decimal("0")
    return QuoteMetrics(
        total=total,
        max_line_discount=max(line_discounts, default=Decimal("0")),
        overall_discount=overall.quantize(Decimal("0.01")),
        margin_percent=margin_percent,
    )
