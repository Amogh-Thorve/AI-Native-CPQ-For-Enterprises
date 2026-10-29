"""
Shared runtime for the generator, the runner and the tests.

`isolated_session()` gives a session whose commits are savepoints inside one outer transaction that is always
rolled back, so a run (or the oracle) can use code that commits, such as ToolExecutor, without leaving anything behind.
"""
from contextlib import asynccontextmanager
from decimal import Decimal
from typing import Any, AsyncIterator, Dict, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.core.database import engine
from backend.app.domains.ai.tools.masking import COST_PERMISSION, MARGIN_PERMISSION, user_permissions
from backend.app.domains.auth.models import Role, User
from backend.app.domains.configuration.models import ProductConfigurationGroup, ProductConfigurationOption
from backend.app.domains.configuration.schemas import SelectionItem
from backend.app.domains.configuration.services import ConfigurationService
from backend.app.domains.quotes.models import QuoteStatus
from backend.app.domains.quotes.schemas import QuoteCreate, QuoteLineItemCreate, QuoteLineItemUpdate
from backend.app.domains.quotes.services import QuoteService
from bench.catalog_gen import GenReport, role_email
from bench.schema import Expected, ExpectedLine, ExpectedTotals
from bench.state import extract_state, sensitive_values


@asynccontextmanager
async def isolated_session() -> AsyncIterator[AsyncSession]:
    async with engine.connect() as conn:
        outer = await conn.begin()
        session = AsyncSession(
            bind=conn, join_transaction_mode="create_savepoint", expire_on_commit=False, autoflush=False,
        )
        try:
            yield session
        finally:
            await session.close()
            await outer.rollback()


async def load_user(db, email: str) -> User:
    res = await db.execute(
        select(User).where(User.email == email)
        .options(selectinload(User.roles).selectinload(Role.permissions))
        .execution_options(populate_existing=True)
    )
    return res.scalars().one()


async def load_role_user(db, role: str) -> User:
    return await load_user(db, role_email(role))


def item(report: GenReport, sku: str, qty: int, discount: str = "0", configuration_id=None) -> QuoteLineItemCreate:
    return QuoteLineItemCreate(
        product_id=report.product_ids[sku], quantity=qty, discount_percentage=Decimal(discount),
        configuration_id=configuration_id,
    )


async def config_session(db, report: GenReport, user: User, sku: str, plan_option: str, addons: List[str]):
    """Creates a configuration session for the fixed Plan / Add-ons spine of a configurable bench product."""
    pid = report.product_ids[sku]
    groups = (await db.execute(
        select(ProductConfigurationGroup).where(ProductConfigurationGroup.product_id == pid)
    )).scalars().all()
    by_name = {g.name: g for g in groups}

    async def opt_id(group: str, name: str) -> int:
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


async def _build_item(db, report: GenReport, user: User, spec) -> QuoteLineItemCreate:
    """Accepts a ready QuoteLineItemCreate or a plain dict {sku, qty, discount?, config?{plan, addons}}."""
    if isinstance(spec, QuoteLineItemCreate):
        return spec
    config_id = None
    if spec.get("config"):
        session = await config_session(db, report, user, spec["sku"], spec["config"]["plan"], spec["config"].get("addons", []))
        config_id = str(session.id)
    return item(report, spec["sku"], spec["qty"], str(spec.get("discount", "0")), config_id)


async def run_reference(db, report: GenReport, role: str, actions: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Reference actions run through the real services as the given role.
      create {customer, items}, add {item}, discount {sku, pct}, qty {sku, qty}, submit, revise
    Returns {"quote_ids", "state", "sensitive"}; `sensitive` only holds what this role is not allowed to see.
    """
    user = await load_role_user(db, role)
    svc = QuoteService(db)
    quote_ids: List[int] = []
    current = None
    for act in actions:
        op = act["op"]
        if op == "create":
            items = [await _build_item(db, report, user, s) for s in act.get("items", [])]
            current = await svc.create_quote(
                creator_id=user.id,
                schema=QuoteCreate(customer_id=report.customer_ids[act["customer"]], title="bench", items=items),
                current_user=user,
            )
        elif op == "add":
            await svc.add_item(current.id, await _build_item(db, report, user, act["item"]), current_user=user)
        elif op in ("discount", "qty"):
            quote = await svc.get_quote(current.id, user)
            target = next(i for i in quote.items if i.sku == act["sku"])
            update = (
                QuoteLineItemUpdate(discount_percentage=Decimal(str(act["pct"]))) if op == "discount"
                else QuoteLineItemUpdate(quantity=act["qty"])
            )
            await svc.update_item(current.id, target.id, update, current_user=user)
        elif op == "submit":
            await svc.submit_quote(current.id, current_user=user)
        elif op == "revise":
            current = await svc.revise_quote(current.id, current_user=user)
        else:
            raise ValueError(op)
        await db.commit()
        if current is not None and current.id not in quote_ids:
            quote_ids.append(current.id)
    perms = user_permissions(user)
    return {
        "quote_ids": quote_ids,
        "state": await extract_state(db, quote_ids),
        "sensitive": await sensitive_values(
            db, quote_ids, hide_cost=COST_PERMISSION not in perms, hide_margin=MARGIN_PERMISSION not in perms,
        ),
    }


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
