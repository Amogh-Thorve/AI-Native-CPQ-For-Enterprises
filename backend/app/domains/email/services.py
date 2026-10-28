import asyncio
import smtplib
import ssl
from email.message import EmailMessage
from pathlib import Path
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.core.config import settings
from backend.app.core.exceptions import DomainValidationError
from backend.app.domains.auth.models import User
from backend.app.domains.document.repositories import DocumentRepository
from backend.app.domains.email.models import EmailLog
from backend.app.domains.email.repositories import EmailRepository
from backend.app.domains.email.schemas import SendEmailRequest
from backend.app.domains.quotes.services import QuoteService


def smtp_configured() -> bool:
    return bool(settings.SMTP_HOST and (settings.SMTP_FROM or settings.SMTP_USERNAME))


def _deliver(message: EmailMessage) -> None:
    """Blocking SMTP delivery; run in a worker thread."""
    context = ssl.create_default_context()
    if settings.SMTP_USE_SSL:
        server = smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT, timeout=20, context=context)
    else:
        server = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=20)
    with server:
        if not settings.SMTP_USE_SSL and settings.SMTP_USE_TLS:
            server.starttls(context=context)
        if settings.SMTP_USERNAME:
            server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
        server.send_message(message)


class EmailService:
    """
    Sends proposal emails (with the latest generated PDF attached) over SMTP and audits every attempt.
    """
    def __init__(self, db: AsyncSession):
        self.db = db
        self.email_repo = EmailRepository(db)
        self.doc_repo = DocumentRepository(db)
        self.quote_service = QuoteService(db)

    def status(self) -> dict:
        return {"configured": smtp_configured(), "host": settings.SMTP_HOST or None,
                "from_address": settings.SMTP_FROM or settings.SMTP_USERNAME or None}

    async def send_quote_email(self, request: SendEmailRequest, current_user: User) -> EmailLog:
        quote = await self.quote_service.get_quote(request.quote_id, current_user)
        documents = await self.doc_repo.list_for_quote(request.quote_id)
        if not documents:
            raise DomainValidationError("Generate the PDF proposal before emailing the quote.")
        pdf_path = Path(documents[0].file_path)
        if not pdf_path.is_file():
            raise DomainValidationError("The PDF file is missing from storage. Please regenerate the proposal.")

        error_msg: Optional[str] = None
        if not smtp_configured():
            error_msg = "Email is not configured on the server (set SMTP_HOST and SMTP_FROM in backend/.env)."
        else:
            message = EmailMessage()
            message["From"] = settings.SMTP_FROM or settings.SMTP_USERNAME
            message["To"] = str(request.recipient)
            message["Subject"] = request.subject
            message["Reply-To"] = current_user.email
            message.set_content(request.body)
            message.add_attachment(pdf_path.read_bytes(), maintype="application", subtype="pdf", filename=pdf_path.name)
            try:
                await asyncio.to_thread(_deliver, message)
            except Exception as exc:  # network/auth/refused: record, don't crash the request
                error_msg = f"{type(exc).__name__}: {exc}"[:490]

        log = await self.email_repo.create_log(
            quote_id=request.quote_id, recipient=str(request.recipient), subject=request.subject,
            status="failed" if error_msg else "sent", error_message=error_msg,
        )
        await self.quote_service.quote_repo.log_audit(
            quote_id=quote.id, action="PROPOSAL_EMAILED" if not error_msg else "PROPOSAL_EMAIL_FAILED",
            user_id=current_user.id, after_value={"recipient": str(request.recipient), "error": error_msg},
        )
        if not error_msg:
            await self.quote_service.mark_sent(quote.id, current_user)
        return log
