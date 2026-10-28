from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.core.database import get_db
from backend.app.domains.auth.dependencies import get_current_user
from backend.app.domains.auth.models import User
from backend.app.domains.ai.schemas import (
    AIStatusResponse,
    CustomerSummaryRequest, CustomerSummaryResponse,
    QuoteSummaryRequest, QuoteSummaryResponse,
    EmailDraftRequest, EmailDraftResponse,
    ProductRecommendationRequest, ProductRecommendationResponse
)
from backend.app.domains.ai.services import AIService
from backend.app.domains.ai.nlquote import QuoteFromTextRequest, QuoteFromTextResponse, build_from_text
from backend.app.domains.ai.insights import AskRequest, AskResponse, DealInsights, ask as ask_copilot, deal_insights

router = APIRouter(prefix="/ai", tags=["ai-copilot"])

@router.get("/status", response_model=AIStatusResponse)
async def ai_status(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Whether a Gemini API key is configured (otherwise the data-driven fallback is used)."""
    return AIService(db).status()

@router.post("/customer-summary", response_model=CustomerSummaryResponse)
async def get_customer_summary(
    request: CustomerSummaryRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Account briefing grounded in the customer's real quote history."""
    return await AIService(db).summarize_customer(request, current_user)

@router.post("/quote-summary", response_model=QuoteSummaryResponse)
async def get_quote_summary(
    request: QuoteSummaryRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Analysis of a quote's lines, discounts, margin (if permitted) and approvals."""
    return await AIService(db).summarize_quote(request, current_user)

@router.post("/draft-email", response_model=EmailDraftResponse)
async def draft_proposal_email(
    request: EmailDraftRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Draft the cover email for a quote proposal addressed to the customer's primary contact."""
    return await AIService(db).draft_email(request, current_user)

@router.post("/recommendations", response_model=ProductRecommendationResponse)
async def get_recommendations(
    request: ProductRecommendationRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Cross-sell suggestions from co-occurrence in historical quotes."""
    return await AIService(db).recommend_products(request, current_user)


@router.post("/quote-from-text", response_model=QuoteFromTextResponse)
async def quote_from_text(
    request: QuoteFromTextRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Turn a natural-language request into a quote. Products/customers are always resolved against the real database;
    with create=true the draft quote is saved and its id returned."""
    ai = AIService(db)
    result = await build_from_text(ai, request, current_user)
    if request.create:
        await db.commit()
    return result

@router.get("/deal-insights/{quote_id}", response_model=DealInsights)
async def get_deal_insights(
    quote_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Win probability, discount guidance, risks and next actions computed from historical quote outcomes."""
    return await deal_insights(AIService(db), quote_id, current_user)

@router.post("/ask", response_model=AskResponse)
async def ask_the_copilot(
    request: AskRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Ask a question about your pipeline, grounded in the quotes you can see."""
    return await ask_copilot(AIService(db), request.question, current_user)
