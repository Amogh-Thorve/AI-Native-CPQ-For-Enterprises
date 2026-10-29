"""CPQ-Bench task format. Money is Decimal throughout; nothing here touches the database."""
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from backend.app.domains.quotes.models import QuoteStatus


class Category(str, Enum):
    SIMPLE_QUOTE = "simple_quote"
    CONSTRAINED_CONFIG = "constrained_config"
    PRICING_EDGE = "pricing_edge"
    POLICY_LIMIT = "policy_limit"
    AMBIGUITY = "ambiguity"
    REVISION = "revision"
    PERMISSION_TRAP = "permission_trap"
    MULTI_TURN = "multi_turn"


class Split(str, Enum):
    DEV = "dev"
    TEST = "test"


UserRole = Literal["Administrator", "Sales Manager", "Sales Representative", "Executive"]


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ExpectedLine(_Model):
    sku: str
    qty: int = Field(ge=1)
    unit_price: Decimal
    line_total: Decimal


class ExpectedTotals(_Model):
    subtotal: Decimal
    discount_amount: Decimal
    tax_amount: Decimal
    total_amount: Decimal


class Expected(_Model):
    lines: List[ExpectedLine] = []
    totals: Optional[ExpectedTotals] = None
    status: Optional[QuoteStatus] = None
    approval_required: bool = False
    # True: the assistant must ask a question and must not create any quote line.
    clarification_expected: bool = False
    # Cost, margin and derived numbers that must never appear in assistant text.
    forbidden_values: List[Decimal] = []


class Task(_Model):
    id: str
    category: Category
    split: Split
    user_role: UserRole
    turns: List[str] = Field(min_length=1)
    expected: Expected
    # Data planted before the run (red-team injections). Applied inside the run's rolled-back transaction.
    setup: List[Dict[str, Any]] = Field(default_factory=list)
