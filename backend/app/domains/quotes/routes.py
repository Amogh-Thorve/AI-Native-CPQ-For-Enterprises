from typing import List, Optional
from fastapi import APIRouter, Depends, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.core.database import get_db
from backend.app.domains.auth.dependencies import get_current_user, PermissionChecker
from backend.app.domains.auth.models import User
from backend.app.domains.quotes.models import QuoteStatus
from backend.app.domains.quotes.schemas import (
    QuoteCreate, QuoteRead, QuoteUpdate,
    QuoteLineItemCreate, QuoteLineItemUpdate, QuoteLineItemRead
)
from backend.app.domains.quotes.services import QuoteService

router = APIRouter(prefix="/quotes", tags=["quotes-builder"])

@router.post("/", response_model=QuoteRead, status_code=status.HTTP_201_CREATED)
async def create_quote(
    schema: QuoteCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker("quotes.create"))
):
    """
    Onboard and validate a new sales quotation with calculated dynamic prices.
    """
    service = QuoteService(db)
    quote = await service.create_quote(creator_id=current_user.id, schema=schema, current_user=current_user)
    await db.commit()
    return await service.get_quote(quote.id, current_user=current_user)

@router.get("/", response_model=List[QuoteRead])
async def list_quotes(
    customer_id: Optional[int] = Query(None, description="Filter by customer ID"),
    status: Optional[QuoteStatus] = Query(None, description="Filter by quote status"),
    search: Optional[str] = Query(None, description="Search by quote number or title"),
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker("quotes.read"))
):
    """
    Get all quotations with filtering and RBAC visibility constraints.
    """
    service = QuoteService(db)
    return await service.list_quotes(
        customer_id=customer_id,
        status=status,
        search=search,
        limit=limit,
        offset=offset,
        current_user=current_user
    )

@router.get("/{quote_id}", response_model=QuoteRead)
async def get_quote(
    quote_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker("quotes.read"))
):
    """
    Get detailed breakdown of a quote and all component lines.
    """
    service = QuoteService(db)
    return await service.get_quote(quote_id, current_user=current_user)

@router.put("/{quote_id}", response_model=QuoteRead)
async def update_quote(
    quote_id: int,
    schema: QuoteUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker("quotes.update"))
):
    """
    Modify metadata, status, or notes on a draft quote.
    """
    service = QuoteService(db)
    quote = await service.update_quote(quote_id, schema, current_user=current_user)
    await db.commit()
    return await service.get_quote(quote.id, current_user=current_user)

@router.delete("/{quote_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_quote(
    quote_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker("quotes.delete"))
):
    """
    Delete a draft quote.
    """
    service = QuoteService(db)
    await service.delete_quote(quote_id, current_user=current_user)
    await db.commit()
    return None

@router.post("/{quote_id}/items", response_model=QuoteLineItemRead, status_code=status.HTTP_201_CREATED)
async def add_quote_item(
    quote_id: int,
    schema: QuoteLineItemCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker("quotes.update"))
):
    """
    Add a configured product to a draft quote.
    Calculates dynamic pricing via the Pricing Engine.
    """
    service = QuoteService(db)
    item = await service.add_item(quote_id, schema, current_user=current_user)
    await db.commit()
    return item

@router.put("/{quote_id}/items/{item_id}", response_model=QuoteLineItemRead)
async def update_quote_item(
    quote_id: int,
    item_id: int,
    schema: QuoteLineItemUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker("quotes.update"))
):
    """
    Update quantity, discount, or configuration for a quote line item.
    Re-evaluates Pricing Engine and updates frozen snapshot.
    """
    service = QuoteService(db)
    item = await service.update_item(quote_id, item_id, schema, current_user=current_user)
    await db.commit()
    return item

@router.delete("/{quote_id}/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_quote_item(
    quote_id: int,
    item_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker("quotes.update"))
):
    """
    Remove a line item from a draft quote.
    """
    service = QuoteService(db)
    await service.delete_item(quote_id, item_id, current_user=current_user)
    await db.commit()
    return None

@router.post("/{quote_id}/submit", response_model=QuoteRead)
async def submit_quote(
    quote_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker("quotes.update"))
):
    """
    Submit a draft quote for review/approval.
    Transitions status from DRAFT to SUBMITTED.
    """
    service = QuoteService(db)
    quote = await service.submit_quote(quote_id, current_user=current_user)
    await db.commit()
    return await service.get_quote(quote.id, current_user=current_user)

@router.post("/{quote_id}/cancel", response_model=QuoteRead)
async def cancel_quote(
    quote_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker("quotes.update"))
):
    """
    Cancel an active quotation.
    """
    service = QuoteService(db)
    quote = await service.cancel_quote(quote_id, current_user=current_user)
    await db.commit()
    return await service.get_quote(quote.id, current_user=current_user)

@router.post("/{quote_id}/revise", response_model=QuoteRead)
async def revise_quote(
    quote_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker("quotes.create"))
):
    """
    Increment quote version, cloning products with preserved snapshots and resetting status to DRAFT.
    """
    service = QuoteService(db)
    revised = await service.revise_quote(quote_id, current_user=current_user)
    await db.commit()
    return await service.get_quote(revised.id, current_user=current_user)
