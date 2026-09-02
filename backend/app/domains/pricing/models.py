import enum
import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import String, Boolean, JSON, DateTime, ForeignKey, Integer, Numeric, func
from sqlalchemy.orm import Mapped, mapped_column
from backend.app.core.database import Base

class PricingRuleType(str, enum.Enum):
    VOLUME_DISCOUNT = "volume_discount"
    TIERED_PRICING = "tiered_pricing"
    CUSTOMER_SEGMENT = "customer_segment"
    PROMOTIONAL = "promotional"

class PricingRule(Base):
    """
    PricingRule database model containing logic parameters.
    Saves conditions (such as minimum quantity thresholds) and discount action details.
    """
    __tablename__ = "pricing_rules"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    rule_type: Mapped[PricingRuleType] = mapped_column(String(50), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    
    # Store target validation filters (e.g. {"min_qty": 10, "product_ids": [1, 2]})
    conditions: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    
    # Store action parameters (e.g. {"discount_type": "percentage", "discount_value": 15.0})
    actions: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    # Governance & Metadata
    description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    status: Mapped[Optional[str]] = mapped_column(String(20), default="ACTIVE", nullable=True)  # DRAFT, ACTIVE, INACTIVE
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), server_default=func.now(), nullable=True)
    updated_by: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), server_default=func.now(), onupdate=func.now(), nullable=True)


from sqlalchemy import ForeignKey, Integer, Numeric
from typing import Optional

class ProductPricingTier(Base):
    """
    Persisted configuration for Tier-Based and Block pricing configurations.
    """
    __tablename__ = "product_pricing_tiers"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), index=True, nullable=False)
    pricing_method: Mapped[str] = mapped_column(String(50), nullable=False)  # TIERED or BLOCK
    tiered_mode: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # VOLUME or CUMULATIVE or Null
    min_quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    max_quantity: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # Null = unlimited
    price: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)  # Per-unit tier price or fixed block price

class ProductPricingSetting(Base):
    """
    Persisted pricing method and markup configurations for catalog products.
    """
    __tablename__ = "product_pricing_settings"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), unique=True, index=True, nullable=False)
    pricing_method: Mapped[str] = mapped_column(String(50), default="STANDARD", nullable=False)
    markup_percent: Mapped[float] = mapped_column(Numeric(12, 2), default=0.00, nullable=False)


class PricingAuditLog(Base):
    """
    Audit logs for administrative pricing configurations.
    """
    __tablename__ = "pricing_audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    user_role: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    action: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    pricing_config_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    product_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=func.now(), server_default=func.now(), nullable=True)
    before_value: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    after_value: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)



