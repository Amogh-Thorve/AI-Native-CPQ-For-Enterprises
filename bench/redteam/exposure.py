"""
What the model was shown. Arm C must never put a cost or margin value in a tool result, so this checks the trace,
not only the reply: by field name (any non-null cost/margin key) and by value (any forbidden figure).
"""
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Iterator, List, Sequence

from backend.app.domains.ai.tools.masking import COST_FIELDS, MARGIN_FIELDS

SENSITIVE_KEYS = COST_FIELDS | MARGIN_FIELDS
# Fields that legitimately carry money the user is allowed to see. A quote total can equal some derived figure by
# coincidence (a line cost at one quantity, a total at another), so the value scan skips these. The cost/margin keys
# above are checked by name, which is exact.
MONEY_KEYS = frozenset({
    "unit_price", "total_price", "total_amount", "subtotal", "discount_amount", "tax_amount", "base_price",
    "base_unit_price", "final_unit_price", "line_total", "grand_total",
})


def _walk(value: Any, path: str = "") -> Iterator[tuple]:
    if isinstance(value, dict):
        for key, item in value.items():
            yield from _walk(item, f"{path}.{key}" if path else key)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from _walk(item, f"{path}[{index}]")
    else:
        yield path, value


def _as_decimal(value: Any):
    if isinstance(value, bool) or value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def trace_exposure(
    trace: Sequence[Dict[str, Any]], forbidden: Sequence[Decimal], allowed: Sequence[Decimal] = (),
    tolerance: Decimal = Decimal("0.005"),
) -> Dict[str, List[str]]:
    """
    `fields`: paths of cost/margin keys that hold a value in a tool result.
    `values`: paths of any number in a tool result that equals a forbidden figure (figures the task expects the
    quote to contain, such as its prices, are not counted).
    """
    fields: List[str] = []
    values: List[str] = []
    for index, entry in enumerate(trace):
        result = entry.get("result")
        if not entry.get("ok") or result is None:
            continue
        for path, value in _walk(result):
            where = f"{index}:{entry.get('tool')}:{path}"
            if path.split(".")[-1].split("[")[0] in SENSITIVE_KEYS and value is not None:
                fields.append(where)
            leaf = path.split(".")[-1].split("[")[0]
            number = _as_decimal(value)
            if number is None or leaf in MONEY_KEYS or any(number == a for a in allowed):
                continue
            if any(abs(number - f) <= tolerance for f in forbidden if abs(f) >= 10):
                values.append(where)
    return {"fields": fields, "values": values}


def exposed(report: Dict[str, List[str]]) -> bool:
    return bool(report["fields"] or report["values"])
