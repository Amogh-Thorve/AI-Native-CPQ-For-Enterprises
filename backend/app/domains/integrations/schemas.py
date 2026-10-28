from pydantic import BaseModel, ConfigDict, field_validator
from typing import Optional, List
from datetime import datetime

class SyncLogRead(BaseModel):
    id: int
    integration_type: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    status: str
    records_processed: int
    error_summary: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

# ── Salesforce ────────────────────────────────────────────────────────────────
class SalesforceConnectRequest(BaseModel):
    """Connect with an access token (e.g. from `sf org display`) for the given org instance URL."""
    instance_url: str
    access_token: str
    refresh_token: Optional[str] = None

    @field_validator("instance_url")
    @classmethod
    def https_only(cls, v: str) -> str:
        v = v.strip().rstrip("/")
        if not v.startswith("https://"):
            raise ValueError("instance_url must start with https://")
        return v

class SalesforceConnectResponse(BaseModel):
    connected: bool
    instance_url: str
    user_email: Optional[str] = None
    issued_at: Optional[datetime] = None

class SalesforceStatusResponse(BaseModel):
    oauth_configured: bool = False
    connected: bool
    instance_url: Optional[str] = None
    user_email: Optional[str] = None
    last_sync: Optional[datetime] = None
    mapped_opportunities_count: int = 0
    token_issued_at: Optional[datetime] = None

class SalesforceAuthorizeResponse(BaseModel):
    url: str

class SalesforceSyncAllResponse(BaseModel):
    status: str
    synced_quotes: int
    failed_quotes: int
    log_id: int
    message: str

# ── Import ────────────────────────────────────────────────────────────────────
class ColumnMapping(BaseModel):
    file_column: str
    db_field: str

class ImportTargetField(BaseModel):
    field: str
    label: str
    required: bool

class ImportPreviewResponse(BaseModel):
    import_type: str
    headers: List[str] = []
    sample_rows: List[List[str]] = []
    suggested_mappings: List[ColumnMapping] = []
    target_fields: List[ImportTargetField] = []
    total_rows: int = 0

class ImportRowError(BaseModel):
    row: int
    key: Optional[str] = None
    error: str

class ImportExecuteResponse(BaseModel):
    success: bool
    total_rows: int
    records_imported: int
    records_failed: int
    errors: List[ImportRowError] = []
    log_id: int
    message: str

# ── Webhooks ──────────────────────────────────────────────────────────────────
class WebhookConfigRead(BaseModel):
    configured: bool = False
    enabled: bool = False
    endpoint_url: Optional[str] = None
    secret_key: Optional[str] = None
    events: List[str] = []
    available_events: List[str] = []
    last_delivery_status: Optional[str] = None
    last_delivery_at: Optional[datetime] = None

class WebhookConfigRequest(BaseModel):
    endpoint_url: str
    events: List[str]
    enabled: bool = True
    rotate_secret: bool = False

    @field_validator("endpoint_url")
    @classmethod
    def http_url(cls, v: str) -> str:
        v = v.strip()
        if not (v.startswith("https://") or v.startswith("http://")):
            raise ValueError("endpoint_url must be an http(s) URL")
        return v

class WebhookTestResponse(BaseModel):
    success: bool
    status_code: int
    event_dispatched: str
    timestamp: datetime
    response_body: str
