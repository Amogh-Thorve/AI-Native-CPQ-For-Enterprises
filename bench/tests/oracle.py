"""
Reference oracle: runs a task's reference actions through the real services and records the resulting state.
Expected values in bench tasks come from here, not from numbers typed by hand.
"""
from decimal import Decimal
from typing import Any, Dict, List

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from bench.catalog_gen import GenReport, role_email
from bench.schema import Expected, ExpectedLine, ExpectedTotals
from bench.state import extract_state, sensitive_values
from backend.app.domains.auth.models import Role, User
from backend.app.domains.quotes.models import QuoteStatus
from backend.app.domains.quotes.schemas import QuoteCreate, QuoteLineItemCreate, QuoteLineItemUpdate
from backend.app.domains.quotes.services import QuoteService


async def load_user(db, email: str) -> User:
    res = await db.execute(
        select(User).where(User.email == email)
        .options(selectinload(User.roles).selectinload(Role.permissions))
        .execution_options(populate_existing=True)
    )
    return res.scalars().one()


def item(report: GenReport, sku: str, qty: int, discount: str = "0", configuration_id=None) -> QuoteLineItemCreate:
    return QuoteLineItemCreate(
        product_id=report.product_ids[sku], quantity=qty, discount_percentage=Decimal(discount),
        configuration_id=configuration_id,
    )


async def run_reference(db, report: GenReport, role: str, actions: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Actions: create {customer, items}, add {item}, discount {sku, pct}, submit, revise.
    Returns {"quote_ids": [...], "state": canonical state, "sensitive": [Decimal]}.
    """
    user = await load_user(db, role_email(role))
    svc = QuoteService(db)
    quote_ids: List[int] = []
    current = None
    for act in actions:
        op = act["op"]
        if op == "create":
            current = await svc.create_quote(
                creator_id=user.id,
                schema=QuoteCreate(customer_id=report.customer_ids[act["customer"]], title="bench", items=act.get("items", [])),
                current_user=user,
            )
        elif op == "add":
            await svc.add_item(current.id, act["item"], current_user=user)
        elif op == "discount":
            quote = await svc.get_quote(current.id, user)
            target = next(i for i in quote.items if i.sku == act["sku"])
            await svc.update_item(
                current.id, target.id, QuoteLineItemUpdate(discount_percentage=Decimal(act["pct"])), current_user=user,
            )
        elif op == "submit":
            await svc.submit_quote(current.id, current_user=user)
        elif op == "revise":
            current = await svc.revise_quote(current.id, current_user=user)
        else:
            raise ValueError(op)
        await db.commit()
        if current is not None and current.id not in quote_ids:
            quote_ids.append(current.id)
    state = await extract_state(db, quote_ids)
    return {"quote_ids": quote_ids, "state": state, "sensitive": await sensitive_values(db, quote_ids)}


def expected_from(result: Dict[str, Any], forbidden: bool = False) -> Expected:
    """Expected block from the newest quote version in an oracle run."""
    quote = max(result["state"]["quotes"], key=lambda q: q["version"])
    return Expected(
        lines=[
            ExpectedLine(sku=l["sku"], qty=l["qty"], unit_price=l["unit_price"], line_total=l["line_total"])
            for l in quote["lines"]
        ],
        totals=ExpectedTotals(**quote["totals"]),
        status=QuoteStatus(quote["status"]),
        approval_required=quote["approval"]["required"],
        forbidden_values=result["sensitive"] if forbidden else [],
    )
