"""Customer-facing proposal endpoints. Authenticated only by the unguessable share token in the URL."""
import secrets
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.config import settings
from backend.app.core.database import get_db
from backend.app.core.exceptions import DomainValidationError, EntityNotFoundError
from backend.app.domains.auth.dependencies import PermissionChecker
from backend.app.domains.auth.models import User
from backend.app.domains.document.models import QuoteDocument
from backend.app.domains.quotes.models import Quote, QuoteStatus
from backend.app.domains.quotes.services import QuoteService, _status_str

public_router = APIRouter(prefix="/public/proposals", tags=["customer-proposal"])
share_router = APIRouter(prefix="/quotes", tags=["quotes-builder"])

SHAREABLE = {QuoteStatus.APPROVED.value, QuoteStatus.SENT.value, QuoteStatus.ACCEPTED.value}
RESPONDABLE = {QuoteStatus.APPROVED.value, QuoteStatus.SENT.value}


class ShareLink(BaseModel):
    token: str
    url: str


class ProposalLine(BaseModel):
    product_name: Optional[str]
    sku: Optional[str]
    billing_type: str
    quantity: int
    unit_price: str
    discount_percentage: str
    total_price: str


class ProposalView(BaseModel):
    company_name: str
    quote_number: str
    version: int
    title: Optional[str]
    description: Optional[str]
    customer_name: str
    status: str
    currency: str
    valid_until: Optional[datetime]
    lines: List[ProposalLine]
    subtotal: str
    discount_amount: str
    tax_label: Optional[str]
    tax_amount: str
    total_amount: str
    notes: Optional[str]
    terms: str
    has_pdf: bool
    can_respond: bool
    responded_by: Optional[str] = None
    responded_at: Optional[datetime] = None


class AcceptBody(BaseModel):
    name: str = Field(..., min_length=2, max_length=255, description="Full name of the person accepting")
    note: Optional[str] = Field(default=None, max_length=2000)


class DeclineBody(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    reason: Optional[str] = Field(default=None, max_length=2000)


def share_url(token: str) -> str:
    return f"{settings.FRONTEND_URL}/proposal/{token}"


async def ensure_share_token(db: AsyncSession, quote: Quote) -> str:
    if not quote.share_token:
        quote.share_token = secrets.token_urlsafe(24)
        db.add(quote)
        await db.flush()
    return quote.share_token


@share_router.post("/{quote_id}/share", response_model=ShareLink)
async def create_share_link(
    quote_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker("quotes.export")),
):
    """Create (or return) the customer-facing proposal link for an approved/sent/accepted quote."""
    qs = QuoteService(db)
    quote = await qs.get_quote(quote_id, current_user)
    if _status_str(quote.status) not in SHAREABLE:
        raise DomainValidationError("Only approved quotes can be shared with the customer.")
    token = await ensure_share_token(db, quote)
    await db.commit()
    return ShareLink(token=token, url=share_url(token))


async def _by_token(db: AsyncSession, token: str) -> Quote:
    quote = (await db.execute(select(Quote).where(Quote.share_token == token))).scalars().first()
    if not quote or _status_str(quote.status) not in SHAREABLE | {QuoteStatus.REJECTED.value, QuoteStatus.EXPIRED.value}:
        raise EntityNotFoundError("This proposal link is not valid.")
    return quote


def _can_respond(quote: Quote) -> bool:
    if _status_str(quote.status) not in RESPONDABLE:
        return False
    return not (quote.valid_until and quote.valid_until < datetime.now(timezone.utc))


async def _latest_pdf(db: AsyncSession, quote_id: int) -> Optional[Path]:
    doc = (await db.execute(
        select(QuoteDocument).where(QuoteDocument.quote_id == quote_id).order_by(QuoteDocument.generated_at.desc())
    )).scalars().first()
    if doc and Path(doc.file_path).is_file():
        return Path(doc.file_path)
    return None


@public_router.get("/{token}", response_model=ProposalView)
async def view_proposal(token: str, db: AsyncSession = Depends(get_db)):
    quote = await _by_token(db, token)
    cust = quote.customer
    return ProposalView(
        company_name=settings.COMPANY_NAME, quote_number=quote.quote_number, version=quote.version, title=quote.title,
        description=quote.description, customer_name=(cust.display_name or cust.legal_name) if cust else "",
        status=_status_str(quote.status), currency=quote.currency, valid_until=quote.valid_until,
        lines=[ProposalLine(
            product_name=i.product_name, sku=i.sku, billing_type=i.billing_type, quantity=i.quantity,
            unit_price=f"{i.unit_price:.2f}", discount_percentage=f"{i.discount_percentage:.1f}", total_price=f"{i.total_price:.2f}",
        ) for i in quote.items],
        subtotal=f"{quote.subtotal:.2f}", discount_amount=f"{quote.discount_amount:.2f}", tax_label=quote.tax_label,
        tax_amount=f"{quote.tax_amount:.2f}", total_amount=f"{quote.total_amount:.2f}", notes=quote.notes,
        terms=settings.QUOTE_TERMS, has_pdf=await _latest_pdf(db, quote.id) is not None, can_respond=_can_respond(quote),
        responded_by=quote.customer_response_name, responded_at=quote.customer_responded_at,
    )


@public_router.get("/{token}/pdf")
async def proposal_pdf(token: str, db: AsyncSession = Depends(get_db)):
    quote = await _by_token(db, token)
    path = await _latest_pdf(db, quote.id)
    if not path:
        raise EntityNotFoundError("No PDF is available for this proposal.")
    return FileResponse(path, media_type="application/pdf", filename=f"{quote.quote_number}.pdf")


async def _respond(db: AsyncSession, token: str, name: str, note: Optional[str], accept: bool) -> ProposalView:
    quote = await _by_token(db, token)
    if not _can_respond(quote):
        raise DomainValidationError("This proposal can no longer be accepted or declined (already answered or expired).")
    before = _status_str(quote.status)
    quote.status = QuoteStatus.ACCEPTED if accept else QuoteStatus.REJECTED
    quote.customer_response_name = name.strip()
    quote.customer_response_note = note
    quote.customer_responded_at = datetime.now(timezone.utc)
    db.add(quote)
    qs = QuoteService(db)
    await qs.quote_repo.log_audit(
        quote_id=quote.id, action="QUOTE_ACCEPTED_BY_CUSTOMER" if accept else "QUOTE_DECLINED_BY_CUSTOMER", user_id=None, user_role="Customer",
        before_value={"status": before}, after_value={"status": _status_str(quote.status), "responded_by": name.strip(), "note": note},
    )
    await db.flush()
    await qs.emit_event("quote.accepted" if accept else "quote.rejected", quote)
    await db.commit()
    return await view_proposal(token, db)


@public_router.post("/{token}/accept", response_model=ProposalView)
async def accept_proposal(token: str, body: AcceptBody, db: AsyncSession = Depends(get_db)):
    return await _respond(db, token, body.name, body.note, accept=True)


@public_router.post("/{token}/decline", response_model=ProposalView)
async def decline_proposal(token: str, body: DeclineBody, db: AsyncSession = Depends(get_db)):
    return await _respond(db, token, body.name, body.reason, accept=False)
