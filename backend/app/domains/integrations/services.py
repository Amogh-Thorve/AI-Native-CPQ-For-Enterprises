import base64
import csv
import io
import re
import secrets
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional, Tuple

import jwt
import openpyxl
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.config import settings
from backend.app.core.exceptions import DomainValidationError, EntityNotFoundError
from backend.app.domains.auth.models import User
from backend.app.domains.catalog.models import Category, Product
from backend.app.domains.catalog.schemas import BillingType, CategoryCreate, ProductCreate
from backend.app.domains.catalog.services import CatalogService
from backend.app.domains.customer.schemas import CustomerCreate
from backend.app.domains.customer.services import CustomerService
from backend.app.domains.integrations import salesforce_client as sf
from backend.app.domains.integrations import webhooks
from backend.app.domains.integrations.models import IntegrationSyncLog
from backend.app.domains.integrations.repositories import IntegrationRepository
from backend.app.domains.integrations.schemas import (
    ColumnMapping, ImportExecuteResponse, ImportPreviewResponse, ImportRowError, ImportTargetField,
    SalesforceConnectRequest, SalesforceConnectResponse, SalesforceStatusResponse, SalesforceSyncAllResponse,
    WebhookConfigRead, WebhookConfigRequest, WebhookTestResponse,
)
from backend.app.domains.quotes.models import Quote, QuoteStatus

STAGE_MAP = {
    "DRAFT": "Prospecting", "SUBMITTED": "Proposal/Price Quote", "APPROVED": "Proposal/Price Quote",
    "SENT": "Negotiation/Review", "ACCEPTED": "Closed Won",
    "REJECTED": "Closed Lost", "CANCELLED": "Closed Lost", "EXPIRED": "Closed Lost",
}
SYNCABLE = [QuoteStatus.APPROVED.value, QuoteStatus.SENT.value, QuoteStatus.ACCEPTED.value]

IMPORT_FIELDS: Dict[str, List[ImportTargetField]] = {
    "catalog": [
        ImportTargetField(field="sku", label="SKU", required=True),
        ImportTargetField(field="name", label="Product name", required=True),
        ImportTargetField(field="base_price", label="List price", required=True),
        ImportTargetField(field="description", label="Description", required=False),
        ImportTargetField(field="category", label="Category", required=False),
        ImportTargetField(field="billing_type", label="Billing type (MRC/NRC/USAGE)", required=False),
        ImportTargetField(field="cost_price", label="Unit cost", required=False),
        ImportTargetField(field="currency", label="Currency", required=False),
        ImportTargetField(field="status", label="Status (Active/Inactive)", required=False),
    ],
    "customers": [
        ImportTargetField(field="customer_number", label="Customer number", required=True),
        ImportTargetField(field="legal_name", label="Legal name", required=True),
        ImportTargetField(field="display_name", label="Display name", required=False),
        ImportTargetField(field="industry", label="Industry", required=False),
        ImportTargetField(field="email", label="Email", required=False),
        ImportTargetField(field="phone", label="Phone", required=False),
        ImportTargetField(field="website", label="Website", required=False),
        ImportTargetField(field="status", label="Status", required=False),
        ImportTargetField(field="currency", label="Currency", required=False),
    ],
}
# header-name hints used to auto-suggest mappings
SYNONYMS = {
    "sku": ["sku", "productcode", "partnumber", "itemcode", "code"],
    "name": ["name", "productname", "title", "item"],
    "base_price": ["baseprice", "listprice", "price", "unitprice", "msrp"],
    "cost_price": ["costprice", "cost", "unitcost"],
    "description": ["description", "desc", "details"],
    "category": ["category", "productfamily", "family", "group"],
    "billing_type": ["billingtype", "billing", "chargetype"],
    "currency": ["currency", "curr"],
    "status": ["status", "active", "state"],
    "customer_number": ["customernumber", "customerid", "accountnumber", "accountid", "customerno"],
    "legal_name": ["legalname", "companyname", "company", "accountname", "customername"],
    "display_name": ["displayname", "tradingname", "shortname"],
    "industry": ["industry", "sector", "vertical"],
    "email": ["email", "emailaddress"],
    "phone": ["phone", "telephone", "phonenumber"],
    "website": ["website", "url", "web"],
}


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def parse_tabular(file_name: str, raw: bytes) -> Tuple[List[str], List[List[str]]]:
    """Parses CSV or XLSX bytes into (headers, rows) of stripped strings; blank rows are dropped."""
    name = (file_name or "").lower()
    rows: List[List[str]] = []
    if name.endswith(".xlsx"):
        try:
            wb = openpyxl.load_workbook(io.BytesIO(raw), data_only=True, read_only=True)
        except Exception as exc:
            raise DomainValidationError(f"Invalid Excel file: {exc}")
        for row in wb.active.iter_rows(values_only=True):
            rows.append(["" if c is None else str(c).strip() for c in row])
    elif name.endswith(".csv"):
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            text = raw.decode("latin-1")
        rows = [[c.strip() for c in r] for r in csv.reader(io.StringIO(text))]
    else:
        raise DomainValidationError("Unsupported file type. Upload a .csv or .xlsx file.")
    rows = [r for r in rows if any(c for c in r)]
    if len(rows) < 2:
        raise DomainValidationError("The file must contain a header row and at least one data row.")
    headers = rows[0]
    width = len(headers)
    return headers, [(r + [""] * width)[:width] for r in rows[1:]]


def suggest_mappings(import_type: str, headers: List[str]) -> List[ColumnMapping]:
    used, out = set(), []
    for field in IMPORT_FIELDS[import_type]:
        hints = SYNONYMS.get(field.field, [field.field])
        for h in headers:
            if h and h not in used and _norm(h) in hints + [_norm(field.field)]:
                out.append(ColumnMapping(file_column=h, db_field=field.field))
                used.add(h)
                break
    return out


def _dec(v: str, label: str) -> Decimal:
    try:
        d = Decimal(v.replace(",", "").replace("$", "").strip())
    except (InvalidOperation, AttributeError):
        raise ValueError(f"Invalid {label} '{v}'")
    if d < 0:
        raise ValueError(f"{label} cannot be negative")
    return d


class IntegrationService:
    """
    External systems: Salesforce CRM (OAuth + opportunity sync), CSV/Excel imports and signed webhooks.
    """
    def __init__(self, db: AsyncSession):
        self.db = db
        self.integration_repo = IntegrationRepository(db)

    # ── Salesforce ──────────────────────────────────────────────────────────────
    async def get_salesforce_status(self) -> SalesforceStatusResponse:
        token = await self.integration_repo.get_salesforce_token()
        if not token:
            return SalesforceStatusResponse(oauth_configured=sf.oauth_configured(), connected=False)
        mapped = (await self.db.execute(
            select(func.count()).select_from(Quote).where(Quote.external_opportunity_id.is_not(None))
        )).scalar() or 0
        last = (await self.db.execute(
            select(func.max(IntegrationSyncLog.completed_at)).where(
                IntegrationSyncLog.integration_type == "salesforce", IntegrationSyncLog.status == "success")
        )).scalar()
        return SalesforceStatusResponse(
            oauth_configured=sf.oauth_configured(), connected=True, instance_url=token.instance_url,
            user_email=token.user_email, last_sync=last, mapped_opportunities_count=int(mapped),
            token_issued_at=token.issued_at,
        )

    def authorize_url(self, user: User) -> str:
        if not sf.oauth_configured():
            raise DomainValidationError(
                "Salesforce OAuth is not configured. Set SALESFORCE_CLIENT_ID and SALESFORCE_CLIENT_SECRET in backend/.env, "
                "or connect with an access token instead.")
        state = jwt.encode(
            {"sub": str(user.id), "purpose": "sf_oauth", "exp": datetime.now(timezone.utc) + timedelta(minutes=10)},
            settings.SECRET_KEY, algorithm=settings.ALGORITHM)
        return sf.build_authorize_url(state)

    async def complete_oauth(self, code: str, state: str) -> None:
        try:
            claims = jwt.decode(state, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        except jwt.PyJWTError:
            raise DomainValidationError("Invalid or expired OAuth state.")
        if claims.get("purpose") != "sf_oauth":
            raise DomainValidationError("Invalid OAuth state.")
        try:
            tok = await sf.exchange_code(code)
            client = sf.SalesforceClient(tok["instance_url"], tok["access_token"])
            email = (await client.userinfo()).get("email")
        except sf.SalesforceError as exc:
            raise DomainValidationError(str(exc))
        await self.integration_repo.save_salesforce_token(
            tok["access_token"], tok.get("refresh_token"), tok["instance_url"], 7200, user_email=email)
        log = await self.integration_repo.create_sync_log("salesforce")
        await self.integration_repo.update_sync_log(log.id, "success", 0)

    async def connect_salesforce(self, request: SalesforceConnectRequest) -> SalesforceConnectResponse:
        client = sf.SalesforceClient(request.instance_url, request.access_token, request.refresh_token)
        try:
            info = await client.userinfo()
        except Exception as exc:
            raise DomainValidationError(f"Could not verify the Salesforce credentials: {exc}")
        token = await self.integration_repo.save_salesforce_token(
            request.access_token, request.refresh_token, request.instance_url, 7200, user_email=info.get("email"))
        log = await self.integration_repo.create_sync_log("salesforce")
        await self.integration_repo.update_sync_log(log.id, "success", 0)
        return SalesforceConnectResponse(
            connected=True, instance_url=token.instance_url, user_email=token.user_email, issued_at=token.issued_at)

    async def disconnect_salesforce(self) -> dict:
        await self.integration_repo.delete_salesforce_token()
        return {"success": True, "message": "Salesforce disconnected and stored credentials deleted."}

    async def _client(self) -> sf.SalesforceClient:
        token = await self.integration_repo.get_salesforce_token()
        if not token:
            raise DomainValidationError("Salesforce is not connected. Connect it on the Integrations page first.")
        return sf.SalesforceClient(
            token.instance_url, token.access_token, token.refresh_token,
            on_token_refreshed=self.integration_repo.update_access_token)

    async def _push_quote(self, client: sf.SalesforceClient, quote: Quote) -> str:
        cust = quote.customer
        acct_name = cust.display_name or cust.legal_name
        found = await client.query(f"SELECT Id FROM Account WHERE Name = '{sf.soql_escape(acct_name)}' LIMIT 1")
        if found:
            account_id = found[0]["Id"]
        else:
            account_id = await client.create("Account", {
                k: v for k, v in {"Name": acct_name, "Phone": cust.phone, "Website": cust.website, "Industry": None}.items() if v})
        status_val = quote.status.value if hasattr(quote.status, "value") else str(quote.status)
        lines = "\n".join(
            f"{i.product_name} ({i.sku}) x{i.quantity} = {quote.currency} {i.total_price:,.2f}" for i in quote.items)
        close = quote.valid_until.date() if quote.valid_until else (datetime.now(timezone.utc) + timedelta(days=30)).date()
        body = {
            "Name": f"{quote.quote_number} - {quote.title or acct_name}"[:120],
            "AccountId": account_id,
            "StageName": STAGE_MAP.get(status_val, "Prospecting"),
            "CloseDate": close.isoformat(),
            "Amount": float(quote.total_amount),
            "Description": f"CPQ quote {quote.quote_number} v{quote.version} ({status_val})\n{lines}"[:32000],
        }
        if quote.external_opportunity_id:
            await client.update("Opportunity", quote.external_opportunity_id, {k: v for k, v in body.items() if k != "AccountId"})
            return quote.external_opportunity_id
        return await client.create("Opportunity", body)

    async def sync_quote_to_crm(self, quote_id: int) -> IntegrationSyncLog:
        quote = (await self.db.execute(select(Quote).where(Quote.id == quote_id))).scalars().first()
        if not quote:
            raise EntityNotFoundError(f"Quote {quote_id} not found.")
        status_val = quote.status.value if hasattr(quote.status, "value") else str(quote.status)
        if status_val not in SYNCABLE:
            raise DomainValidationError("Only approved, sent or accepted quotes can be synced to Salesforce.")
        client = await self._client()
        log = await self.integration_repo.create_sync_log("salesforce")
        try:
            opp_id = await self._push_quote(client, quote)
            quote.external_opportunity_id = opp_id
            self.db.add(quote)
            await self.integration_repo.update_sync_log(log.id, "success", 1)
        except Exception as exc:
            await self.integration_repo.update_sync_log(log.id, "failed", 0, str(exc)[:490])
        await self.db.refresh(log)
        return log

    async def sync_all_crm(self) -> SalesforceSyncAllResponse:
        client = await self._client()
        quotes = list((await self.db.execute(select(Quote).where(Quote.status.in_(SYNCABLE)))).scalars().all())
        log = await self.integration_repo.create_sync_log("salesforce")
        ok, failed, last_err = 0, 0, None
        for q in quotes:
            try:
                q.external_opportunity_id = await self._push_quote(client, q)
                self.db.add(q)
                ok += 1
            except Exception as exc:
                failed += 1
                last_err = str(exc)
        await self.integration_repo.update_sync_log(
            log.id, "failed" if (failed and not ok) else "success", ok, last_err[:490] if last_err else None)
        return SalesforceSyncAllResponse(
            status="FAILED" if (failed and not ok) else ("PARTIAL" if failed else "SUCCESS"),
            synced_quotes=ok, failed_quotes=failed, log_id=log.id,
            message=f"Synced {ok} quote(s) to Salesforce" + (f"; {failed} failed ({last_err})" if failed else "."))

    # ── Imports ─────────────────────────────────────────────────────────────────
    def _check_type(self, import_type: str) -> None:
        if import_type not in IMPORT_FIELDS:
            raise DomainValidationError("import_type must be 'catalog' or 'customers'.")

    async def import_preview(self, import_type: str, file_name: str, raw: bytes) -> ImportPreviewResponse:
        self._check_type(import_type)
        headers, rows = parse_tabular(file_name, raw)
        return ImportPreviewResponse(
            import_type=import_type, headers=headers, sample_rows=rows[:5],
            suggested_mappings=suggest_mappings(import_type, headers),
            target_fields=IMPORT_FIELDS[import_type], total_rows=len(rows))

    async def import_execute(
        self, import_type: str, file_name: str, raw: bytes, mappings: List[ColumnMapping], user: User
    ) -> ImportExecuteResponse:
        self._check_type(import_type)
        headers, rows = parse_tabular(file_name, raw)
        col = {m.db_field: headers.index(m.file_column) for m in mappings if m.file_column in headers}
        missing = [f.label for f in IMPORT_FIELDS[import_type] if f.required and f.field not in col]
        if missing:
            raise DomainValidationError("Map the required field(s): " + ", ".join(missing))

        perms = {p.name for r in user.roles for p in r.permissions}
        if import_type == "catalog" and "cost_price" in col and "catalog.cost.manage" not in perms:
            raise DomainValidationError("You do not have permission to import cost information.")

        log = await self.integration_repo.create_sync_log(f"import_{import_type}")
        errors: List[ImportRowError] = []
        imported = 0
        catalog = CatalogService(self.db)
        customers = CustomerService(self.db)
        cat_cache: Dict[str, Category] = {c.name.lower(): c for c in await catalog.list_categories()}

        for idx, row in enumerate(rows, start=2):
            def get(field: str) -> str:
                return row[col[field]].strip() if field in col else ""
            key = get("sku") or get("customer_number")
            try:
                blank = [f.label for f in IMPORT_FIELDS[import_type] if f.required and not get(f.field)]
                if blank:
                    raise ValueError("Missing required value: " + ", ".join(blank))
                async with self.db.begin_nested():
                    if import_type == "catalog":
                        if await catalog.product_repo.get_by_sku(get("sku")):
                            raise ValueError("SKU already exists")
                        category_id = None
                        if get("category"):
                            cat = cat_cache.get(get("category").lower())
                            if not cat:
                                cat = await catalog.create_category(CategoryCreate(name=get("category")))
                                cat_cache[cat.name.lower()] = cat
                            category_id = cat.id
                        bt = (get("billing_type") or "MRC").upper()
                        if bt not in ("MRC", "NRC", "USAGE"):
                            raise ValueError(f"Invalid billing type '{bt}'")
                        status_raw = (get("status") or "active").lower()
                        await catalog.product_repo.create(ProductCreate(
                            sku=get("sku"), name=get("name"), description=get("description") or None,
                            base_price=_dec(get("base_price"), "list price"),
                            cost_price=_dec(get("cost_price"), "unit cost") if get("cost_price") else None,
                            currency=(get("currency") or "USD").upper()[:3], is_active=status_raw not in ("inactive", "false", "0", "no"),
                            category_id=category_id, billing_type=BillingType(bt)))
                    else:
                        status_raw = (get("status") or "PROSPECT").upper()
                        await customers.create_customer(user.id, CustomerCreate(
                            customer_number=get("customer_number"), legal_name=get("legal_name"),
                            display_name=get("display_name") or None, industry=get("industry") or None,
                            email=get("email") or None, phone=get("phone") or None, website=get("website") or None,
                            status=status_raw if status_raw in ("ACTIVE", "INACTIVE", "PROSPECT", "ARCHIVED") else "PROSPECT",
                            currency=(get("currency") or "USD").upper()), current_user=user)
                imported += 1
            except Exception as exc:
                msg = getattr(exc, "detail", None) or str(exc)
                errors.append(ImportRowError(row=idx, key=key or None, error=str(msg)[:200]))

        await self.integration_repo.update_sync_log(
            log.id, "success" if imported or not errors else "failed", imported,
            f"{len(errors)} row(s) failed" if errors else None)
        return ImportExecuteResponse(
            success=imported > 0 or not errors, total_rows=len(rows), records_imported=imported,
            records_failed=len(errors), errors=errors[:50], log_id=log.id,
            message=f"Imported {imported} of {len(rows)} row(s)" + (f"; {len(errors)} failed." if errors else "."))

    # ── Webhooks ────────────────────────────────────────────────────────────────
    async def get_webhook_config(self) -> WebhookConfigRead:
        cfg = await webhooks.get_config(self.db)
        if not cfg:
            return WebhookConfigRead(available_events=webhooks.SUPPORTED_EVENTS)
        return WebhookConfigRead(
            configured=True, enabled=cfg.enabled, endpoint_url=cfg.endpoint_url, secret_key=cfg.secret_key,
            events=cfg.events or [], available_events=webhooks.SUPPORTED_EVENTS,
            last_delivery_status=cfg.last_delivery_status, last_delivery_at=cfg.last_delivery_at)

    async def save_webhook_config(self, request: WebhookConfigRequest) -> WebhookConfigRead:
        bad = [e for e in request.events if e not in webhooks.SUPPORTED_EVENTS]
        if bad:
            raise DomainValidationError(f"Unsupported event(s): {', '.join(bad)}")
        cfg = await webhooks.get_config(self.db)
        if not cfg:
            cfg = webhooks.WebhookConfig(endpoint_url=request.endpoint_url, secret_key="whsec_" + secrets.token_hex(16), events=request.events, enabled=request.enabled)
        else:
            cfg.endpoint_url, cfg.events, cfg.enabled = request.endpoint_url, request.events, request.enabled
            if request.rotate_secret:
                cfg.secret_key = "whsec_" + secrets.token_hex(16)
        self.db.add(cfg)
        await self.db.flush()
        return await self.get_webhook_config()

    async def delete_webhook_config(self) -> None:
        cfg = await webhooks.get_config(self.db)
        if cfg:
            await self.db.delete(cfg)
            await self.db.flush()

    async def test_webhook(self) -> WebhookTestResponse:
        cfg = await webhooks.get_config(self.db)
        if not cfg:
            raise DomainValidationError("Configure a webhook endpoint first.")
        log = await self.integration_repo.create_sync_log("webhooks")
        ok, code, body = await webhooks.deliver(self.db, cfg, "webhook.test", {"message": "Test event from CPQ"})
        await self.integration_repo.update_sync_log(log.id, "success" if ok else "failed", 1 if ok else 0, None if ok else (body or "delivery failed")[:490])
        return WebhookTestResponse(success=ok, status_code=code, event_dispatched="webhook.test", timestamp=datetime.utcnow(), response_body=body)
