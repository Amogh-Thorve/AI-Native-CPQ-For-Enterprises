"""
Deal intelligence and the pipeline copilot.

Win probability and discount guidance are computed from the organisation's real decided quotes
(accepted vs rejected/expired), not from a model guess; the LLM, when configured, only narrates.
"""
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional

from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.domains.approval.models import ApprovalPolicy, ApprovalRequest, ApprovalStatus
from backend.app.domains.auth.models import User
from backend.app.domains.customer.models import Contact
from backend.app.domains.quotes.models import Quote, QuoteStatus

WON = QuoteStatus.ACCEPTED.value
LOST = (QuoteStatus.REJECTED.value, QuoteStatus.EXPIRED.value)
OPEN = (QuoteStatus.DRAFT.value, QuoteStatus.SUBMITTED.value, QuoteStatus.APPROVED.value, QuoteStatus.SENT.value)
BANDS = [(0, 5), (5, 10), (10, 20), (20, 101)]


def _sv(v: Any) -> str:
    return v.value if hasattr(v, "value") else str(v)


def _peak_discount(q: Quote) -> float:
    return max((float(i.discount_percentage or 0) for i in q.items), default=0.0)


def _band(d: float) -> int:
    for idx, (lo, hi) in enumerate(BANDS):
        if lo <= d < hi:
            return idx
    return len(BANDS) - 1


def _band_label(idx: int) -> str:
    lo, hi = BANDS[idx]
    return f"{lo}%+" if hi > 100 else f"{lo}-{hi}%"


class BandStat(BaseModel):
    band: str
    decided: int
    won: int
    win_rate: Optional[float]


class DealInsights(BaseModel):
    quote_id: int
    quote_number: str
    win_probability: Optional[float]  # 0-100, None when there is no history to learn from
    confidence: str  # none | low | medium | high
    decided_quotes_used: int
    current_discount: float
    discount_bands: List[BandStat]
    discount_guidance: Optional[str]
    risks: List[str]
    next_actions: List[str]
    narrative: str
    source: str


class AskRequest(BaseModel):
    question: str


class AskResponse(BaseModel):
    answer: str
    source: str
    facts: Dict[str, Any] = {}


async def deal_insights(ai, quote_id: int, user: User) -> DealInsights:
    db: AsyncSession = ai.db
    quote = await ai.quote_service.get_quote(quote_id, user)
    show_margin = ai._can_see_margin(user)

    decided = list((await db.execute(
        select(Quote).where(Quote.status.in_([WON, *LOST]), Quote.id != quote.id)
    )).scalars().all())
    won = [q for q in decided if _sv(q.status) == WON]
    base_rate = (len(won) + 1) / (len(decided) + 2) if decided else None

    stats = [[0, 0] for _ in BANDS]  # decided, won
    for q in decided:
        b = _band(_peak_discount(q))
        stats[b][0] += 1
        stats[b][1] += 1 if _sv(q.status) == WON else 0
    bands = [BandStat(band=_band_label(i), decided=d, won=w, win_rate=round(w / d * 100, 1) if d else None) for i, (d, w) in enumerate(stats)]

    cur_disc = _peak_discount(quote)
    cb = _band(cur_disc)
    cust_decided = [q for q in decided if q.customer_id == quote.customer_id]
    cust_won = sum(1 for q in cust_decided if _sv(q.status) == WON)

    probability: Optional[float] = None
    if decided:
        band_rate = (stats[cb][1] + 1) / (stats[cb][0] + 2)
        cust_rate = (cust_won + 1) / (len(cust_decided) + 2)
        probability = round((0.6 * band_rate + 0.25 * base_rate + 0.15 * cust_rate) * 100, 1)
    n = len(decided)
    confidence = "none" if n == 0 else "low" if n < 10 else "medium" if n < 30 else "high"

    guidance: Optional[str] = None
    rated = [(i, (w + 1) / (d + 2)) for i, (d, w) in enumerate(stats) if d >= 3]
    if len(rated) >= 2:
        best = max(r for _, r in rated)
        sweet = min(i for i, r in rated if r >= best - 0.05)
        guidance = (f"Historically the best win rates occur at {_band_label(sweet)} discount; deeper discounts have not improved wins."
                    if sweet < cb else f"Current {cur_disc:.1f}% discount sits within the range with the best historical win rate.")

    risks: List[str] = []
    actions: List[str] = []
    status_val = _sv(quote.status)
    if show_margin and quote.margin_percentage is not None and quote.items and Decimal(quote.margin_percentage) < 20:
        risks.append(f"Blended margin is {Decimal(quote.margin_percentage):.1f}%, below a 20% guardrail.")
        actions.append("Reduce discounts or review line costs before sending.")
    policies = list((await db.execute(select(ApprovalPolicy).where(ApprovalPolicy.is_active.is_(True)))).scalars().all())
    for p in policies:
        if getattr(p, "policy_type", "DISCOUNT") == "DISCOUNT" and cur_disc >= float(p.discount_threshold) and status_val == QuoteStatus.DRAFT.value:
            risks.append(f"Discount of {cur_disc:.1f}% will require '{p.name}' approval ({p.role_required}).")
    pending = (await db.execute(select(func.count()).select_from(ApprovalRequest).where(
        ApprovalRequest.quote_id == quote.id, ApprovalRequest.status == ApprovalStatus.PENDING.value))).scalar() or 0
    if pending:
        risks.append(f"{pending} approval request(s) are still pending.")
        actions.append("Chase the approver; the quote cannot be sent until approved.")
    if quote.valid_until:
        days = (quote.valid_until - datetime.now(timezone.utc)).days
        if status_val in OPEN and days < 0:
            risks.append("The quote has passed its validity date.")
            actions.append("Revise the quote with a new validity date.")
        elif status_val in OPEN and days <= 7:
            risks.append(f"The quote expires in {days} day(s).")
            actions.append("Follow up with the customer before it lapses.")
    contact = (await db.execute(select(Contact).where(Contact.customer_id == quote.customer_id).limit(1))).scalars().first()
    if not contact and not (quote.customer and quote.customer.email):
        risks.append("No contact or email is on file for this customer.")
        actions.append("Add a primary contact so the proposal can be emailed.")
    if status_val == QuoteStatus.APPROVED.value:
        actions.append("Generate the PDF and send the proposal to the customer.")
    if status_val == QuoteStatus.SENT.value:
        actions.append("Follow up with the customer; share the online acceptance link.")
    if status_val == QuoteStatus.DRAFT.value and quote.items:
        actions.append("Submit for approval once pricing is final.")
    if not quote.items:
        risks.append("The quote has no line items.")

    facts = "\n".join([
        f"Quote {quote.quote_number} status {status_val}, total {quote.currency} {quote.total_amount:.2f}, peak discount {cur_disc:.1f}%",
        f"Win probability estimate: {probability if probability is not None else 'n/a'}% from {n} decided quotes ({confidence} confidence)",
        "Win rate by discount band: " + "; ".join(f"{b.band}: {b.won}/{b.decided}" for b in bands),
        f"Customer history: {cust_won} won of {len(cust_decided)} decided",
        "Risks: " + ("; ".join(risks) or "none"), "Actions: " + ("; ".join(actions) or "none"),
    ])
    llm = await ai._generate(
        "Write 2-3 plain-text sentences for a sales rep: how likely this deal is to close, the main risk, and the single best next step. "
        "Use only the numbers provided.", facts)
    if llm:
        narrative, source = llm, "gemini"
    else:
        source = "rules"
        if probability is None:
            narrative = "There are no won or lost quotes yet, so a win probability cannot be estimated. " + (risks[0] if risks else "")
        else:
            narrative = f"Estimated {probability:.0f}% chance to close ({confidence} confidence, based on {n} past outcomes). " + \
                        (risks[0] + " " if risks else "No major risks detected. ") + (f"Next: {actions[0]}" if actions else "")
    return DealInsights(
        quote_id=quote.id, quote_number=quote.quote_number, win_probability=probability, confidence=confidence,
        decided_quotes_used=n, current_discount=round(cur_disc, 1), discount_bands=bands, discount_guidance=guidance,
        risks=risks, next_actions=actions, narrative=narrative.strip(), source=source,
    )


async def ask(ai, question: str, user: User) -> AskResponse:
    """Pipeline Q&A grounded in the quotes the caller may see."""
    db: AsyncSession = ai.db
    quotes = await ai.quote_service.list_quotes(limit=100, current_user=user)
    now = datetime.now(timezone.utc)
    show_margin = ai._can_see_margin(user)
    open_q = [q for q in quotes if _sv(q.status) in OPEN]
    won_q = [q for q in quotes if _sv(q.status) == WON]

    def row(q: Quote) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "quote": q.quote_number, "customer": (q.customer.display_name or q.customer.legal_name) if q.customer else None,
            "status": _sv(q.status), "total": float(q.total_amount), "peak_discount_pct": round(_peak_discount(q), 1),
            "days_to_expiry": (q.valid_until - now).days if q.valid_until else None,
        }
        if show_margin and q.margin_percentage is not None:
            d["margin_pct"] = float(q.margin_percentage)
        return d

    pending = (await db.execute(select(func.count()).select_from(ApprovalRequest).where(ApprovalRequest.status == ApprovalStatus.PENDING.value))).scalar() or 0
    by_cust: Dict[str, float] = {}
    for q in open_q + won_q:
        name = (q.customer.display_name or q.customer.legal_name) if q.customer else f"#{q.customer_id}"
        by_cust[name] = by_cust.get(name, 0) + float(q.total_amount)
    facts: Dict[str, Any] = {
        "open_pipeline_total": round(sum(float(q.total_amount) for q in open_q), 2), "open_quotes": len(open_q),
        "won_revenue": round(sum(float(q.total_amount) for q in won_q), 2), "won_quotes": len(won_q),
        "pending_approvals": int(pending),
        "top_customers": sorted(by_cust.items(), key=lambda kv: -kv[1])[:5],
        "open_quote_list": [row(q) for q in sorted(open_q, key=lambda q: q.updated_at, reverse=True)[:25]],
    }
    import json
    llm = await ai._generate(
        "You are a CPQ sales copilot. Answer the user's question in 1-4 sentences using ONLY the JSON facts. "
        "If the facts cannot answer it, say so. Quote numbers and currency amounts exactly as given. Plain text.",
        f"QUESTION: {question}\nFACTS: {json.dumps(facts, default=str)}")
    if llm:
        return AskResponse(answer=llm, source="gemini", facts=facts)

    ql = question.lower()
    usd = lambda v: f"${v:,.2f}"
    if any(k in ql for k in ("expir", "closing", "due", "deadline", "lapse")):
        soon = sorted([r for r in facts["open_quote_list"] if r["days_to_expiry"] is not None and r["days_to_expiry"] <= 14], key=lambda r: r["days_to_expiry"])
        ans = ("Quotes expiring within 14 days: " + "; ".join(f"{r['quote']} ({r['customer']}, {r['days_to_expiry']}d)" for r in soon)) if soon else "No open quotes expire within the next 14 days."
    elif "approv" in ql:
        ans = f"There are {facts['pending_approvals']} pending approval request(s)."
    elif any(k in ql for k in ("won", "revenue", "closed")):
        ans = f"Won revenue is {usd(facts['won_revenue'])} across {facts['won_quotes']} accepted quote(s)."
    elif any(k in ql for k in ("top", "best", "biggest", "largest")) and "customer" in ql:
        ans = "Top customers by open and won value: " + "; ".join(f"{n} ({usd(v)})" for n, v in facts["top_customers"]) if facts["top_customers"] else "No quote value recorded yet."
    elif any(k in ql for k in ("discount",)):
        deep = sorted(facts["open_quote_list"], key=lambda r: -r["peak_discount_pct"])[:3]
        ans = ("Deepest discounts on open quotes: " + "; ".join(f"{r['quote']} {r['peak_discount_pct']}%" for r in deep)) if deep else "No open quotes."
    else:
        ans = (f"Open pipeline is {usd(facts['open_pipeline_total'])} across {facts['open_quotes']} quote(s); won revenue is "
               f"{usd(facts['won_revenue'])}; {facts['pending_approvals']} approval(s) are pending. "
               "(Free-form questions need a Gemini API key; try asking about expiring quotes, approvals, revenue, top customers or discounts.)")
    return AskResponse(answer=ans, source="rules", facts=facts)
