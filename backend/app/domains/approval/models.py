import enum
import uuid
from typing import Optional, List, TYPE_CHECKING
from datetime import datetime
from sqlalchemy import String, ForeignKey, Numeric, DateTime, func, Boolean, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.app.core.database import Base

if TYPE_CHECKING:
    from backend.app.domains.quotes.models import Quote
    from backend.app.domains.auth.models import User

class ApprovalStatus(str, enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"

    @classmethod
    def _missing_(cls, value: object):
        if isinstance(value, str):
            val_upper = value.upper()
            for member in cls:
                if member.value == val_upper:
                    return member
        return None

class ApprovalPolicy(Base):
    """
    ApprovalPolicy database model.
    Establishes rules defining when quotes need to be routed for authorization
    (e.g., minimum margin or discount threshold triggers).
    """
    __tablename__ = "approval_policies"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    
    # Threshold that triggers this policy (e.g. if quote discount >= threshold)
    discount_threshold: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    
    # UserRole (e.g. MANAGER, EXECUTIVE, ADMINISTRATOR) required to sign off on this policy
    role_required: Mapped[str] = mapped_column(String(50), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class ApprovalRequest(Base):
    """
    ApprovalRequest database model.
    Created when a quote triggers an active approval policy.
    """
    __tablename__ = "approval_requests"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    quote_id: Mapped[int] = mapped_column(ForeignKey("quotes.id", ondelete="CASCADE"), nullable=False)
    policy_id: Mapped[int] = mapped_column(ForeignKey("approval_policies.id"), nullable=False)
    
    status: Mapped[ApprovalStatus] = mapped_column(String(50), default=ApprovalStatus.PENDING, nullable=False)
    comments: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    
    assigned_role: Mapped[str] = mapped_column(String(50), nullable=False)
    decided_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid, ForeignKey("users.id"), nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)
    decided_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    policy: Mapped["ApprovalPolicy"] = relationship(lazy="joined")
    quote: Mapped["Quote"] = relationship("Quote", lazy="joined")
    decided_by: Mapped[Optional["User"]] = relationship("User", foreign_keys=[decided_by_id], lazy="selectin")

    @property
    def quote_number(self) -> Optional[str]:
        return self.quote.quote_number if self.quote else None

    @property
    def customer_name(self) -> str:
        if self.quote and getattr(self.quote, "customer", None):
            cust = self.quote.customer
            return getattr(cust, "display_name", None) or getattr(cust, "legal_name", None) or f"Customer #{self.quote.customer_id}"
        return f"Customer #{self.quote_id}"

    @property
    def amount(self) -> str:
        if not self.quote:
            return "$0.00"
        return f"${float(self.quote.total_amount):,.2f}"

    @property
    def subtotal(self) -> str:
        if not self.quote:
            return "$0.00"
        return f"${float(self.quote.subtotal):,.2f}"

    @property
    def discount_amount(self) -> str:
        if not self.quote:
            return "$0.00"
        return f"${float(self.quote.discount_amount):,.2f}"

    @property
    def discount_percentage(self) -> str:
        if not self.quote:
            return "0.0%"
        total_before = float(self.quote.total_amount) + float(self.quote.discount_amount)
        overall = (float(self.quote.discount_amount) / total_before * 100.0) if total_before > 0 else 0.0
        line_max = 0.0
        for it in (getattr(self.quote, "items", []) or []):
            if it.discount_percentage:
                line_max = max(line_max, float(it.discount_percentage))
        eff = max(overall, line_max)
        return f"{eff:.1f}%"

    @property
    def margin_percentage(self) -> str:
        if not self.quote or self.quote.margin_percentage is None:
            return "0.0%"
        return f"{float(self.quote.margin_percentage):.1f}%"

    @property
    def requested_by(self) -> str:
        if self.quote and getattr(self.quote, "created_by", None):
            u = self.quote.created_by
            name = f"{getattr(u, 'first_name', '')} {getattr(u, 'last_name', '')}".strip()
            return name if name else getattr(u, "email", "Sales Rep")
        return "Sales Representative"

    @property
    def requested_role(self) -> str:
        if self.quote and getattr(self.quote, "created_by", None):
            roles = getattr(self.quote.created_by, "roles", [])
            if roles:
                return roles[0].name
        return "Account Executive"

    @property
    def submitted_date(self) -> str:
        if self.created_at:
            return self.created_at.strftime("%Y-%m-%d %H:%M")
        return ""

    @property
    def reason(self) -> str:
        if self.comments:
            return self.comments
        if self.policy:
            return f"{self.policy.name} ({float(self.policy.discount_threshold):.0f}% discount trigger)"
        return "Discount threshold override review"

    @property
    def items(self) -> list:
        if not self.quote or not getattr(self.quote, "items", None):
            return []
        res = []
        for it in self.quote.items:
            res.append({
                "id": it.id,
                "product_name": it.product_name or it.sku or "Product",
                "sku": it.sku or "",
                "quantity": it.quantity,
                "unit_price": f"${float(it.unit_price):,.2f}",
                "discount_percentage": f"{float(it.discount_percentage):.1f}%",
                "discount_amount": f"${float(it.discount_amount):,.2f}",
                "total_price": f"${float(it.total_price):,.2f}",
                "margin_percentage": f"{float(it.margin_percentage):.1f}%" if it.margin_percentage is not None else "N/A"
            })
        return res

