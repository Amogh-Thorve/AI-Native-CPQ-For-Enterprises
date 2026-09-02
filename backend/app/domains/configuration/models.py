import enum
import uuid
from datetime import datetime
from typing import List, Optional
from sqlalchemy import String, ForeignKey, Boolean, Integer, JSON, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.app.core.database import Base

class ConfigRuleType(str, enum.Enum):
    REQUIRES = "REQUIRES"
    EXCLUDES = "EXCLUDES"

class ConfigurationVersion(Base):
    """
    Blueprints versions mapping status (DRAFT, ACTIVE, INACTIVE, ARCHIVED).
    """
    __tablename__ = "configuration_versions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False) # "PRODUCT" or "BUNDLE"
    entity_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="DRAFT", nullable=False) # DRAFT, ACTIVE, INACTIVE, ARCHIVED
    change_summary: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)

class ProductConfigurationGroup(Base):
    """
    Groups of configuration options for a product (e.g., Plan, Support, Users).
    """
    __tablename__ = "product_configuration_groups"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    version_id: Mapped[Optional[int]] = mapped_column(ForeignKey("configuration_versions.id", ondelete="SET NULL"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    required: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    selection_type: Mapped[str] = mapped_column(String(50), default="SINGLE_SELECT", nullable=False)  # SINGLE_SELECT, MULTI_SELECT
    display_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    options: Mapped[List["ProductConfigurationOption"]] = relationship(
        "ProductConfigurationOption",
        back_populates="group",
        cascade="all, delete-orphan",
        order_by="ProductConfigurationOption.display_order"
    )

class ProductConfigurationOption(Base):
    """
    Concrete choices inside a configuration group (e.g. Basic Plan, Premium Support).
    """
    __tablename__ = "product_configuration_options"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("product_configuration_groups.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    value: Mapped[str] = mapped_column(String(255), nullable=False)
    min_quantity: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    max_quantity: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    display_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    group: Mapped["ProductConfigurationGroup"] = relationship("ProductConfigurationGroup", back_populates="options")

class ConfigurationRule(Base):
    """
    Logical rules dictating compatible/incompatible selections (REQUIRES, EXCLUDES).
    """
    __tablename__ = "configuration_rules"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    version_id: Mapped[Optional[int]] = mapped_column(ForeignKey("configuration_versions.id", ondelete="SET NULL"), nullable=True, index=True)
    rule_type: Mapped[str] = mapped_column(String(50), nullable=False)  # REQUIRES, EXCLUDES
    source_option_id: Mapped[int] = mapped_column(ForeignKey("product_configuration_options.id", ondelete="CASCADE"), nullable=False, index=True)
    target_option_id: Mapped[int] = mapped_column(ForeignKey("product_configuration_options.id", ondelete="CASCADE"), nullable=False, index=True)
    message: Mapped[str] = mapped_column(String(500), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    source_option: Mapped["ProductConfigurationOption"] = relationship("ProductConfigurationOption", foreign_keys=[source_option_id])
    target_option: Mapped["ProductConfigurationOption"] = relationship("ProductConfigurationOption", foreign_keys=[target_option_id])

class ConfigurationSession(Base):
    """
    Temporary or draft selection workflows during configuration.
    """
    __tablename__ = "configuration_sessions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    version_id: Mapped[Optional[int]] = mapped_column(ForeignKey("configuration_versions.id", ondelete="SET NULL"), nullable=True, index=True)
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    selections: Mapped[dict] = mapped_column(JSON, default=list, nullable=False)  # e.g., [{"group_id": 1, "option_ids": [2], "quantities": {"2": 1}}]
    is_valid: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)

class Bundle(Base):
    """
    Sellable solution composed of multiple components.
    """
    __tablename__ = "bundles"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    sku: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_by: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)

    components: Mapped[List["BundleComponent"]] = relationship(
        "BundleComponent",
        back_populates="bundle",
        cascade="all, delete-orphan",
        order_by="BundleComponent.display_order"
    )

class BundleComponent(Base):
    """
    Intersection model mapping catalog products to parent bundles with quantity bounds.
    """
    __tablename__ = "bundle_components"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    bundle_id: Mapped[int] = mapped_column(ForeignKey("bundles.id", ondelete="CASCADE"), nullable=False, index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    version_id: Mapped[Optional[int]] = mapped_column(ForeignKey("configuration_versions.id", ondelete="SET NULL"), nullable=True, index=True)
    required: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    default_selected: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    min_quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    max_quantity: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    default_quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    bundle: Mapped["Bundle"] = relationship("Bundle", back_populates="components")
    product: Mapped["Product"] = relationship("Product", foreign_keys=[product_id])

class BundleConfigurationSession(Base):
    """
    Selections and quantities drafts saved during guided bundle configuration.
    """
    __tablename__ = "bundle_configuration_sessions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    bundle_id: Mapped[int] = mapped_column(ForeignKey("bundles.id", ondelete="CASCADE"), nullable=False, index=True)
    version_id: Mapped[Optional[int]] = mapped_column(ForeignKey("configuration_versions.id", ondelete="SET NULL"), nullable=True, index=True)
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    selections: Mapped[dict] = mapped_column(JSON, default=list, nullable=False)  # List[dict] matching validation body selections format
    is_valid: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)

class BundleAuditLog(Base):
    """
    Auditing tracks bundle modifications.
    """
    __tablename__ = "bundle_audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    user_role: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False)  # BUNDLE_CREATED, BUNDLE_UPDATED, etc.
    bundle_id: Mapped[Optional[int]] = mapped_column(ForeignKey("bundles.id", ondelete="SET NULL"), nullable=True, index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)
    before_value: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    after_value: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

