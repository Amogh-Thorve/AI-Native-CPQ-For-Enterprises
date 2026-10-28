"""
Typed tool layer tests. They run against the local dev database, as the other domain tests do.
No network calls and no LLM.
"""
import uuid
from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from backend.app.core.database import SessionLocal
from backend.app.domains.auth.models import Role, User
from backend.app.domains.auth.schemas import UserCreate
from backend.app.domains.auth.services import AuthService
from backend.app.domains.catalog.models import Category, Product
from backend.app.domains.configuration.services import ConfigurationService
from backend.app.domains.customer.schemas import CustomerCreate
from backend.app.domains.customer.services import CustomerService
from backend.app.domains.pricing.models import ProductPricingSetting
from backend.app.domains.quotes.models import QuoteLineItem
from backend.app.domains.quotes.schemas import QuoteCreate, QuoteLineItemCreate
from backend.app.domains.quotes.services import QuoteService
from backend.app.domains.ai.tools import TOOL_BY_NAME, Deny, NeedsApproval, ToolExecutor

PASSWORD = "ToolsTest123!"


# ─── Fixtures as plain helpers ──────────────────────────────────────────────

async def load_user(db, user_id) -> User:
    res = await db.execute(
        select(User).where(User.id == user_id)
        .options(selectinload(User.roles).selectinload(Role.permissions))
        .execution_options(populate_existing=True)
    )
    return res.scalars().one()


async def ensure_user(db, email: str, role_name: str) -> User:
    """Creates the user once and reuses it on later runs. A role missing from the seed is created with no permissions."""
    user = (await db.execute(select(User).where(User.email == email))).scalars().first()
    if user is None:
        user = await AuthService(db).register_user(UserCreate(
            email=email, first_name="Tool", last_name="Test", username=email.split("@")[0].replace(".", "_"),
            password=PASSWORD, confirm_password=PASSWORD,
        ))
        await db.commit()
    role = (await db.execute(select(Role).where(Role.name == role_name))).scalars().first()
    if role is None:
        role = Role(name=role_name, description="Tool tests: no permissions")
        db.add(role)
        await db.flush()
    user = await load_user(db, user.id)
    user.roles = [role]
    await db.commit()
    return await load_user(db, user.id)


async def build_world(db) -> dict:
    rep_a = await ensure_user(db, "tools.rep.a@cpq.com", "Sales Representative")
    rep_b = await ensure_user(db, "tools.rep.b@cpq.com", "Sales Representative")
    exec_user = await ensure_user(db, "tools.exec@cpq.com", "Executive")
    noaccess = await ensure_user(db, "tools.noaccess@cpq.com", "Tools No Access")

    suffix = uuid.uuid4().hex[:6]
    category = Category(name=f"Tools_{suffix}", description="tool tests")
    db.add(category)
    await db.flush()
    product = Product(
        sku=f"TOOL-{suffix}", name=f"Tools Laptop {suffix}", base_price=Decimal("1000.00"),
        cost_price=Decimal("700.00"), currency="USD", is_active=True, billing_type="NRC", category_id=category.id,
    )
    db.add(product)
    await db.flush()
    db.add(ProductPricingSetting(product_id=product.id, pricing_method="STANDARD", markup_percent=Decimal("0"), status="ACTIVE"))
    await db.commit()

    customers = CustomerService(db)
    cust_a = await customers.create_customer(rep_a.id, CustomerCreate(customer_number=f"TA-{suffix}", legal_name=f"Tools Co A {suffix}"), current_user=rep_a)
    cust_b = await customers.create_customer(rep_b.id, CustomerCreate(customer_number=f"TB-{suffix}", legal_name=f"Tools Co B {suffix}"), current_user=rep_b)
    await db.commit()

    quotes = QuoteService(db)
    q_a = await quotes.create_quote(
        creator_id=rep_a.id,
        schema=QuoteCreate(customer_id=cust_a.id, title="Rep A quote", items=[QuoteLineItemCreate(product_id=product.id, quantity=2)]),
        current_user=rep_a,
    )
    q_b = await quotes.create_quote(
        creator_id=rep_b.id,
        schema=QuoteCreate(customer_id=cust_b.id, title="Rep B quote", items=[QuoteLineItemCreate(product_id=product.id, quantity=1)]),
        current_user=rep_b,
    )
    await db.commit()
    q_a = await quotes.get_quote(q_a.id, rep_a)
    await db.refresh(q_a, attribute_names=["items"])
    q_b = await quotes.get_quote(q_b.id, rep_b)
    await db.refresh(q_b, attribute_names=["items"])

    return {
        "rep_a": rep_a.id, "rep_b": rep_b.id, "exec": exec_user.id, "noaccess": noaccess.id,
        "sku": product.sku, "product_id": product.id,
        "cust_a": cust_a.id, "cust_b": cust_b.id,
        "quote_a": q_a.id, "item_a": q_a.items[0].id, "quote_b": q_b.id,
    }


def happy_args(w: dict, name: str) -> dict:
    p, c, q, i = w["product_id"], w["cust_a"], w["quote_a"], w["item_a"]
    return {
        "search_products": {"query": w["sku"]},
        "get_customer": {"customer_id": c},
        "list_customers": {"page_size": 5},
        "validate_configuration": {"product_id": p},
        "price_item": {"product_id": p, "quantity": 2, "discount_percent": "5"},
        "create_quote": {"customer_id": c, "title": "Tool-created", "items": [{"product_id": p, "quantity": 1}]},
        "add_quote_item": {"quote_id": q, "product_id": p, "quantity": 1},
        "update_quote_item": {"quote_id": q, "item_id": i, "quantity": 3},
        "remove_quote_item": {"quote_id": q, "item_id": i},
        "get_quote": {"quote_id": q},
        "submit_quote": {"quote_id": q},
        "revise_quote": {"quote_id": q},
    }[name]


TOOL_NAMES = list(TOOL_BY_NAME)


# ─── Happy path and permission denial, for every tool ──────────────────────

@pytest.mark.asyncio
@pytest.mark.parametrize("name", TOOL_NAMES)
async def test_happy_path(name):
    async with SessionLocal() as db:
        w = await build_world(db)
        rep = await load_user(db, w["rep_a"])
        ex = ToolExecutor(rep, db)
        res = await ex.call(name, happy_args(w, name))
        assert res["ok"], res
        assert ex.trace[-1].ok and ex.trace[-1].tool == name


@pytest.mark.asyncio
@pytest.mark.parametrize("name", TOOL_NAMES)
async def test_permission_denied(name):
    async with SessionLocal() as db:
        w = await build_world(db)
        noaccess = await load_user(db, w["noaccess"])
        ex = ToolExecutor(noaccess, db)
        res = await ex.call(name, happy_args(w, name))
        assert res["ok"] is False and res["error_code"] == "FORBIDDEN", res
        assert ex.trace[-1].error_code == "FORBIDDEN"


# ─── Cost and margin masking ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_rep_gets_null_cost_and_margin_executive_does_not():
    async with SessionLocal() as db:
        w = await build_world(db)
        rep = await load_user(db, w["rep_a"])
        exe = await load_user(db, w["exec"])
        args = {"product_id": w["product_id"], "quantity": 2}

        rep_price = (await ToolExecutor(rep, db).call("price_item", args))["data"]
        assert rep_price["unit_cost"] is None and rep_price["total_cost"] is None
        assert rep_price["margin_amount"] is None and rep_price["margin_percentage"] is None

        exe_price = (await ToolExecutor(exe, db).call("price_item", args))["data"]
        assert exe_price["unit_cost"] is not None and exe_price["total_cost"] is not None
        assert exe_price["margin_amount"] is not None and exe_price["margin_percentage"] is not None

        rep_products = (await ToolExecutor(rep, db).call("search_products", {"query": w["sku"]}))["data"]["items"]
        assert rep_products and all(p["cost_price"] is None for p in rep_products)
        exe_products = (await ToolExecutor(exe, db).call("search_products", {"query": w["sku"]}))["data"]["items"]
        assert exe_products and exe_products[0]["cost_price"] is not None


@pytest.mark.asyncio
async def test_quote_lines_are_masked_for_rep_and_visible_to_executive():
    async with SessionLocal() as db:
        w = await build_world(db)
        rep = await load_user(db, w["rep_a"])
        exe = await load_user(db, w["exec"])

        rep_quote = (await ToolExecutor(rep, db).call("get_quote", {"quote_id": w["quote_a"]}))["data"]
        assert rep_quote["margin_percentage"] is None
        assert all(line["margin_amount"] is None and line["margin_percentage"] is None for line in rep_quote["items"])

        exe_quote = (await ToolExecutor(exe, db).call("get_quote", {"quote_id": w["quote_a"]}))["data"]
        assert exe_quote["margin_percentage"] is not None
        assert all(line["margin_amount"] is not None for line in exe_quote["items"])


# ─── Ownership ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_rep_cannot_read_another_reps_quote():
    async with SessionLocal() as db:
        w = await build_world(db)
        rep_a = await load_user(db, w["rep_a"])
        res = await ToolExecutor(rep_a, db).call("get_quote", {"quote_id": w["quote_b"]})
        assert res["ok"] is False and res["error_code"] == "FORBIDDEN"


@pytest.mark.asyncio
async def test_rep_cannot_edit_or_read_another_reps_customer():
    async with SessionLocal() as db:
        w = await build_world(db)
        rep_a = await load_user(db, w["rep_a"])
        ex = ToolExecutor(rep_a, db)
        # Tenant isolation: each user is their own tenant, so another rep's customer is not found at all.
        assert (await ex.call("get_customer", {"customer_id": w["cust_b"]}))["error_code"] == "NOT_FOUND"
        before = (await db.execute(select(func.count()).select_from(QuoteLineItem).where(QuoteLineItem.quote_id == w["quote_b"]))).scalar()
        res = await ex.call("add_quote_item", {"quote_id": w["quote_b"], "product_id": w["product_id"], "quantity": 1})
        assert res["error_code"] == "FORBIDDEN"
        after = (await db.execute(select(func.count()).select_from(QuoteLineItem).where(QuoteLineItem.quote_id == w["quote_b"]))).scalar()
        assert before == after


# ─── Input rules: no free-text prices, bounded values, structured errors ───

@pytest.mark.asyncio
@pytest.mark.parametrize("args", [
    {"product_id": 1, "quantity": -1},
    {"product_id": 1, "quantity": 1, "discount_percent": 150},
    {"product_id": 1, "quantity": 1, "unit_price": "1.00"},
    {"product_id": 1, "quantity": 1, "total_price": "1.00"},
])
async def test_price_inputs_are_validated(args):
    async with SessionLocal() as db:
        w = await build_world(db)
        rep = await load_user(db, w["rep_a"])
        res = await ToolExecutor(rep, db).call("price_item", args)
        assert res["ok"] is False and res["error_code"] == "INVALID_INPUT", res


@pytest.mark.asyncio
async def test_unknown_product_is_a_structured_not_found():
    async with SessionLocal() as db:
        w = await build_world(db)
        rep = await load_user(db, w["rep_a"])
        res = await ToolExecutor(rep, db).call("price_item", {"product_id": 999_999_999, "quantity": 1})
        assert res["ok"] is False and res["error_code"] == "NOT_FOUND"


@pytest.mark.asyncio
async def test_unknown_tool_name_is_structured_error():
    async with SessionLocal() as db:
        w = await build_world(db)
        rep = await load_user(db, w["rep_a"])
        res = await ToolExecutor(rep, db).call("set_price_directly", {})
        assert res["error_code"] == "UNKNOWN_TOOL"


@pytest.mark.asyncio
async def test_configuration_session_for_another_product_is_rejected():
    async with SessionLocal() as db:
        w = await build_world(db)
        rep = await load_user(db, w["rep_a"])
        session = await ConfigurationService(db).create_session(w["product_id"], rep.id, [])
        await db.commit()
        session_id, session_valid = str(session.id), session.is_valid  # read before any rollback expires it
        res = await ToolExecutor(rep, db).call("price_item", {"product_id": w["product_id"] + 10_000, "quantity": 1, "configuration_session_id": session_id})
        assert res["ok"] is False and res["error_code"] == "INVALID_CONFIGURATION", res
        same = await ToolExecutor(rep, db).call("price_item", {"product_id": w["product_id"], "quantity": 1, "configuration_session_id": session_id})
        assert same["ok"] is session_valid, same


# ─── Policy hook ────────────────────────────────────────────────────────────

class _DenyAll:
    async def check_line(self, user, quote, line):
        return Deny("Discount above the allowed limit")


class _NeedApproval:
    async def check_line(self, user, quote, line):
        return NeedsApproval("Requires manager approval")


@pytest.mark.asyncio
@pytest.mark.parametrize("policy, code", [(_DenyAll(), "POLICY_DENIED"), (_NeedApproval(), "NEEDS_APPROVAL")])
async def test_policy_blocks_line_without_writing(policy, code):
    async with SessionLocal() as db:
        w = await build_world(db)
        rep = await load_user(db, w["rep_a"])
        before = (await db.execute(select(func.count()).select_from(QuoteLineItem).where(QuoteLineItem.quote_id == w["quote_a"]))).scalar()
        res = await ToolExecutor(rep, db, policy_checker=policy).call("add_quote_item", {"quote_id": w["quote_a"], "product_id": w["product_id"], "quantity": 1})
        assert res["ok"] is False and res["error_code"] == code
        after = (await db.execute(select(func.count()).select_from(QuoteLineItem).where(QuoteLineItem.quote_id == w["quote_a"]))).scalar()
        assert before == after


@pytest.mark.asyncio
async def test_default_policy_allows():
    async with SessionLocal() as db:
        w = await build_world(db)
        rep = await load_user(db, w["rep_a"])
        res = await ToolExecutor(rep, db).call("add_quote_item", {"quote_id": w["quote_a"], "product_id": w["product_id"], "quantity": 1})
        assert res["ok"] is True, res


# ─── Trace and schemas ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_trace_records_every_call_with_outcome():
    async with SessionLocal() as db:
        w = await build_world(db)
        rep = await load_user(db, w["rep_a"])
        ex = ToolExecutor(rep, db)
        await ex.call("get_quote", {"quote_id": w["quote_a"]})
        await ex.call("get_quote", {"quote_id": w["quote_b"]})
        assert [t.tool for t in ex.trace] == ["get_quote", "get_quote"]
        assert [t.ok for t in ex.trace] == [True, False]
        assert ex.trace[1].error_code == "FORBIDDEN"
        assert all(t.duration_ms >= 0 for t in ex.trace)


@pytest.mark.asyncio
async def test_json_schemas_cover_every_tool_and_price_input_is_closed():
    async with SessionLocal() as db:
        w = await build_world(db)
        rep = await load_user(db, w["rep_a"])
        schemas = ToolExecutor(rep, db).json_schemas()
        assert sorted(s["function"]["name"] for s in schemas) == sorted(TOOL_NAMES)
        price = next(s for s in schemas if s["function"]["name"] == "price_item")["function"]["parameters"]
        assert set(price["properties"]) == {"product_id", "quantity", "discount_percent", "configuration_session_id"}
        assert price.get("additionalProperties") is False
