import uuid
from datetime import datetime
from decimal import Decimal
from typing import List, Optional, Set

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.exceptions import DomainValidationError, EntityNotFoundError
from backend.app.domains.approval.engine import STEP_ROLES, Level, RequiredApproval, evaluate
from backend.app.domains.approval.errors import ApproverRoleError, SelfApprovalError
from backend.app.domains.approval.models import ApprovalPolicy, ApprovalRequest, ApprovalStatus
from backend.app.domains.approval.repositories import ApprovalRepository
from backend.app.domains.approval.rules import load_rule_rows
from backend.app.domains.approval.schemas import ApprovalPolicyCreate, DecideApprovalRequest, SubmitApprovalRequest
from backend.app.domains.approval.snapshot import metrics_for_quote, snapshot_hash
from backend.app.domains.auth.models import User
from backend.app.domains.quotes.models import Quote, QuoteStatus
from backend.app.domains.quotes.services import QuoteService


def _sv(value) -> str:
    return value.value if hasattr(value, "value") else str(value)


def _level_for_role(role: str) -> Level:
    return Level.MANAGER if role.strip().lower() == "sales manager" else Level.EXECUTIVE


def _may_decide(step_role: str, user_roles: List[str]) -> bool:
    allowed = {step_role.lower(), "administrator"}
    return any(r.lower() in allowed for r in user_roles)


class ApprovalService:
    """
    Approval workflow. Routing comes from the pure rule engine (`engine.evaluate`). A request is bound to the
    quote's content hash, so an approval applies only to the exact content that was reviewed.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.approval_repo = ApprovalRepository(db)
        self.quote_service = QuoteService(db)

    async def create_policy(self, schema: ApprovalPolicyCreate) -> ApprovalPolicy:
        """Legacy shape (one discount or margin threshold and a role) becomes one rule row in its own group."""
        if schema.policy_type == "MARGIN":
            metric, op, threshold = "MARGIN_PERCENT", "LT", schema.margin_threshold
        else:
            metric, op, threshold = "MAX_LINE_DISCOUNT", "GE", schema.discount_threshold
        policy = ApprovalPolicy(
            name=schema.name, policy_type=schema.policy_type, discount_threshold=schema.discount_threshold,
            margin_threshold=schema.margin_threshold, role_required=schema.role_required, is_active=schema.is_active,
            metric=metric, op=op, threshold=Decimal(str(threshold)),
            required_level=_level_for_role(schema.role_required).name,
            rule_group=await self.approval_repo.next_rule_group(),
        )
        self.db.add(policy)
        await self.db.flush()
        return policy

    async def check_and_route_quote(self, quote: Quote, current_user: Optional[User] = None) -> List[ApprovalRequest]:
        """
        Evaluates the rules against the quote as it is now. No requirement: the quote is approved at once.
        Otherwise a request is opened for the exact content hash and the quote is SUBMITTED.
        """
        rows = await load_rule_rows(self.approval_repo)
        required = evaluate(rows, metrics_for_quote(quote))
        requester = current_user.id if current_user else quote.created_by_id
        role = _role_label(current_user)
        content_hash = snapshot_hash(quote)

        await self.approval_repo.supersede_pending(quote.id)

        if not required.requires_approval:
            quote.status = QuoteStatus.APPROVED
            quote.approved_snapshot_hash = content_hash
            self.db.add(quote)
            await self.db.flush()
            await self.quote_service.quote_repo.log_audit(
                quote_id=quote.id, action="QUOTE_AUTO_APPROVED", user_id=requester, user_role=role,
                after_value={"status": QuoteStatus.APPROVED.value, "level": Level.NONE.name, "snapshot_hash": content_hash},
            )
            await self.quote_service.emit_event("quote.approved", quote)
            return []

        policy_id = _first_policy_id(rows, required)
        req = await self.approval_repo.create_routed_request(
            quote_id=quote.id, policy_id=policy_id, quote_version=quote.version, snapshot_hash=content_hash,
            required=required, requested_by_id=requester,
            reason=f"{required.level.name} sign-off required by {len(required.triggered_groups)} rule(s)",
        )
        quote.status = QuoteStatus.SUBMITTED
        self.db.add(quote)
        await self.db.flush()
        await self.quote_service.quote_repo.log_audit(
            quote_id=quote.id, action="QUOTE_SUBMITTED", user_id=requester, user_role=role,
            after_value={
                "status": QuoteStatus.SUBMITTED.value, "level": required.level.name,
                "steps": [STEP_ROLES[s] for s in required.steps], "snapshot_hash": content_hash,
            },
        )
        await self.quote_service.emit_event("quote.submitted", quote)
        return [req]

    async def check_and_submit_quote(self, request: SubmitApprovalRequest, current_user: Optional[User] = None) -> List[ApprovalRequest]:
        """API entry point to submit a quote for approval routing."""
        quote = await self.quote_service.get_quote(request.quote_id, current_user)
        if quote.status not in (QuoteStatus.DRAFT, QuoteStatus.SUBMITTED):
            raise DomainValidationError(f"Cannot submit a quote for approval if it is in '{quote.status}' state.")
        return await self.check_and_route_quote(quote, current_user)

    async def decide_request(
        self,
        request_id: int,
        user_id: uuid.UUID,
        user_roles: List[str],
        user_permissions: Set[str],
        decision: DecideApprovalRequest,
    ) -> ApprovalRequest:
        """
        Decides the open step of a request.
        - The submitter can never decide. The step's role (or Administrator) must be held.
        - Steps run in order. A rejection at any step rejects the request and the quote.
        - Final approval applies only if the quote still has the hash that was reviewed; otherwise the request is
          STALE and the quote goes back to DRAFT.
        """
        req = await self.approval_repo.get_request_by_id(request_id)
        if not req:
            raise EntityNotFoundError(f"Approval request {request_id} not found.")
        if _sv(req.status) != ApprovalStatus.PENDING.value:
            raise DomainValidationError("This request has already been decided.")
        if req.requested_by_id is not None and req.requested_by_id == user_id:
            raise SelfApprovalError()

        step = next((s for s in req.steps if s.status == "PENDING"), None)
        if step is None:
            raise DomainValidationError("This request has no open approval step.")
        if not _may_decide(step.role, user_roles):
            raise ApproverRoleError(step.role)

        now = datetime.utcnow()  # naive UTC, matching the DateTime columns
        step.status = decision.status.value
        step.decided_by_id = user_id
        step.decided_at = now
        step.comments = decision.comments
        self.db.add(step)

        quote = await self.quote_service.get_quote(req.quote_id)
        role = user_roles[0] if user_roles else step.role

        if decision.status == ApprovalStatus.REJECTED:
            req.status = ApprovalStatus.REJECTED.value
            _close(req, user_id, now, decision.comments)
            quote.status = QuoteStatus.REJECTED
            self.db.add(quote)
            await self.db.flush()
            await self.quote_service.quote_repo.log_audit(
                quote_id=quote.id, action="QUOTE_REJECTED", user_id=user_id, user_role=role,
                after_value={"status": QuoteStatus.REJECTED.value, "comments": decision.comments, "request_id": req.id, "step": step.level},
            )
            await self.quote_service.emit_event("quote.rejected", quote)
            return await self.approval_repo.get_request_by_id(req.id)

        remaining = [s for s in req.steps if s.status == "PENDING"]
        await self.db.flush()
        if remaining:
            req.assigned_role = remaining[0].role
            self.db.add(req)
            await self.quote_service.quote_repo.log_audit(
                quote_id=quote.id, action="QUOTE_APPROVAL_STEP_APPROVED", user_id=user_id, user_role=role,
                after_value={"request_id": req.id, "step": step.level, "next_role": remaining[0].role},
            )
            await self.db.flush()
            return await self.approval_repo.get_request_by_id(req.id)

        current_hash = snapshot_hash(quote)
        if current_hash != req.snapshot_hash:
            req.status = ApprovalStatus.STALE.value
            _close(req, user_id, now, "Quote changed before the final decision.")
            quote.status = QuoteStatus.DRAFT
            self.db.add(quote)
            await self.db.flush()
            await self.quote_service.quote_repo.log_audit(
                quote_id=quote.id, action="QUOTE_APPROVAL_STALE", user_id=user_id, user_role=role,
                after_value={"request_id": req.id, "reviewed_hash": req.snapshot_hash, "current_hash": current_hash},
            )
            return await self.approval_repo.get_request_by_id(req.id)

        req.status = ApprovalStatus.APPROVED.value
        _close(req, user_id, now, decision.comments)
        quote.status = QuoteStatus.APPROVED
        quote.approved_snapshot_hash = current_hash
        self.db.add(quote)
        await self.db.flush()
        await self.quote_service.quote_repo.log_audit(
            quote_id=quote.id, action="QUOTE_APPROVED", user_id=user_id, user_role=role,
            after_value={"status": QuoteStatus.APPROVED.value, "comments": decision.comments, "request_id": req.id, "snapshot_hash": current_hash},
        )
        await self.quote_service.emit_event("quote.approved", quote)
        return await self.approval_repo.get_request_by_id(req.id)


def _close(req: ApprovalRequest, user_id: uuid.UUID, now: datetime, comments: Optional[str]) -> None:
    req.decided_by_id = user_id
    req.decided_at = now
    req.comments = comments


def _first_policy_id(rows, required: RequiredApproval) -> int:
    for row in rows:
        if row.group in required.triggered_groups:
            return row.rule_id
    raise DomainValidationError("No rule matched the required approval.")


def _role_label(user: Optional[User]) -> Optional[str]:
    if user is None or not user.roles:
        return None
    return user.roles[0].name
