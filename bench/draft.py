"""
Arm A output format. With no tools the model answers with a JSON quote draft; this module parses it and turns it
into the same canonical state the scorer reads for arms B and C.
"""
import json
import re
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Dict, List, Literal, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field, ValidationError

DRAFT_EXAMPLE = {
    "clarification": None,
    "customer_number": "BENCH-C001",
    "status": "DRAFT",
    "approval_required": False,
    "lines": [{"sku": "BENCH-P0001", "qty": 2, "unit_price": "100.00", "line_total": "200.00"}],
    "totals": {"subtotal": "200.00", "discount_amount": "0.00", "tax_amount": "16.00", "total_amount": "216.00"},
}


class DraftLine(BaseModel):
    model_config = ConfigDict(extra="ignore")
    sku: str
    qty: int = Field(ge=1)
    unit_price: Decimal
    line_total: Decimal


class DraftTotals(BaseModel):
    model_config = ConfigDict(extra="ignore")
    subtotal: Decimal
    discount_amount: Decimal = Decimal("0")
    tax_amount: Decimal = Decimal("0")
    total_amount: Decimal


class Draft(BaseModel):
    model_config = ConfigDict(extra="ignore")
    clarification: Optional[str] = None
    customer_number: Optional[str] = None
    status: Literal["DRAFT", "SUBMITTED", "APPROVED"] = "DRAFT"
    approval_required: bool = False
    lines: List[DraftLine] = []
    totals: Optional[DraftTotals] = None


_FENCE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)


def _json_candidates(text: str) -> List[str]:
    found = [m.group(1) for m in _FENCE.finditer(text or "")]
    start, end = (text or "").find("{"), (text or "").rfind("}")
    if start != -1 and end > start:
        found.append(text[start:end + 1])
    return found


def parse_draft(text: str) -> Tuple[Optional[Draft], Optional[str]]:
    """The last JSON object in the reply that fits the schema, or an error message."""
    error = "no JSON object in the reply"
    for candidate in reversed(_json_candidates(text)):
        try:
            return Draft.model_validate(json.loads(candidate)), None
        except (json.JSONDecodeError, ValidationError) as exc:
            error = f"{type(exc).__name__}: {str(exc)[:200]}"
    return None, error


def _q2(value: Decimal) -> Decimal:
    return Decimal(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def draft_to_state(draft: Draft) -> Dict[str, Any]:
    if not draft.lines:
        return {"quotes": []}
    totals = draft.totals
    return {"quotes": [{
        "number": "DRAFT", "version": 1, "status": draft.status, "currency": "USD",
        "customer_number": draft.customer_number,
        "totals": {
            "subtotal": _q2(totals.subtotal) if totals else Decimal("0.00"),
            "discount_amount": _q2(totals.discount_amount) if totals else Decimal("0.00"),
            "tax_amount": _q2(totals.tax_amount) if totals else Decimal("0.00"),
            "total_amount": _q2(totals.total_amount) if totals else Decimal("0.00"),
        },
        "lines": [
            {"sku": l.sku, "qty": l.qty, "unit_price": _q2(l.unit_price), "discount_pct": Decimal("0.00"),
             "line_total": _q2(l.line_total), "config_valid": None}
            for l in sorted(draft.lines, key=lambda l: l.sku)
        ],
        "approval": {"required": draft.approval_required, "level": None, "request_status": None, "steps": []},
        "orders": [],
    }]}
