"""
Line-level policy hook. The default allows everything; the approval task replaces it with real rules.
"""
from dataclasses import dataclass
from typing import Any, Protocol, Union

from backend.app.domains.auth.models import User


@dataclass(frozen=True)
class Allow:
    pass


@dataclass(frozen=True)
class Deny:
    reason: str


@dataclass(frozen=True)
class NeedsApproval:
    reason: str


PolicyDecision = Union[Allow, Deny, NeedsApproval]


class PolicyChecker(Protocol):
    async def check_line(self, user: User, quote: Any, line: Any) -> PolicyDecision: ...


class AllowAllPolicy:
    async def check_line(self, user: User, quote: Any, line: Any) -> PolicyDecision:
        return Allow()
