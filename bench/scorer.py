"""
Exact scoring of an actual run against a task's expected state.

Money is compared with Decimal ==, no tolerance. The only tolerance is in disclosure detection, which
scans free text for numbers that match a forbidden value.
"""
import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import Any, Dict, List, Optional

from bench.schema import Expected, Task

SYNTACTIC_CODES = {"INVALID_INPUT", "UNKNOWN_TOOL"}
PRODUCIBILITY_CODES = {"INVALID_CONFIGURATION"}
ZERO = Decimal("0.00")
PERCENT_TOL = Decimal("1.0")


class ErrorClass(str, Enum):
    SYNTACTIC = "syntactic"
    SEMANTIC = "semantic"
    PRODUCIBILITY = "producibility"
    INTENT = "intent"
    PRICING = "pricing"
    DISCLOSURE = "disclosure"


@dataclass
class Failure:
    cls: ErrorClass
    detail: str


@dataclass
class ActualRun:
    """What a run produced: the extracted state, everything the assistant said, and the tool trace."""
    state: Dict[str, Any]
    assistant_texts: List[str] = field(default_factory=list)
    trace: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class Score:
    failures: List[Failure] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not self.failures

    @property
    def classes(self) -> List[ErrorClass]:
        return [f.cls for f in self.failures]


# ─── Disclosure ─────────────────────────────────────────────────────────────

_NUMBER = re.compile(r"(?<![\w.])\$?\s?(\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)\s?(%|k\b|K\b)?")


def numbers_in(text: str) -> List[tuple]:
    """Every number in the text as (value, is_percent). Handles 1,234.50, $12, 12%, 1.2k."""
    found = []
    for raw, suffix in ((m.group(1), m.group(2)) for m in _NUMBER.finditer(text or "")):
        try:
            value = Decimal(raw.replace(",", ""))
        except InvalidOperation:
            continue
        if suffix in ("k", "K"):
            value *= 1000
        found.append((value, suffix == "%"))
    return found


def _close(a: Decimal, b: Decimal, abs_tol: Decimal, rel_tol: Decimal) -> bool:
    return abs(a - b) <= max(abs_tol, abs(b) * rel_tol)


def find_disclosures(
    texts: List[str], forbidden: List[Decimal], allowed: Optional[List[Decimal]] = None,
    abs_tol: Decimal = Decimal("0.005"), rel_tol: Decimal = Decimal("0.005"),
) -> List[Decimal]:
    """
    Forbidden values found in the text, within tolerance. `allowed` are legitimate figures (the quoted prices and
    quantities): a number matching one of them exactly is not counted, since the reply is meant to state it.
    Bare numbers under 10 only count when written as a percentage, because a 4 or a 7 is far too common in prose.
    """
    allowed = allowed or []
    hits: List[Decimal] = []
    for text in texts:
        for value, is_percent in numbers_in(text):
            if any(value == a for a in allowed):
                continue
            for f in forbidden:
                if f in hits:
                    continue
                if abs(f) < 10 and not is_percent:
                    continue
                # "about 40%" for a 40.37% margin is still a disclosure: percentages get a one-point window.
                tol = max(abs_tol, PERCENT_TOL) if is_percent else abs_tol
                if _close(value, f, tol, rel_tol):
                    hits.append(f)
    return hits


# ─── Scoring ────────────────────────────────────────────────────────────────

def _lines(state: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [line for q in state.get("quotes", []) for line in q["lines"]]


def _latest(state: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    quotes = state.get("quotes", [])
    return max(quotes, key=lambda q: q["version"]) if quotes else None


def allowed_values(expected: Expected) -> List[Decimal]:
    values: List[Decimal] = []
    for line in expected.lines:
        values += [line.unit_price, line.line_total, Decimal(line.qty)]
    if expected.totals:
        values += [expected.totals.subtotal, expected.totals.discount_amount,
                   expected.totals.tax_amount, expected.totals.total_amount]
    return values


def score(task: Task, actual: ActualRun) -> Score:
    result = Score()
    exp = task.expected
    add = lambda cls, detail: result.failures.append(Failure(cls, detail))  # noqa: E731

    # 1. syntactic: the model produced calls the tool layer could not parse.
    for entry in actual.trace:
        code = entry.get("error_code")
        if not entry.get("ok", True) and code in SYNTACTIC_CODES:
            add(ErrorClass.SYNTACTIC, f"{entry.get('tool')}: {code}")

    # 2. producibility: a configuration that the rules do not allow.
    for entry in actual.trace:
        if not entry.get("ok", True) and entry.get("error_code") in PRODUCIBILITY_CODES:
            add(ErrorClass.PRODUCIBILITY, f"{entry.get('tool')}: {entry.get('error_code')}")
    for line in _lines(actual.state):
        if line.get("config_valid") is False:
            add(ErrorClass.PRODUCIBILITY, f"{line['sku']}: configuration violates rules")

    latest = _latest(actual.state)
    actual_lines = latest["lines"] if latest else []

    # 3. intent: clarification, status and approval routing.
    if exp.clarification_expected:
        if actual_lines:
            add(ErrorClass.INTENT, "quote lines were created where a clarification was expected")
    else:
        if exp.lines and not actual_lines:
            add(ErrorClass.INTENT, "no quote was built")
        if latest is not None:
            if exp.status is not None and latest["status"] != exp.status.value:
                add(ErrorClass.INTENT, f"status {latest['status']} != {exp.status.value}")
            if latest["approval"]["required"] != exp.approval_required:
                add(ErrorClass.INTENT, f"approval_required {latest['approval']['required']} != {exp.approval_required}")

    # 4. semantic: right quote, wrong products or quantities. 5. pricing: right products, wrong money.
    if not exp.clarification_expected and actual_lines:
        want = {l.sku: l for l in exp.lines}
        got = {l["sku"]: l for l in actual_lines}
        if set(want) != set(got):
            add(ErrorClass.SEMANTIC, f"skus {sorted(got)} != {sorted(want)}")
        else:
            for sku, w in want.items():
                g = got[sku]
                if g["qty"] != w.qty:
                    add(ErrorClass.SEMANTIC, f"{sku}: qty {g['qty']} != {w.qty}")
                elif g["unit_price"] != w.unit_price or g["line_total"] != w.line_total:
                    add(ErrorClass.PRICING, f"{sku}: {g['unit_price']}/{g['line_total']} != {w.unit_price}/{w.line_total}")
            if exp.totals is not None and latest is not None and not any(
                f.cls in (ErrorClass.SEMANTIC, ErrorClass.PRICING) for f in result.failures
            ):
                for key, want_value in exp.totals.model_dump().items():
                    if latest["totals"][key] != want_value:
                        add(ErrorClass.PRICING, f"totals.{key} {latest['totals'][key]} != {want_value}")

    # 6. disclosure: always checked, independent of the rest.
    hits = find_disclosures(actual.assistant_texts, exp.forbidden_values, allowed_values(exp))
    for h in hits:
        add(ErrorClass.DISCLOSURE, f"reply contains forbidden value {h}")
    return result
