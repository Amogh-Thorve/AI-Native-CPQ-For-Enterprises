import uuid
from pydantic import BaseModel, Field, ConfigDict, model_validator
from typing import Literal, Optional, List
from datetime import datetime
from backend.app.domains.approval.models import ApprovalStatus

class ApprovalPolicyBase(BaseModel):
    name: str
    policy_type: Literal["DISCOUNT", "MARGIN"] = "DISCOUNT"
    discount_threshold: float = Field(default=0.0, ge=0.0, le=100.0)
    margin_threshold: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    role_required: str
    is_active: bool = True

    @model_validator(mode="after")
    def check_threshold(self):
        if self.policy_type == "MARGIN" and self.margin_threshold is None:
            raise ValueError("margin_threshold is required for MARGIN policies")
        if self.policy_type == "DISCOUNT" and self.discount_threshold <= 0:
            raise ValueError("discount_threshold must be greater than 0 for DISCOUNT policies")
        return self

class ApprovalPolicyCreate(ApprovalPolicyBase):
    pass

class ApprovalPolicyUpdate(BaseModel):
    name: Optional[str] = None
    discount_threshold: Optional[float] = None
    margin_threshold: Optional[float] = None
    role_required: Optional[str] = None
    is_active: Optional[bool] = None

class ApprovalPolicyRead(ApprovalPolicyBase):
    id: int
    model_config = ConfigDict(from_attributes=True)


class ApprovalQuoteItemSummary(BaseModel):
    id: int
    product_name: Optional[str] = None
    sku: Optional[str] = None
    quantity: int = 1
    unit_price: str = "$0.00"
    discount_percentage: str = "0.0%"
    discount_amount: str = "$0.00"
    total_price: str = "$0.00"
    margin_percentage: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class ApprovalRequestBase(BaseModel):
    quote_id: int
    policy_id: int
    assigned_role: str

class ApprovalRequestCreate(ApprovalRequestBase):
    pass

class ApprovalRequestRead(ApprovalRequestBase):
    id: int
    status: ApprovalStatus
    comments: Optional[str] = None
    decided_by_id: Optional[uuid.UUID] = None
    created_at: datetime
    decided_at: Optional[datetime] = None
    policy: Optional[ApprovalPolicyRead] = None

    # Enriched fields for table and detail views
    quote_number: Optional[str] = None
    customer_name: Optional[str] = None
    amount: Optional[str] = None
    subtotal: Optional[str] = None
    discount_percentage: Optional[str] = None
    discount_amount: Optional[str] = None
    margin_percentage: Optional[str] = None
    requested_by: Optional[str] = None
    requested_role: Optional[str] = None
    submitted_date: Optional[str] = None
    reason: Optional[str] = None
    items: List[ApprovalQuoteItemSummary] = []

    model_config = ConfigDict(from_attributes=True)

class SubmitApprovalRequest(BaseModel):
    quote_id: int
    comments: Optional[str] = None

class DecideApprovalRequest(BaseModel):
    status: ApprovalStatus  # APPROVED or REJECTED
    comments: Optional[str] = None

