import json
from typing import List
from urllib.parse import quote_plus

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.config import settings
from backend.app.core.database import get_db
from backend.app.core.exceptions import DomainValidationError
from backend.app.domains.auth.dependencies import PermissionChecker, get_current_user
from backend.app.domains.auth.models import User
from backend.app.domains.integrations.schemas import (
    ColumnMapping, ImportExecuteResponse, ImportPreviewResponse,
    SalesforceAuthorizeResponse, SalesforceConnectRequest, SalesforceConnectResponse,
    SalesforceStatusResponse, SalesforceSyncAllResponse,
    SyncLogRead, WebhookConfigRead, WebhookConfigRequest, WebhookTestResponse,
)
from backend.app.domains.integrations.services import IntegrationService

router = APIRouter(prefix="/integrations", tags=["external-integrations"])

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
ADMIN_ROLES = {"Administrator", "Executive"}


def require_integration_admin(current_user: User = Depends(get_current_user)) -> User:
    """Connecting external systems and webhooks is restricted to Administrators and Executives."""
    if not ADMIN_ROLES.intersection(r.name for r in current_user.roles):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only Administrators and Executives can manage integrations.")
    return current_user


async def _read_upload(file: UploadFile) -> bytes:
    raw = await file.read()
    if len(raw) > MAX_UPLOAD_BYTES:
        raise DomainValidationError("File too large (max 10 MB).")
    return raw


def _import_permission(import_type: str) -> str:
    return "customer.import" if import_type == "customers" else "catalog.import"


def _require_import_permission(import_type: str, user: User) -> None:
    perms = {p.name for r in user.roles for p in r.permissions}
    if _import_permission(import_type) not in perms:
        raise HTTPException(status_code=403, detail=f"Permission denied. Required permission: {_import_permission(import_type)}")


# ── Salesforce ────────────────────────────────────────────────────────────────
@router.get("/salesforce/status", response_model=SalesforceStatusResponse)
async def get_salesforce_status(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Current Salesforce connection state, last successful sync and number of quotes mapped to opportunities."""
    return await IntegrationService(db).get_salesforce_status()


@router.get("/salesforce/authorize", response_model=SalesforceAuthorizeResponse)
async def salesforce_authorize_url(db: AsyncSession = Depends(get_db), current_user: User = Depends(require_integration_admin)):
    """Returns the Salesforce OAuth consent URL (requires SALESFORCE_CLIENT_ID/SECRET on the server)."""
    return SalesforceAuthorizeResponse(url=IntegrationService(db).authorize_url(current_user))


@router.get("/salesforce/callback", include_in_schema=False)
async def salesforce_oauth_callback(
    code: str = Query(None), state: str = Query(None), error: str = Query(None), error_description: str = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """OAuth redirect target. Authenticated by the signed `state` issued by /salesforce/authorize."""
    target = f"{settings.FRONTEND_URL}/integrations"
    if error or not code or not state:
        return RedirectResponse(f"{target}?sf=error&message={quote_plus(error_description or error or 'Missing authorization code')}")
    try:
        await IntegrationService(db).complete_oauth(code, state)
        await db.commit()
    except DomainValidationError as exc:
        await db.rollback()
        return RedirectResponse(f"{target}?sf=error&message={quote_plus(exc.detail)}")
    return RedirectResponse(f"{target}?sf=connected")


@router.post("/salesforce/connect", response_model=SalesforceConnectResponse)
async def connect_salesforce_crm(
    request: SalesforceConnectRequest, db: AsyncSession = Depends(get_db), current_user: User = Depends(require_integration_admin),
):
    """Connect using an access token; the credentials are verified against Salesforce before being stored."""
    res = await IntegrationService(db).connect_salesforce(request)
    await db.commit()
    return res


@router.post("/salesforce/disconnect")
async def disconnect_salesforce_crm(db: AsyncSession = Depends(get_db), current_user: User = Depends(require_integration_admin)):
    res = await IntegrationService(db).disconnect_salesforce()
    await db.commit()
    return res


@router.post("/salesforce/sync-quote/{quote_id}", response_model=SyncLogRead)
async def sync_quote_to_crm(
    quote_id: int, db: AsyncSession = Depends(get_db), current_user: User = Depends(PermissionChecker("quotes.export")),
):
    """Create/update the Salesforce Opportunity for an approved, sent or accepted quote."""
    log = await IntegrationService(db).sync_quote_to_crm(quote_id)
    await db.commit()
    return log


@router.post("/salesforce/sync-all", response_model=SalesforceSyncAllResponse)
async def sync_all_crm_pipeline(db: AsyncSession = Depends(get_db), current_user: User = Depends(require_integration_admin)):
    res = await IntegrationService(db).sync_all_crm()
    await db.commit()
    return res


# ── Imports ───────────────────────────────────────────────────────────────────
@router.post("/import/preview", response_model=ImportPreviewResponse)
async def import_preview(
    file: UploadFile = File(...), import_type: str = Form("catalog"),
    db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user),
):
    """Parse an uploaded CSV/XLSX and suggest a column mapping to the catalog or customer fields."""
    _require_import_permission(import_type, current_user)
    return await IntegrationService(db).import_preview(import_type, file.filename or "", await _read_upload(file))


@router.post("/import/execute", response_model=ImportExecuteResponse)
async def import_execute(
    file: UploadFile = File(...), import_type: str = Form("catalog"), mappings: str = Form(...),
    db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user),
):
    """Import rows from the uploaded file using the confirmed column mapping. Rows that fail are reported, the rest are saved."""
    _require_import_permission(import_type, current_user)
    try:
        parsed = [ColumnMapping(**m) for m in json.loads(mappings)]
    except Exception:
        raise DomainValidationError("mappings must be a JSON array of {file_column, db_field}.")
    res = await IntegrationService(db).import_execute(import_type, file.filename or "", await _read_upload(file), parsed, current_user)
    await db.commit()
    return res


# ── Webhooks ──────────────────────────────────────────────────────────────────
@router.get("/webhooks", response_model=WebhookConfigRead)
async def get_webhook_configuration(db: AsyncSession = Depends(get_db), current_user: User = Depends(require_integration_admin)):
    return await IntegrationService(db).get_webhook_config()


@router.put("/webhooks", response_model=WebhookConfigRead)
async def save_webhook_configuration(
    request: WebhookConfigRequest, db: AsyncSession = Depends(get_db), current_user: User = Depends(require_integration_admin),
):
    res = await IntegrationService(db).save_webhook_config(request)
    await db.commit()
    return res


@router.delete("/webhooks", status_code=status.HTTP_204_NO_CONTENT)
async def delete_webhook_configuration(db: AsyncSession = Depends(get_db), current_user: User = Depends(require_integration_admin)):
    await IntegrationService(db).delete_webhook_config()
    await db.commit()


@router.post("/webhooks/test", response_model=WebhookTestResponse)
async def test_webhook_event_dispatch(db: AsyncSession = Depends(get_db), current_user: User = Depends(require_integration_admin)):
    """Send a signed `webhook.test` event to the configured endpoint and report the real HTTP result."""
    res = await IntegrationService(db).test_webhook()
    await db.commit()
    return res


@router.get("/logs", response_model=List[SyncLogRead])
async def list_integration_sync_logs(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Sync, import and webhook delivery history."""
    return await IntegrationService(db).integration_repo.list_sync_logs()
