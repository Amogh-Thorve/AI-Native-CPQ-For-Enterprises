import os
from pathlib import Path
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.domains.document.repositories import DocumentRepository
from backend.app.domains.document.models import QuoteDocument
from backend.app.domains.document.schemas import GenerateDocumentRequest
from backend.app.domains.document.pdf_builder import build_quote_pdf
from backend.app.domains.quotes.services import QuoteService
from backend.app.domains.quotes.models import QuoteStatus
from backend.app.domains.customer.models import Contact, CustomerAddress
from backend.app.domains.auth.models import User
from backend.app.core.exceptions import DomainValidationError, EntityNotFoundError

DOCUMENT_DIR = Path("storage/documents")  # private; served only through the authenticated download endpoint
ELIGIBLE_STATUSES = {QuoteStatus.APPROVED.value, QuoteStatus.SENT.value, QuoteStatus.ACCEPTED.value}


class DocumentService:
    """
    Generates client-facing PDF proposals for approved quotes and tracks the files.
    """
    def __init__(self, db: AsyncSession):
        self.db = db
        self.doc_repo = DocumentRepository(db)
        self.quote_service = QuoteService(db)

    async def generate_pdf(self, creator: User, request: GenerateDocumentRequest) -> QuoteDocument:
        quote = await self.quote_service.get_quote(request.quote_id, creator)
        status_val = quote.status.value if hasattr(quote.status, "value") else str(quote.status)
        if status_val not in ELIGIBLE_STATUSES:
            raise DomainValidationError("Proposal PDFs can only be generated for approved quotes.")

        customer = quote.customer
        contact = (await self.db.execute(
            select(Contact).where(Contact.customer_id == customer.id).order_by(Contact.is_primary.desc(), Contact.id)
        )).scalars().first()
        address = (await self.db.execute(
            select(CustomerAddress).where(CustomerAddress.customer_id == customer.id)
            .order_by(CustomerAddress.is_primary.desc(), CustomerAddress.id)
        )).scalars().first()
        author = quote.created_by
        prepared_by = (f"{author.first_name} {author.last_name}".strip() or author.email) if author else ""

        pdf_bytes = build_quote_pdf(quote, customer, contact, address, prepared_by)

        DOCUMENT_DIR.mkdir(parents=True, exist_ok=True)
        existing = await self.doc_repo.list_for_quote(quote.id)
        file_name = f"{quote.quote_number}_v{quote.version}_{len(existing) + 1}.pdf"
        path = DOCUMENT_DIR / file_name
        path.write_bytes(pdf_bytes)

        doc = await self.doc_repo.create(quote_id=quote.id, creator_id=creator.id, file_path=str(path).replace(os.sep, "/"))
        await self.quote_service.quote_repo.log_audit(
            quote_id=quote.id, action="PROPOSAL_GENERATED", user_id=creator.id,
            after_value={"file": file_name, "size_bytes": len(pdf_bytes)},
        )
        return doc

    async def get_document_file(self, doc_id: int, user: User) -> tuple[Path, str]:
        doc = await self.doc_repo.get_by_id(doc_id)
        if not doc:
            raise EntityNotFoundError(f"Document {doc_id} not found.")
        await self.quote_service.get_quote(doc.quote_id, user)  # enforces RBAC visibility
        path = Path(doc.file_path)
        if not path.is_file():
            raise EntityNotFoundError("The PDF file is missing from storage. Please regenerate the proposal.")
        return path, path.name
