from sqlalchemy import String, DateTime, func, Integer, JSON, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from typing import Optional, List
from datetime import datetime
from backend.app.core.database import Base

class IntegrationSyncLog(Base):
    """
    IntegrationSyncLog database model.
    Audits execution runs for external connectors (CSV imports, Salesforce updates, webhook deliveries).
    """
    __tablename__ = "integration_sync_logs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    integration_type: Mapped[str] = mapped_column(String(50), index=True, nullable=False)  # salesforce, import_catalog, import_customers, webhooks

    started_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False)  # running, success, failed

    records_processed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_summary: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

class SalesforceToken(Base):
    """
    SalesforceToken database model.
    Saves external CRM access credentials and OAuth state for authentication.
    """
    __tablename__ = "salesforce_tokens"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    access_token: Mapped[str] = mapped_column(String(500), nullable=False)
    refresh_token: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    instance_url: Mapped[str] = mapped_column(String(255), nullable=False)
    user_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    issued_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)
    expires_in: Mapped[int] = mapped_column(Integer, nullable=False)

class WebhookConfig(Base):
    """
    Single outbound webhook subscription. Events are POSTed as JSON signed with HMAC-SHA256.
    """
    __tablename__ = "webhook_configs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    endpoint_url: Mapped[str] = mapped_column(String(500), nullable=False)
    secret_key: Mapped[str] = mapped_column(String(100), nullable=False)
    events: Mapped[List[str]] = mapped_column(JSON, nullable=False, default=list)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_delivery_status: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    last_delivery_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
