"""
Natural-language quote builder.

The LLM (when configured) only EXTRACTS intent from the text (customer, product phrases, quantities, discount).
Every product and customer is then resolved against the real database, so a quote can never contain an
invented product. Without an API key a deterministic regex extractor feeds the same resolver.
"""
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.exceptions import DomainValidationError
from backend.app.domains.auth.models import User
from backend.app.domains.catalog.models import Product
from backend.app.domains.customer.models import Customer
from backend.app.domains.quotes.schemas import QuoteCreate, QuoteLineItemCreate
from backend.app.domains.quotes.services import QuoteService

STOP = {"a", "an", "the", "of", "for", "to", "and", "with", "x", "units", "unit", "licenses", "license", "seats", "seat", "pcs", "qty", "quantity", "new", "quote", "please", "create", "make", "build", "draft"}


class QuoteFromTextRequest(BaseModel):
    prompt: str = Field(..., min_length=3, max_length=2000)
    customer_id: Optional[int] = None
    create: bool = False


class MatchedProduct(BaseModel):
    product_id: int
    sku: str
    name: str
    base_price: float
    currency: str
    billing_type: str


class ParsedLine(BaseModel):
    query: str
    quantity: int
    discount_percentage: float = 0
    matched: Optional[MatchedProduct] = None
    confidence: float = 0
    alternatives: List[MatchedProduct] = []


class QuoteFromTextResponse(BaseModel):
    source: str
    customer_id: Optional[int] = None
    customer_name: Optional[str] = None
    customer_query: Optional[str] = None
    title: Optional[str] = None
    valid_days: Optional[int] = None
    lines: List[ParsedLine] = []
    warnings: List[str] = []
    created_quote_id: Optional[int] = None
    created_quote_number: Optional[str] = None


def _tokens(text: str) -> List[str]:
    return [t for t in re.findall(r"[a-z0-9][a-z0-9\-\.]*", text.lower()) if t not in STOP and len(t) > 1]


def regex_extract(text: str) -> Dict[str, Any]:
    """Deterministic fallback extractor for prompts such as
    'Quote for Acme Corp: 10 Dell Latitude 7440, 50 cloud subscriptions with 8% discount, valid 45 days'."""
    work = text.strip()
    discount = 0.0
    m = re.search(r"(\d+(?:\.\d+)?)\s*%\s*(?:discount|off)?", work, re.I)
    if m:
        discount = min(100.0, float(m.group(1)))
        work = work[:m.start()] + " " + work[m.end():]
    work = re.sub(r"\b(?:with|and|at)?\s*(?:a\s*)?(?:discount|off)\b", " ", work, flags=re.I)
    valid_days = None
    m = re.search(r"valid\s*(?:for\s*)?(\d+)\s*days?", work, re.I)
    if m:
        valid_days = int(m.group(1))
        work = work[:m.start()] + " " + work[m.end():]
    customer = None
    m = re.search(r"\b(?:for|to)\s+([A-Z0-9][\w&.\-' ]*?)(?=\s*(?::|,|;|\s-\s|\bwith\b|\bincluding\b|\bcontaining\b|$))", work)
    if m:
        customer = m.group(1).strip()
        work = work[:m.start()] + " " + work[m.end():]
    work = re.sub(r"^\s*(?:please\s+)?(?:create|make|build|draft|prepare)?\s*(?:a\s+|an\s+)?(?:new\s+)?quote\s*", "", work, flags=re.I)
    work = re.sub(r"^[\s:,\-]+", "", work)
    parts = [p.strip(" .") for p in re.split(r",|;|\band\b|\+|\n", work) if p.strip(" .")]
    items = []
    for part in parts:
        part = re.sub(r"^(?:with|including|containing|plus|also)\s+", "", part, flags=re.I)
        part = re.sub(r"\s+(?:with|at|and)$", "", part, flags=re.I).strip()
        m = re.match(r"^(\d+)\s*(?:x|units?\s+of|licen[sc]es?\s+of|seats?\s+of|pcs?\s+of|of)?\s*(.+)$", part, re.I)
        if m:
            items.append({"query": m.group(2).strip(), "quantity": int(m.group(1)), "discount_percentage": discount})
        elif _tokens(part):
            items.append({"query": part, "quantity": 1, "discount_percentage": discount})
    return {"customer": customer, "items": items, "valid_days": valid_days, "title": None}


async def _candidates(db: AsyncSession, query: str, limit: int = 40) -> List[Product]:
    toks = _tokens(query)
    if not toks:
        return []
    conds = []
    for t in toks:
        pat = f"%{t}%"
        conds += [Product.name.ilike(pat), Product.sku.ilike(pat)]
    res = await db.execute(select(Product).where(Product.is_active.is_(True), or_(*conds)).limit(limit))
    return list(res.scalars().all())


def _score(query: str, product: Product) -> float:
    q = set(_tokens(query))
    if not q:
        return 0.0
    hay = set(_tokens(product.name)) | set(_tokens(product.sku))
    hay_text = f"{product.name} {product.sku}".lower()
    hits = sum(1 for t in q if t in hay or (len(t) >= 4 and t in hay_text))
    score = hits / len(q)
    if query.strip().lower() == product.sku.lower():
        score = 1.0
    # prefer tighter names when several products share the matched tokens
    return score - min(len(hay) / 200.0, 0.05)


def _mp(p: Product) -> MatchedProduct:
    return MatchedProduct(product_id=p.id, sku=p.sku, name=p.name, base_price=float(p.base_price), currency=p.currency, billing_type=p.billing_type)


async def resolve_product(db: AsyncSession, query: str) -> tuple[Optional[MatchedProduct], float, List[MatchedProduct]]:
    cands = await _candidates(db, query)
    ranked = sorted(((_score(query, p), p) for p in cands), key=lambda x: -x[0])
    if not ranked or ranked[0][0] < 0.5:
        return None, ranked[0][0] if ranked else 0.0, [_mp(p) for _, p in ranked[:3]]
    best_score, best = ranked[0]
    return _mp(best), round(best_score, 2), [_mp(p) for _, p in ranked[1:4]]


async def resolve_customer(db: AsyncSession, query: str, user: User, qs: QuoteService) -> Optional[Customer]:
    toks = _tokens(query)
    if not toks:
        return None
    conds = []
    for t in toks:
        conds += [Customer.legal_name.ilike(f"%{t}%"), Customer.display_name.ilike(f"%{t}%")]
    rows = list((await db.execute(select(Customer).where(Customer.deleted_at.is_(None), or_(*conds)).limit(500))).scalars().all())
    best, best_score = None, 0.0
    for c in rows:
        name_tokens = set(_tokens(f"{c.legal_name} {c.display_name or ''}"))
        score = sum(1 for t in toks if t in name_tokens) / len(toks)
        if score > best_score:
            best, best_score = c, score
    if not best or best_score < 0.5:
        return None
    try:
        await qs.customer_service.get_customer(user.id, best.id, current_user=user)  # RBAC (reps: own customers)
    except Exception:
        return None
    return best


async def build_from_text(ai, request: QuoteFromTextRequest, user: User) -> QuoteFromTextResponse:
    """`ai` is an AIService (provides the optional LLM extractor and db session)."""
    db: AsyncSession = ai.db
    qs = ai.quote_service

    extracted = await ai._generate_json(
        "Extract a sales quote request. Return JSON {\"customer\": string|null, \"title\": string|null, \"valid_days\": integer|null, "
        "\"items\": [{\"query\": product name or SKU phrase as written, \"quantity\": integer>=1, \"discount_percentage\": number 0-100}]}. "
        "Do not invent products or numbers that are not in the text.",
        request.prompt,
    )
    source = "gemini" if extracted and isinstance(extracted.get("items"), list) else "rules"
    if source == "rules":
        extracted = regex_extract(request.prompt)

    warnings: List[str] = []
    customer = None
    if request.customer_id:
        customer = await qs.customer_service.customer_repo.get_by_id(None, request.customer_id)
    elif extracted.get("customer"):
        phrase = str(extracted["customer"])
        customer = await resolve_customer(db, phrase, user, qs)
        words = phrase.split()
        while not customer and len(words) > 1:
            # the phrase may have swallowed the first product ("for Acme 10 laptops"): shrink until a customer matches
            words = words[:-1]
            customer = await resolve_customer(db, " ".join(words), user, qs)
            if customer and source == "rules":
                extracted["items"] = list(extracted.get("items") or []) + regex_extract(" ".join(phrase.split()[len(words):]))["items"]
        if not customer:
            warnings.append(f"Could not find a customer matching '{extracted['customer']}'. Pick one to continue.")
    else:
        warnings.append("No customer was mentioned. Pick one to continue.")

    lines: List[ParsedLine] = []
    for raw in extracted.get("items") or []:
        try:
            qty = max(1, int(raw.get("quantity") or 1))
            disc = max(0.0, min(100.0, float(raw.get("discount_percentage") or 0)))
            query = str(raw.get("query") or "").strip()
        except (TypeError, ValueError):
            continue
        if not query:
            continue
        matched, conf, alts = await resolve_product(db, query)
        if not matched:
            warnings.append(f"No catalog product matched '{query}'.")
        lines.append(ParsedLine(query=query, quantity=qty, discount_percentage=disc, matched=matched, confidence=conf, alternatives=alts))
    if not lines:
        warnings.append("No products were recognised in the request.")

    resp = QuoteFromTextResponse(
        source=source, customer_id=customer.id if customer else None,
        customer_name=(customer.display_name or customer.legal_name) if customer else None,
        customer_query=extracted.get("customer"), title=extracted.get("title"), valid_days=extracted.get("valid_days"),
        lines=lines, warnings=warnings,
    )

    if request.create:
        perms = {p.name for r in user.roles for p in r.permissions}
        if "quotes.create" not in perms:
            raise DomainValidationError("You do not have permission to create quotes.")
        usable = [l for l in lines if l.matched]
        if not customer:
            raise DomainValidationError("Choose a customer before creating the quote.")
        if not usable:
            raise DomainValidationError("No catalog products could be matched, so there is nothing to quote.")
        valid_until = datetime.now(timezone.utc) + timedelta(days=int(resp.valid_days or 30))
        quote = await qs.create_quote(
            creator_id=user.id,
            schema=QuoteCreate(
                customer_id=customer.id, title=resp.title or "Quote from AI request", valid_until=valid_until,
                description=f"Drafted from request: {request.prompt[:500]}",
                items=[QuoteLineItemCreate(product_id=l.matched.product_id, quantity=l.quantity, discount_percentage=l.discount_percentage) for l in usable],
            ),
            current_user=user,
        )
        resp.created_quote_id, resp.created_quote_number = quote.id, quote.quote_number
    return resp
