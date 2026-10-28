import logging
from decimal import Decimal
from typing import Any, List, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.config import settings
from backend.app.core.exceptions import EntityNotFoundError
from backend.app.domains.ai.schemas import (
    AIStatusResponse,
    CustomerSummaryRequest, CustomerSummaryResponse,
    EmailDraftRequest, EmailDraftResponse,
    ProductRecommendationRequest, ProductRecommendationResponse, RecommendedProduct,
    QuoteSummaryRequest, QuoteSummaryResponse,
)
from backend.app.domains.auth.models import User
from backend.app.domains.catalog.models import Product
from backend.app.domains.customer.models import Contact
from backend.app.domains.customer.services import CustomerService
from backend.app.domains.quotes.models import Quote, QuoteLineItem, QuoteStatus
from backend.app.domains.quotes.services import QuoteService

logger = logging.getLogger(__name__)

WON = (QuoteStatus.ACCEPTED.value,)
OPEN = (QuoteStatus.DRAFT.value, QuoteStatus.SUBMITTED.value, QuoteStatus.APPROVED.value, QuoteStatus.SENT.value)


def _sv(v: Any) -> str:
    return v.value if hasattr(v, "value") else str(v)


def _money(v, cur="USD") -> str:
    return f"{cur} {Decimal(v or 0):,.2f}"


class AIService:
    """
    Sales copilot. Every answer is grounded in facts read from the database (quotes, lines, approvals,
    purchase history). When a Gemini API key is configured the facts are given to Gemini to write the
    narrative; otherwise a deterministic, data-driven narrative is produced and flagged source="rules".
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.quote_service = QuoteService(db)
        self.customer_service = CustomerService(db)

    # ── LLM plumbing ────────────────────────────────────────────────────────────
    def status(self) -> AIStatusResponse:
        return AIStatusResponse(gemini_configured=bool(settings.GEMINI_API_KEY), model=settings.GEMINI_MODEL)

    async def _generate(self, instruction: str, facts: str) -> Optional[str]:
        """Returns Gemini's text, or None when unavailable/failed (callers then use the rules fallback)."""
        if not settings.GEMINI_API_KEY:
            return None
        try:
            from google import genai
            from google.genai import types
            client = genai.Client(api_key=settings.GEMINI_API_KEY)
            resp = await client.aio.models.generate_content(
                model=settings.GEMINI_MODEL,
                contents=f"{instruction}\n\nFACTS (authoritative, do not invent numbers beyond these):\n{facts}",
                config=types.GenerateContentConfig(temperature=0.3, max_output_tokens=900),
            )
            text = (resp.text or "").strip()
            return text or None
        except Exception as exc:
            logger.warning("Gemini call failed, using rules fallback: %s", exc)
            return None

    async def _generate_json(self, instruction: str, facts: str) -> Optional[dict]:
        """Like _generate but requests strict JSON; returns None when unavailable or unparsable."""
        if not settings.GEMINI_API_KEY:
            return None
        try:
            import json
            from google import genai
            from google.genai import types
            client = genai.Client(api_key=settings.GEMINI_API_KEY)
            resp = await client.aio.models.generate_content(
                model=settings.GEMINI_MODEL,
                contents=f"{instruction}\n\nINPUT:\n{facts}",
                config=types.GenerateContentConfig(temperature=0.0, response_mime_type="application/json"),
            )
            data = json.loads((resp.text or "").strip())
            return data if isinstance(data, dict) else None
        except Exception as exc:
            logger.warning("Gemini JSON call failed, using rules fallback: %s", exc)
            return None

    @staticmethod
    def _can_see_margin(user: User) -> bool:
        perms = {p.name for r in user.roles for p in r.permissions}
        return "pricing.margin.view" in perms

    # ── Customer summary ────────────────────────────────────────────────────────
    async def summarize_customer(self, request: CustomerSummaryRequest, user: User) -> CustomerSummaryResponse:
        customer = await self.customer_service.customer_repo.get_by_id(None, request.customer_id)
        if not customer:
            raise EntityNotFoundError(f"Customer {request.customer_id} not found.")
        await self.customer_service.get_customer(user.id, request.customer_id, current_user=user)  # RBAC

        quotes = await self.quote_service.list_quotes(customer_id=customer.id, limit=100, current_user=user)
        won = [q for q in quotes if _sv(q.status) in WON]
        open_q = [q for q in quotes if _sv(q.status) in OPEN]
        lost = [q for q in quotes if _sv(q.status) in (QuoteStatus.REJECTED.value, QuoteStatus.EXPIRED.value, QuoteStatus.CANCELLED.value)]
        won_total = sum((q.total_amount for q in won), Decimal(0))
        open_total = sum((q.total_amount for q in open_q), Decimal(0))
        decided = len(won) + len([q for q in lost if _sv(q.status) != QuoteStatus.CANCELLED.value])
        win_rate = (len(won) / decided * 100) if decided else None

        discounts = [max((Decimal(i.discount_percentage or 0) for i in q.items), default=Decimal(0)) for q in quotes if q.items]
        avg_disc = (sum(discounts, Decimal(0)) / len(discounts)) if discounts else Decimal(0)

        product_counts: dict[str, int] = {}
        for q in won + open_q:
            for i in q.items:
                product_counts[i.product_name or i.sku or "Product"] = product_counts.get(i.product_name or i.sku or "Product", 0) + i.quantity
        top = sorted(product_counts.items(), key=lambda kv: -kv[1])[:3]

        contacts = (await self.db.execute(select(func.count()).select_from(Contact).where(Contact.customer_id == customer.id))).scalar() or 0
        name = customer.display_name or customer.legal_name

        metrics = [
            f"{len(quotes)} quote(s): {len(won)} won, {len(open_q)} open, {len(lost)} lost/expired",
            f"Won revenue: {_money(won_total)}",
            f"Open pipeline: {_money(open_total)}",
            f"Average peak discount: {avg_disc:.1f}%",
            f"Win rate: {win_rate:.0f}%" if win_rate is not None else "Win rate: no decided quotes yet",
            f"{contacts} contact(s) on file",
        ]
        facts = "\n".join([
            f"Customer: {name} | status {customer.status} | industry {customer.industry or 'n/a'} | currency {customer.currency}",
            *metrics,
            "Top products: " + (", ".join(f"{n} (x{c})" for n, c in top) or "none yet"),
        ])
        llm = await self._generate(
            "You are a CPQ sales copilot. Write a 3-4 sentence account briefing for a sales rep about this customer: "
            "relationship state, revenue, open opportunities and one concrete next action. Plain text, no markdown.", facts)
        if llm:
            return CustomerSummaryResponse(customer_id=customer.id, summary_text=llm, key_metrics=metrics, source="gemini")

        parts = [f"{name} is a {str(customer.status).lower()} {customer.industry or 'business'} account."]
        if quotes:
            parts.append(f"There are {len(quotes)} quote(s) on record with {_money(won_total)} won and {_money(open_total)} still open.")
        else:
            parts.append("No quotes have been created for this account yet.")
        if top:
            parts.append("Most quoted products: " + ", ".join(n for n, _ in top) + ".")
        if open_q:
            parts.append(f"Next step: progress the {len(open_q)} open quote(s) toward acceptance.")
        elif not quotes:
            parts.append("Next step: create a first quote for this account.")
        return CustomerSummaryResponse(customer_id=customer.id, summary_text=" ".join(parts), key_metrics=metrics)

    # ── Quote summary ───────────────────────────────────────────────────────────
    async def summarize_quote(self, request: QuoteSummaryRequest, user: User) -> QuoteSummaryResponse:
        quote = await self.quote_service.get_quote(request.quote_id, user)
        show_margin = self._can_see_margin(user)
        cur = quote.currency
        lines = []
        for i in quote.items:
            line = f"- {i.product_name} ({i.sku}) x{i.quantity} @ {_money(i.unit_price, cur)}, disc {Decimal(i.discount_percentage or 0):.1f}%, total {_money(i.total_price, cur)} [{i.billing_type}]"
            if show_margin and i.margin_percentage is not None:
                line += f", margin {Decimal(i.margin_percentage):.1f}%"
            lines.append(line)
        max_disc = max((Decimal(i.discount_percentage or 0) for i in quote.items), default=Decimal(0))

        from backend.app.domains.approval.repositories import ApprovalRepository
        reqs = await ApprovalRepository(self.db).list_requests_for_quote(quote.id)
        approvals = [f"{r.policy.name}: {_sv(r.status)} (needs {r.assigned_role})" for r in reqs]

        facts = "\n".join([
            f"Quote {quote.quote_number} v{quote.version} for {quote.customer.display_name or quote.customer.legal_name}, status {_sv(quote.status)}",
            f"Subtotal {_money(quote.subtotal, cur)}, discount {_money(quote.discount_amount, cur)}, total {_money(quote.total_amount, cur)}",
            f"Peak line discount {max_disc:.1f}%" + (f", blended margin {Decimal(quote.margin_percentage or 0):.1f}%" if show_margin else ""),
            f"Valid until: {quote.valid_until.date() if quote.valid_until else 'not set'}",
            "Lines:", *lines,
            "Approvals: " + ("; ".join(approvals) if approvals else "none required/triggered"),
        ])
        llm = await self._generate(
            "You are a CPQ analyst. Return two short paragraphs separated by a line containing only '---'. "
            "First: what the quote contains and its total. Second: pricing/discount/margin/approval risks and a recommended next step. Plain text.", facts)
        if llm:
            first, _, second = llm.partition("---")
            return QuoteSummaryResponse(quote_id=quote.id, summary_text=first.strip(), explanation=(second or first).strip(), source="gemini")

        recurring = sum((i.total_price for i in quote.items if i.billing_type == "MRC"), Decimal(0))
        summary = (f"Quote {quote.quote_number} v{quote.version} has {len(quote.items)} line(s) totalling {_money(quote.total_amount, cur)}"
                   f" ({_money(recurring, cur)} recurring) and is {_sv(quote.status)}.")
        notes = []
        if max_disc > 0:
            notes.append(f"The deepest line discount is {max_disc:.1f}%.")
        if show_margin and quote.margin_percentage is not None:
            m = Decimal(quote.margin_percentage)
            notes.append(f"Blended margin is {m:.1f}%" + (" - below a healthy 20% floor." if m < 20 else "."))
        if approvals:
            notes.append("Approvals: " + "; ".join(approvals) + ".")
        if quote.valid_until:
            notes.append(f"Valid until {quote.valid_until.date()}.")
        if not quote.items:
            notes.append("The quote has no lines yet.")
        return QuoteSummaryResponse(quote_id=quote.id, summary_text=summary, explanation=" ".join(notes) or "No pricing risks detected.")

    # ── Email draft ─────────────────────────────────────────────────────────────
    async def draft_email(self, request: EmailDraftRequest, user: User) -> EmailDraftResponse:
        quote = await self.quote_service.get_quote(request.quote_id, user)
        contact = (await self.db.execute(
            select(Contact).where(Contact.customer_id == quote.customer_id).order_by(Contact.is_primary.desc(), Contact.id)
        )).scalars().first()
        recipient = contact.email if contact else quote.customer.email
        greeting_name = contact.first_name if contact else (quote.customer.display_name or quote.customer.legal_name)
        sender = f"{user.first_name} {user.last_name}".strip() or user.email
        cur = quote.currency
        item_lines = "\n".join(f"- {i.product_name} x{i.quantity}: {_money(i.total_price, cur)}" for i in quote.items)
        subject = f"Proposal {quote.quote_number} - {quote.title or quote.customer.display_name or quote.customer.legal_name}"

        facts = "\n".join([
            f"Recipient: {greeting_name}", f"Sender: {sender}", f"Tone: {request.tone}",
            f"Quote {quote.quote_number}: total {_money(quote.total_amount, cur)}, valid until {quote.valid_until.date() if quote.valid_until else 'n/a'}",
            "Items:", item_lines, "The PDF proposal is attached.",
        ])
        llm = await self._generate(
            "Write the body of a concise sales email (no subject line) that accompanies the attached proposal PDF. "
            "Greet the recipient by first name, summarise the offer in 2-3 sentences, mention validity, invite questions, sign with the sender name. Plain text.", facts)
        if llm:
            return EmailDraftResponse(quote_id=quote.id, subject=subject, body=llm, recipient=recipient, source="gemini")

        valid = f" This proposal is valid until {quote.valid_until.strftime('%d %b %Y')}." if quote.valid_until else ""
        body = (f"Hello {greeting_name},\n\nThank you for the opportunity. Please find attached proposal {quote.quote_number} "
                f"with a total of {_money(quote.total_amount, cur)}:\n\n{item_lines}\n\n{valid.strip()}\n\n"
                f"Let me know if you have any questions or would like to adjust anything.\n\nBest regards,\n{sender}").replace("\n\n\n", "\n\n")
        return EmailDraftResponse(quote_id=quote.id, subject=subject, body=body, recipient=recipient)

    # ── Recommendations (collaborative filtering over real quote history) ───────
    async def recommend_products(self, request: ProductRecommendationRequest, user: User) -> ProductRecommendationResponse:
        customer = await self.customer_service.customer_repo.get_by_id(None, request.customer_id)
        if not customer:
            raise EntityNotFoundError(f"Customer {request.customer_id} not found.")
        await self.customer_service.get_customer(user.id, request.customer_id, current_user=user)

        owned = set(request.current_product_ids)
        own_rows = await self.db.execute(
            select(QuoteLineItem.product_id).join(Quote, Quote.id == QuoteLineItem.quote_id)
            .where(Quote.customer_id == customer.id, Quote.status != QuoteStatus.CANCELLED.value)
        )
        owned |= {r[0] for r in own_rows}

        scores: dict[int, int] = {}
        if owned:
            # quotes (from any customer) that contain at least one product we already have
            sibling = select(QuoteLineItem.quote_id).where(QuoteLineItem.product_id.in_(owned))
            rows = await self.db.execute(
                select(QuoteLineItem.product_id, func.count(func.distinct(QuoteLineItem.quote_id)))
                .join(Quote, Quote.id == QuoteLineItem.quote_id)
                .where(QuoteLineItem.quote_id.in_(sibling), QuoteLineItem.product_id.notin_(owned),
                       Quote.status.notin_([QuoteStatus.CANCELLED.value, QuoteStatus.REJECTED.value]))
                .group_by(QuoteLineItem.product_id)
            )
            scores = {pid: int(c) for pid, c in rows}
        if len(scores) < 5:
            # backfill with the most-quoted active products overall
            rows = await self.db.execute(
                select(QuoteLineItem.product_id, func.count(func.distinct(QuoteLineItem.quote_id)))
                .join(Quote, Quote.id == QuoteLineItem.quote_id)
                .where(QuoteLineItem.product_id.notin_(owned or {-1}), Quote.status.notin_([QuoteStatus.CANCELLED.value]))
                .group_by(QuoteLineItem.product_id).order_by(func.count(func.distinct(QuoteLineItem.quote_id)).desc()).limit(10)
            )
            for pid, c in rows:
                scores.setdefault(pid, int(c))

        ranked = sorted(scores.items(), key=lambda kv: -kv[1])[:5]
        products = {}
        if ranked:
            res = await self.db.execute(select(Product).where(Product.id.in_([p for p, _ in ranked]), Product.is_active.is_(True)))
            products = {p.id: p for p in res.scalars().all()}
        recs: List[RecommendedProduct] = []
        for pid, score in ranked:
            p = products.get(pid)
            if not p:
                continue
            recs.append(RecommendedProduct(
                product_id=p.id, sku=p.sku, name=p.name, base_price=float(p.base_price), currency=p.currency, score=score,
                reason=f"Appears in {score} other quote(s)" + (" alongside products this customer already buys." if owned else "; a frequently quoted product."),
            ))

        if not recs:
            return ProductRecommendationResponse(reasoning="Not enough quote history yet to make data-driven recommendations.")
        facts = f"Customer {customer.display_name or customer.legal_name} already has {len(owned)} product(s). Candidates:\n" + \
            "\n".join(f"- {r.name} ({r.sku}), {r.currency} {r.base_price:,.2f}: {r.reason}" for r in recs)
        llm = await self._generate("In 2-3 sentences explain to a sales rep why these cross-sell candidates make sense and which to lead with. Plain text.", facts)
        reasoning = llm or (f"Based on co-occurrence across {sum(r.score for r in recs)} historical quote line(s), "
                            f"lead with {recs[0].name}: {recs[0].reason}")
        return ProductRecommendationResponse(
            recommended_product_ids=[r.product_id for r in recs], recommendations=recs, reasoning=reasoning,
            source="gemini" if llm else "rules",
        )
