"""
The twelve tools. Each handler calls application services only (never routes or repositories) and
converts the result to its output model. Handlers do not commit; the executor owns the transaction.
"""
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Awaitable, Callable, List, Optional, Type

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.domains.ai.tools import schemas as s
from backend.app.domains.ai.tools.policy import Allow, Deny, NeedsApproval
from backend.app.domains.auth.models import User
from backend.app.domains.catalog.services import CatalogService
from backend.app.domains.configuration.schemas import SelectionItem, ValidateConfigurationRequest
from backend.app.domains.configuration.services import ConfigurationService
from backend.app.domains.customer.services import CustomerService
from backend.app.domains.pricing.api.schemas import CalculatePriceRequest
from backend.app.domains.pricing.application.services import PricingApplicationService
from backend.app.domains.quotes.schemas import QuoteCreate, QuoteLineItemCreate, QuoteLineItemUpdate
from backend.app.domains.quotes.services import QuoteService


class ToolError(Exception):
    """A tool failed in a way the caller should see as a structured error."""

    def __init__(self, error_code: str, message: str):
        super().__init__(message)
        self.error_code = error_code
        self.message = message


@dataclass
class ToolContext:
    db: AsyncSession
    user: User
    permissions: set
    role: str
    enforce_policy: bool
    policy: Any


Handler = Callable[[ToolContext, Any], Awaitable[BaseModel]]


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    permission: str
    input_model: Type[BaseModel]
    output_model: Type[BaseModel]
    handler: Handler
    write: bool = False


# ─── Helpers ────────────────────────────────────────────────────────────────

def _sv(value: Any) -> str:
    return value.value if hasattr(value, "value") else str(value)


def _quote_out(q) -> s.QuoteOut:
    return s.QuoteOut(
        id=q.id, quote_number=q.quote_number, version=q.version, status=_sv(q.status), customer_id=q.customer_id,
        title=q.title, currency=q.currency, valid_until=q.valid_until, subtotal=q.subtotal,
        discount_amount=q.discount_amount, tax_amount=q.tax_amount, total_amount=q.total_amount,
        margin_percentage=q.margin_percentage,
        items=[s.LineOut.model_validate(i, from_attributes=True) for i in q.items],
    )


async def _load_quote(ctx: ToolContext, quote_id: int):
    """Reads the quote as the caller (ownership applies), then reloads its lines after a write."""
    quote = await QuoteService(ctx.db).get_quote(quote_id, ctx.user)
    await ctx.db.refresh(quote, attribute_names=["items"])
    return quote


async def _check_session(ctx: ToolContext, product_id: int, session_id: Optional[uuid.UUID]) -> Optional[str]:
    if session_id is None:
        return None
    session = await ConfigurationService(ctx.db).get_session(session_id)
    is_admin = "configuration.admin" in ctx.permissions
    if session.user_id and session.user_id != ctx.user.id and not is_admin:
        raise ToolError("FORBIDDEN", "That configuration session belongs to another user.")
    if session.product_id != product_id:
        raise ToolError("INVALID_CONFIGURATION", "The configuration session is for a different product.")
    if not session.is_valid:
        raise ToolError("INVALID_CONFIGURATION", "The configuration session has not passed validation.")
    return str(session_id)


async def _line_check(ctx: ToolContext, quote, line_input) -> None:
    if not ctx.enforce_policy:
        return
    decision = await ctx.policy.check_line(ctx.user, quote, line_input)
    if isinstance(decision, Deny):
        raise ToolError("POLICY_DENIED", decision.reason)
    if isinstance(decision, NeedsApproval):
        raise ToolError("NEEDS_APPROVAL", decision.reason)
    assert isinstance(decision, Allow)


# ─── Catalog and customers ──────────────────────────────────────────────────

async def search_products(ctx: ToolContext, a: s.SearchProductsIn) -> s.ProductListOut:
    rows = await CatalogService(ctx.db).list_products(
        limit=a.limit, offset=0, category_id=a.category_id, search=a.query,
        is_active=True if a.active_only else None,
    )
    return s.ProductListOut(items=[s.ProductOut.model_validate(p, from_attributes=True) for p in rows])


async def get_customer(ctx: ToolContext, a: s.GetCustomerIn) -> s.CustomerOut:
    customer = await CustomerService(ctx.db).get_customer(ctx.user.id, a.customer_id, current_user=ctx.user)
    return s.CustomerOut.model_validate(customer, from_attributes=True)


async def list_customers(ctx: ToolContext, a: s.ListCustomersIn) -> s.CustomerListOut:
    page = await CustomerService(ctx.db).list_customers(
        ctx.user.id, page=a.page, page_size=a.page_size, status=a.status,
        customer_type=a.customer_type, industry=a.industry, current_user=ctx.user,
    )
    return s.CustomerListOut(
        items=[s.CustomerOut.model_validate(c, from_attributes=True) for c in page.items],
        total=page.total, page=page.page, page_size=page.page_size,
    )


# ─── Configuration and pricing ──────────────────────────────────────────────

async def validate_configuration(ctx: ToolContext, a: s.ValidateConfigurationIn) -> s.ValidateConfigurationOut:
    request = ValidateConfigurationRequest(
        product_id=a.product_id,
        selections=[SelectionItem(group_id=x.group_id, option_ids=x.option_ids) for x in a.selections],
    )
    result = await ConfigurationService(ctx.db).validate_configuration(request)
    return s.ValidateConfigurationOut(
        valid=result.valid,
        errors=[s.ConfigErrorOut(rule_type=e.rule_type, message=e.message) for e in result.errors],
        warnings=list(result.warnings),
    )


async def price_item(ctx: ToolContext, a: s.PriceItemIn) -> s.PriceOut:
    session = await _check_session(ctx, a.product_id, a.configuration_session_id)
    res = await PricingApplicationService(ctx.db).calculate_price(
        request=CalculatePriceRequest(product_id=a.product_id, quantity=a.quantity, discount_percent=a.discount_percent),
        user_permissions=ctx.permissions, user_id=ctx.user.id, user_role=ctx.role,
    )
    return s.PriceOut(
        product_id=res.product_id, sku=res.sku, quantity=res.quantity, pricing_method=_sv(res.pricing_method),
        billing_type=res.billing_type, currency=res.currency, base_unit_price=res.base_unit_price,
        discount_percent=res.discount_percent, final_unit_price=res.final_unit_price, total_price=res.total_price,
        unit_cost=res.unit_cost, total_cost=res.total_cost, margin_amount=res.margin_amount,
        margin_percentage=res.margin_percentage,
        configuration_session_id=uuid.UUID(session) if session else None,
    )


# ─── Quotes ─────────────────────────────────────────────────────────────────

async def create_quote(ctx: ToolContext, a: s.CreateQuoteIn) -> s.QuoteOut:
    items: List[QuoteLineItemCreate] = []
    for item in a.items:
        session = await _check_session(ctx, item.product_id, item.configuration_session_id)
        items.append(QuoteLineItemCreate(
            product_id=item.product_id, quantity=item.quantity, discount_percentage=item.discount_percent,
            configuration_id=session,
        ))
    valid_until = datetime.now(timezone.utc) + timedelta(days=a.valid_days) if a.valid_days else None
    service = QuoteService(ctx.db)
    quote = await service.create_quote(
        creator_id=ctx.user.id,
        schema=QuoteCreate(customer_id=a.customer_id, title=a.title, currency=a.currency, valid_until=valid_until, items=items),
        current_user=ctx.user,
    )
    return _quote_out(await _load_quote(ctx, quote.id))


async def add_quote_item(ctx: ToolContext, a: s.AddQuoteItemIn) -> s.QuoteOut:
    quote = await QuoteService(ctx.db).get_quote(a.quote_id, ctx.user)
    await _line_check(ctx, quote, a)
    session = await _check_session(ctx, a.product_id, a.configuration_session_id)
    await QuoteService(ctx.db).add_item(
        a.quote_id,
        QuoteLineItemCreate(product_id=a.product_id, quantity=a.quantity, discount_percentage=a.discount_percent, configuration_id=session),
        current_user=ctx.user,
    )
    return _quote_out(await _load_quote(ctx, a.quote_id))


async def update_quote_item(ctx: ToolContext, a: s.UpdateQuoteItemIn) -> s.QuoteOut:
    quote = await QuoteService(ctx.db).get_quote(a.quote_id, ctx.user)
    await _line_check(ctx, quote, a)
    await QuoteService(ctx.db).update_item(
        a.quote_id, a.item_id,
        QuoteLineItemUpdate(quantity=a.quantity, discount_percentage=a.discount_percent),
        current_user=ctx.user,
    )
    return _quote_out(await _load_quote(ctx, a.quote_id))


async def remove_quote_item(ctx: ToolContext, a: s.RemoveQuoteItemIn) -> s.QuoteOut:
    await QuoteService(ctx.db).delete_item(a.quote_id, a.item_id, current_user=ctx.user)
    return _quote_out(await _load_quote(ctx, a.quote_id))


async def get_quote(ctx: ToolContext, a: s.QuoteRefIn) -> s.QuoteOut:
    quote = await QuoteService(ctx.db).get_quote(a.quote_id, ctx.user)
    await ctx.db.refresh(quote, attribute_names=["items"])
    return _quote_out(quote)


async def submit_quote(ctx: ToolContext, a: s.QuoteRefIn) -> s.QuoteOut:
    await QuoteService(ctx.db).submit_quote(a.quote_id, current_user=ctx.user)
    return _quote_out(await _load_quote(ctx, a.quote_id))


async def revise_quote(ctx: ToolContext, a: s.QuoteRefIn) -> s.QuoteOut:
    revised = await QuoteService(ctx.db).revise_quote(a.quote_id, current_user=ctx.user)
    return _quote_out(await _load_quote(ctx, revised.id))


# ─── Registry ───────────────────────────────────────────────────────────────

TOOLS: List[Tool] = [
    Tool("search_products", "Search active catalog products by name or SKU. Returns list prices.",
         "catalog.read", s.SearchProductsIn, s.ProductListOut, search_products),
    Tool("get_customer", "Get one customer account you are allowed to see.",
         "customers.read", s.GetCustomerIn, s.CustomerOut, get_customer),
    Tool("list_customers", "List customer accounts you are allowed to see, with optional filters.",
         "customers.read", s.ListCustomersIn, s.CustomerListOut, list_customers),
    Tool("validate_configuration", "Check a product configuration (option selections) against its rules.",
         "configuration.configure", s.ValidateConfigurationIn, s.ValidateConfigurationOut, validate_configuration),
    Tool("price_item", "Price one product for a quantity and discount, optionally tied to a validated configuration session. Prices are computed, never supplied.",
         "pricing.calculate", s.PriceItemIn, s.PriceOut, price_item),
    Tool("create_quote", "Create a draft quote for a customer, optionally with initial product lines.",
         "quotes.create", s.CreateQuoteIn, s.QuoteOut, create_quote, write=True),
    Tool("add_quote_item", "Add a product line to a draft quote. Price is computed by the pricing engine.",
         "quotes.update", s.AddQuoteItemIn, s.QuoteOut, add_quote_item, write=True),
    Tool("update_quote_item", "Change the quantity or discount percent of a draft quote line.",
         "quotes.update", s.UpdateQuoteItemIn, s.QuoteOut, update_quote_item, write=True),
    Tool("remove_quote_item", "Remove a line from a draft quote.",
         "quotes.update", s.RemoveQuoteItemIn, s.QuoteOut, remove_quote_item, write=True),
    Tool("get_quote", "Get a quote and its lines that you are allowed to see.",
         "quotes.read", s.QuoteRefIn, s.QuoteOut, get_quote),
    Tool("submit_quote", "Submit a draft quote. Discount policies may route it for approval.",
         "quotes.update", s.QuoteRefIn, s.QuoteOut, submit_quote, write=True),
    Tool("revise_quote", "Create a new draft revision of an existing quote.",
         "quotes.create", s.QuoteRefIn, s.QuoteOut, revise_quote, write=True),
]

TOOL_BY_NAME = {t.name: t for t in TOOLS}
