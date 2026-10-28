"""
PolicyChecker for the AI tool layer. It projects the quote with the new line, then runs the same pure
`evaluate` the submit path uses. It never denies: an approval rule means "needs approval", not "forbidden".
"""
from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.domains.ai.tools.masking import user_permissions
from backend.app.domains.ai.tools.policy import Allow, NeedsApproval, PolicyDecision
from backend.app.domains.approval.engine import QuoteMetrics, compute_metrics, evaluate
from backend.app.domains.approval.repositories import ApprovalRepository
from backend.app.domains.approval.rules import load_rule_rows
from backend.app.domains.quotes.services import QuoteService


def projected_metrics(quote: Any, priced: Any) -> QuoteMetrics:
    line_total = Decimal(priced.total_price)
    subtotal = Decimal(quote.subtotal or 0) + line_total
    total = Decimal(quote.total_amount or 0) + line_total
    line_discounts = [Decimal(i.discount_percentage or 0) for i in quote.items] + [Decimal(priced.discount_percent)]
    margin = None
    if priced.margin_amount is not None and subtotal > 0:
        existing = sum((Decimal(i.margin_amount or 0) for i in quote.items), Decimal("0"))
        margin = (existing + Decimal(priced.margin_amount)) / subtotal * Decimal("100")
    return compute_metrics(
        subtotal=subtotal, total=total, discount_amount=Decimal(quote.discount_amount or 0),
        line_discounts=line_discounts, margin_percent=margin,
    )


class ApprovalPolicyChecker:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def check_line(self, user, quote, line) -> PolicyDecision:
        # Same pricing path as add_item, so the projected line matches what would be stored.
        role = user.roles[0].name if user.roles else "Unknown"
        priced = await QuoteService(self.db)._calculate_item_pricing(
            line.product_id, line.quantity, line.discount_percent, None, user_permissions(user), user.id, role,
        )
        rows = await load_rule_rows(ApprovalRepository(self.db))
        required = evaluate(rows, projected_metrics(quote, priced))
        if not required.requires_approval:
            return Allow()
        return NeedsApproval(
            f"Adding this line needs {required.level.name.lower().replace('_', '-')} approval. The line was not added."
        )
