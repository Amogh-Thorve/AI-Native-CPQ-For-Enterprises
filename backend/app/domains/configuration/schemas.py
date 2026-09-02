from pydantic import BaseModel, ConfigDict
from typing import Optional, List, Dict
import uuid
from backend.app.domains.configuration.models import ConfigRuleType

# --- Option Schemas ---

class ProductConfigurationOptionBase(BaseModel):
    name: str
    description: Optional[str] = None
    value: str
    min_quantity: Optional[int] = None
    max_quantity: Optional[int] = None
    display_order: int = 0
    is_active: bool = True

class ProductConfigurationOptionCreate(ProductConfigurationOptionBase):
    group_id: int

class ProductConfigurationOptionUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    value: Optional[str] = None
    min_quantity: Optional[int] = None
    max_quantity: Optional[int] = None
    display_order: Optional[int] = None
    is_active: Optional[bool] = None

class ProductConfigurationOptionRead(ProductConfigurationOptionBase):
    id: int
    group_id: int

    model_config = ConfigDict(from_attributes=True)

# --- Group Schemas ---

class ProductConfigurationGroupBase(BaseModel):
    name: str
    description: Optional[str] = None
    required: bool = True
    selection_type: str = "SINGLE_SELECT"  # SINGLE_SELECT, MULTI_SELECT
    display_order: int = 0
    is_active: bool = True

class ProductConfigurationGroupCreate(ProductConfigurationGroupBase):
    product_id: int
    version_id: Optional[int] = None

class ProductConfigurationGroupUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    required: Optional[bool] = None
    selection_type: Optional[str] = None
    display_order: Optional[int] = None
    is_active: Optional[bool] = None

class ProductConfigurationGroupRead(ProductConfigurationGroupBase):
    id: int
    product_id: int
    version_id: Optional[int] = None
    options: List[ProductConfigurationOptionRead] = []

    model_config = ConfigDict(from_attributes=True)

# --- Rule Schemas ---

class ConfigurationRuleBase(BaseModel):
    product_id: int
    rule_type: ConfigRuleType
    source_option_id: int
    target_option_id: int
    message: str
    is_active: bool = True

class ConfigurationRuleCreate(ConfigurationRuleBase):
    version_id: Optional[int] = None

class ConfigurationRuleUpdate(BaseModel):
    product_id: Optional[int] = None
    rule_type: Optional[ConfigRuleType] = None
    source_option_id: Optional[int] = None
    target_option_id: Optional[int] = None
    message: Optional[str] = None
    is_active: Optional[bool] = None

class ConfigurationRuleRead(ConfigurationRuleBase):
    id: int
    version_id: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)

# --- Validation Schemas ---

class SelectionItem(BaseModel):
    group_id: int
    option_ids: List[int]
    quantities: Optional[Dict[str, int]] = None  # maps "option_id" -> quantity

class ValidateConfigurationRequest(BaseModel):
    product_id: int
    selections: List[SelectionItem]

class ConfigurationErrorDetail(BaseModel):
    rule_type: str  # REQUIRED_GROUP, SINGLE_SELECT, REQUIRES, EXCLUDES, QUANTITY, INVALID_OPTION, INACTIVE_OPTION
    message: str
    group_id: Optional[int] = None
    option_id: Optional[int] = None

class ValidateConfigurationResponse(BaseModel):
    valid: bool
    errors: List[ConfigurationErrorDetail] = []
    warnings: List[str] = []

# --- Session Schemas ---

class ConfigurationSessionCreate(BaseModel):
    product_id: int
    selections: List[SelectionItem]

class ConfigurationSessionRead(BaseModel):
    id: uuid.UUID
    product_id: int
    user_id: Optional[uuid.UUID] = None
    selections: List[SelectionItem]
    is_valid: bool

    model_config = ConfigDict(from_attributes=True)

# --- Bundle Components Schemas ---

class BundleComponentBase(BaseModel):
    product_id: int
    required: bool = True
    default_selected: bool = True
    min_quantity: int = 1
    max_quantity: Optional[int] = None
    default_quantity: int = 1
    display_order: int = 0
    is_active: bool = True

class BundleComponentCreate(BundleComponentBase):
    version_id: Optional[int] = None

class BundleComponentUpdate(BaseModel):
    product_id: Optional[int] = None
    required: Optional[bool] = None
    default_selected: Optional[bool] = None
    min_quantity: Optional[int] = None
    max_quantity: Optional[int] = None
    default_quantity: Optional[int] = None
    display_order: Optional[int] = None
    is_active: Optional[bool] = None

from backend.app.domains.catalog.schemas import ProductRead

class BundleComponentRead(BundleComponentBase):
    id: int
    bundle_id: int
    version_id: Optional[int] = None
    product: Optional[ProductRead] = None

    model_config = ConfigDict(from_attributes=True)

# --- Bundle Schemas ---

class BundleBase(BaseModel):
    name: str
    description: Optional[str] = None
    sku: str
    is_active: bool = True

class BundleCreate(BundleBase):
    pass

class BundleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    sku: Optional[str] = None
    is_active: Optional[bool] = None

class BundleRead(BundleBase):
    id: int
    components: List[BundleComponentRead] = []

    model_config = ConfigDict(from_attributes=True)

# --- Bundle Validation Schemas ---

class ComponentSelectionItem(BaseModel):
    component_id: int
    selected: bool
    quantity: int
    configuration: Optional[ValidateConfigurationRequest] = None

class ValidateBundleRequest(BaseModel):
    bundle_id: int
    selections: List[ComponentSelectionItem]

class BundleErrorDetail(BaseModel):
    type: str  # REQUIRED_COMPONENT, QUANTITY, CONFIGURATION, INVALID_PRODUCT, INACTIVE_PRODUCT
    message: str
    component_id: Optional[int] = None

class ValidateBundleResponse(BaseModel):
    valid: bool
    errors: List[BundleErrorDetail] = []
    warnings: List[str] = []

# --- Bundle Session Schemas ---

class BundleConfigurationSessionCreate(BaseModel):
    bundle_id: int
    selections: List[ComponentSelectionItem]

class BundleConfigurationSessionRead(BaseModel):
    id: uuid.UUID
    bundle_id: int
    user_id: Optional[uuid.UUID] = None
    selections: List[ComponentSelectionItem]
    is_valid: bool

    model_config = ConfigDict(from_attributes=True)

# --- Versioning Schemas ---

from datetime import datetime

class ConfigurationVersionRead(BaseModel):
    id: int
    entity_type: str
    entity_id: int
    version_number: int
    status: str
    change_summary: Optional[str] = None
    created_by: Optional[uuid.UUID] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

class ConfigurationVersionCreate(BaseModel):
    entity_type: str
    entity_id: int
    change_summary: Optional[str] = None

class ConfigurationVersionUpdate(BaseModel):
    status: Optional[str] = None
    change_summary: Optional[str] = None

class VersionComparisonResponse(BaseModel):
    version_a: int
    version_b: int
    added_groups: List[str] = []
    removed_groups: List[str] = []
    added_options: List[str] = []
    removed_options: List[str] = []
    added_rules: List[str] = []
    removed_rules: List[str] = []
    added_components: List[str] = []
    removed_components: List[str] = []


