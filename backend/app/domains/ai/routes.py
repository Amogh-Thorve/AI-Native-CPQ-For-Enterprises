from typing import List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
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

from backend.app.core.config import settings
from backend.app.domains.ai.llm import Message, Orchestrator, ProviderError, build_provider
from backend.app.domains.ai.tools import ToolExecutor
from backend.app.domains.approval.checker import ApprovalPolicyChecker


class ChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4000)


class QuoteAssistantRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    history: List[ChatTurn] = Field(default_factory=list, max_length=20)


class QuoteAssistantResponse(BaseModel):
    reply: str
    trace: List[dict]
    quote_id: Optional[int] = None
    stopped_reason: str
    usage: dict
    model_version: str = ""

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


@router.post("/quote-assistant", response_model=QuoteAssistantResponse)
async def quote_assistant(
    body: QuoteAssistantRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Natural-language quoting. The model may call tools; every tool runs as the caller, so ownership,
    RBAC and masking apply. Stateless: the client sends prior text turns in `history`.
    """
    model = settings.LLM_MODEL or settings.GEMINI_MODEL
    try:
        provider = build_provider(settings.LLM_PROVIDER, api_key=settings.GEMINI_API_KEY, model=model, base_url=settings.LLM_BASE_URL)
    except ProviderError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    if provider is None:
        raise HTTPException(status_code=503, detail="The quote assistant is not configured. Set LLM_PROVIDER in backend/.env.")

    executor = ToolExecutor(current_user, db, policy_checker=ApprovalPolicyChecker(db))
    history = [Message(role=t.role, content=t.content) for t in body.history]
    result = await Orchestrator(provider, executor).run(body.message, history)
    return QuoteAssistantResponse(
        reply=result.reply, trace=result.trace, quote_id=result.quote_id,
        stopped_reason=result.stopped_reason, usage=result.usage, model_version=result.model_version,
    )

