"""
Output masking for tool results.

Cost fields need `pricing.cost.view`; margin fields need `pricing.margin.view`. These are the same
permissions the pricing engine uses for its own masking. Masking runs on the serialised output, so
it applies to every tool without each handler having to remember it.
"""
from typing import Any, Set

from backend.app.domains.auth.models import User

COST_FIELDS = frozenset({"cost_price", "unit_cost", "total_cost"})
MARGIN_FIELDS = frozenset({"margin_amount", "margin_percentage"})
COST_PERMISSION = "pricing.cost.view"
MARGIN_PERMISSION = "pricing.margin.view"


def user_permissions(user: User) -> Set[str]:
    return {p.name for r in (user.roles or []) for p in (r.permissions or [])}


def mask_fields(data: Any, permissions: Set[str]) -> Any:
    """Returns a copy of `data` with cost/margin values replaced by None where the caller lacks the permission."""
    hide_cost = COST_PERMISSION not in permissions
    hide_margin = MARGIN_PERMISSION not in permissions
    return _walk(data, hide_cost, hide_margin)


def _walk(value: Any, hide_cost: bool, hide_margin: bool) -> Any:
    if isinstance(value, dict):
        masked = {}
        for key, item in value.items():
            if (hide_cost and key in COST_FIELDS) or (hide_margin and key in MARGIN_FIELDS):
                masked[key] = None
            else:
                masked[key] = _walk(item, hide_cost, hide_margin)
        return masked
    if isinstance(value, list):
        return [_walk(item, hide_cost, hide_margin) for item in value]
    return value
