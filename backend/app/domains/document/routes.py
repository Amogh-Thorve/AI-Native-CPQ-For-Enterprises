from fastapi import APIRouter, Depends, status
from fastapi.responses import FileResponse
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.core.database import get_db
from backend.app.domains.auth.dependencies import get_current_user, PermissionChecker
from backend.app.domains.auth.models import User
from backend.app.domains.document.schemas import GenerateDocumentRequest, DocumentRead
from backend.app.domains.document.services import DocumentService

router = APIRouter(prefix="/documents", tags=["documents-generation"])

@router.post("/generate", response_model=DocumentRead, status_code=status.HTTP_201_CREATED)
async def generate_document(
    request: GenerateDocumentRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker("quotes.export"))
):
    """
    Generate a formal PDF proposal for an approved sales quotation.
    """
    service = DocumentService(db)
    doc = await service.generate_pdf(creator=current_user, request=request)
    await db.commit()
    return doc

@router.get("/quote/{quote_id}", response_model=List[DocumentRead])
async def list_quote_documents(
    quote_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Retrieve all historical generated PDF proposals for a specific quote ID.
    """
    service = DocumentService(db)
    await service.quote_service.get_quote(quote_id, current_user)
    return await service.doc_repo.list_for_quote(quote_id)

@router.get("/{doc_id}/download")
async def download_document(
    doc_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Download a generated proposal PDF (access follows the parent quote's visibility rules).
    """
    service = DocumentService(db)
    path, name = await service.get_document_file(doc_id, current_user)
    return FileResponse(path, media_type="application/pdf", filename=name)
