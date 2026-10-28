from fastapi import APIRouter, Depends, status
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.core.database import get_db
from backend.app.domains.auth.dependencies import get_current_user, PermissionChecker
from backend.app.domains.auth.models import User
from backend.app.domains.email.schemas import SendEmailRequest, EmailLogRead
from backend.app.domains.email.services import EmailService

router = APIRouter(prefix="/emails", tags=["email-dispatcher"])

@router.get("/status")
async def email_status(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Whether outbound SMTP delivery is configured on the server.
    """
    return EmailService(db).status()

@router.post("/send", response_model=EmailLogRead, status_code=status.HTTP_201_CREATED)
async def send_quote_proposal(
    request: SendEmailRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker("quotes.export"))
):
    """
    Send proposal email with latest generated PDF quote attachment.
    The returned log has status 'sent' or 'failed' (with error_message).
    """
    service = EmailService(db)
    log = await service.send_quote_email(request, current_user)
    await db.commit()
    return log

@router.get("/quote/{quote_id}", response_model=List[EmailLogRead])
async def list_quote_emails(
    quote_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Retrieve all outbound email audit logs sent for a specific quote ID.
    """
    service = EmailService(db)
    await service.quote_service.get_quote(quote_id, current_user)
    return await service.email_repo.list_for_quote(quote_id)
