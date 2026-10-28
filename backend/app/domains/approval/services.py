import uuid
from datetime import datetime, timezone
from typing import List, Optional, Set
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.domains.approval.repositories import ApprovalRepository
from backend.app.domains.approval.models import ApprovalRequest, ApprovalPolicy, ApprovalStatus
from backend.app.domains.approval.schemas import (
    SubmitApprovalRequest, DecideApprovalRequest, 
    ApprovalPolicyCreate, ApprovalRequestCreate
)
from backend.app.domains.quotes.services import QuoteService
from backend.app.domains.quotes.models import Quote, QuoteStatus
from backend.app.domains.auth.models import User
from backend.app.core.exceptions import EntityNotFoundError, DomainValidationError

class ApprovalService:
    """
    Business service layer managing approval cycles.
    Validates discount thresholds, routes requests to appropriate roles,
    and updates parent quote states.
    """
    def __init__(self, db: AsyncSession):
        self.db = db
        self.approval_repo = ApprovalRepository(db)
        self.quote_service = QuoteService(db)

    async def create_policy(self, schema: ApprovalPolicyCreate) -> ApprovalPolicy:
        return await self.approval_repo.create_policy(schema)

    async def check_and_route_quote(self, quote: Quote, current_user: Optional[User] = None) -> List[ApprovalRequest]:
        """
        Internal evaluation of approval policies for a given quote.
        Routes to approval queue if discount threshold triggered;
        otherwise auto-approves the quote.
        """
        # Calculate overall discount and max line-item discount
        total_before_discount = float(quote.subtotal) if quote.subtotal > 0 else (float(quote.total_amount) + float(quote.discount_amount))
        overall_discount = 0.0
        if total_before_discount > 0:
            overall_discount = (float(quote.discount_amount) / total_before_discount) * 100.0

        max_line_discount = 0.0
        for it in (quote.items or []):
            if it.discount_percentage and float(it.discount_percentage) > max_line_discount:
                max_line_discount = float(it.discount_percentage)

        effective_discount = max(overall_discount, max_line_discount)

        active_policies = await self.approval_repo.list_active_policies()
        existing_requests = await self.approval_repo.list_requests_for_quote(quote.id)
        existing_policy_ids = {r.policy_id for r in existing_requests if r.status in (ApprovalStatus.PENDING, "pending", "PENDING")}
        triggered_requests: List[ApprovalRequest] = []

        for policy in active_policies:
            if effective_discount >= float(policy.discount_threshold):
                if policy.id not in existing_policy_ids:
                    req = await self.approval_repo.create_request(
                        ApprovalRequestCreate(
                            quote_id=quote.id,
                            policy_id=policy.id,
                            assigned_role=policy.role_required
                        )
                    )
                    triggered_requests.append(req)
                else:
                    # Already pending for this policy
                    for r in existing_requests:
                        if r.policy_id == policy.id and r.status in (ApprovalStatus.PENDING, "pending", "PENDING"):
                            triggered_requests.append(r)

        user_roles, _ = self.quote_service._extract_user_context(current_user)
        user_role_str = user_roles[0] if user_roles else "Sales Representative"
        user_id_val = current_user.id if current_user else quote.created_by_id

        if triggered_requests:
            # Quote requires review
            quote.status = QuoteStatus.SUBMITTED
            self.db.add(quote)
            await self.db.flush()

            await self.quote_service.quote_repo.log_audit(
                quote_id=quote.id,
                action="QUOTE_SUBMITTED",
                user_id=user_id_val,
                user_role=user_role_str,
                after_value={
                    "status": QuoteStatus.SUBMITTED.value,
                    "effective_discount": f"{effective_discount:.2f}%",
                    "policies_triggered": [p.assigned_role for p in triggered_requests]
                }
            )
            await self.quote_service.emit_event("quote.submitted", quote)
        else:
            # Auto-approved
            quote.status = QuoteStatus.APPROVED
            self.db.add(quote)
            await self.db.flush()

            await self.quote_service.quote_repo.log_audit(
                quote_id=quote.id,
                action="QUOTE_AUTO_APPROVED",
                user_id=user_id_val,
                user_role=user_role_str,
                after_value={
                    "status": QuoteStatus.APPROVED.value,
                    "effective_discount": f"{effective_discount:.2f}%"
                }
            )
            await self.quote_service.emit_event("quote.submitted", quote)
            await self.quote_service.emit_event("quote.approved", quote)

        return triggered_requests

    async def check_and_submit_quote(self, request: SubmitApprovalRequest, current_user: Optional[User] = None) -> List[ApprovalRequest]:
        """
        API entry point to submit a quote for approval routing.
        """
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
        decision: DecideApprovalRequest
    ) -> ApprovalRequest:
        """
        Record a decision (APPROVED/REJECTED) on a pending request.
        If rejected:
        - Quote status = REJECTED
        If approved:
        - Check if all other pending approval requests for this quote are completed.
        - If all approved, mark the quote as APPROVED.
        """
        req = await self.approval_repo.get_request_by_id(request_id)
        if not req:
            raise EntityNotFoundError(f"Approval request {request_id} not found.")

        current_status_upper = req.status.upper() if isinstance(req.status, str) else req.status.value.upper()
        if current_status_upper != "PENDING":
            raise DomainValidationError("This request has already been decided.")

        # Verify RBAC role / permission match
        is_admin = any(r.lower() in ("administrator", "admin") for r in user_roles)
        is_exec = any(r.lower() == "executive" for r in user_roles)
        has_manage_perm = "approval.manage" in user_permissions or "quotes.approve" in user_permissions
        role_matches = any(r.lower() == req.assigned_role.lower() for r in user_roles)

        if not (is_admin or is_exec or has_manage_perm or role_matches):
            raise DomainValidationError(
                f"Unauthorized. User roles {user_roles} do not have permission to decide requests for assigned role '{req.assigned_role}'."
            )

        # Update request state
        decision_status_enum = ApprovalStatus(decision.status)
        req.status = decision_status_enum
        req.comments = decision.comments
        req.decided_by_id = user_id
        req.decided_at = datetime.utcnow()
        self.db.add(req)
        await self.db.flush()


        # Update parent Quote state
        quote = await self.quote_service.get_quote(req.quote_id)
        primary_role = user_roles[0] if user_roles else "Manager"

        if decision_status_enum == ApprovalStatus.REJECTED:
            quote.status = QuoteStatus.REJECTED
            self.db.add(quote)
            await self.db.flush()
            await self.quote_service.quote_repo.log_audit(
                quote_id=quote.id,
                action="QUOTE_REJECTED",
                user_id=user_id,
                user_role=primary_role,
                after_value={
                    "status": QuoteStatus.REJECTED.value,
                    "comments": decision.comments,
                    "request_id": req.id
                }
            )
            await self.quote_service.emit_event("quote.rejected", quote)
        elif decision_status_enum == ApprovalStatus.APPROVED:
            all_requests = await self.approval_repo.list_requests_for_quote(req.quote_id)
            all_approved = True
            for r in all_requests:
                r_status = r.status.upper() if isinstance(r.status, str) else r.status.value.upper()
                if r_status != "APPROVED":
                    all_approved = False
                    break

            if all_approved:
                quote.status = QuoteStatus.APPROVED
                self.db.add(quote)
                await self.db.flush()
                await self.quote_service.quote_repo.log_audit(
                    quote_id=quote.id,
                    action="QUOTE_APPROVED",
                    user_id=user_id,
                    user_role=primary_role,
                    after_value={
                        "status": QuoteStatus.APPROVED.value,
                        "comments": decision.comments,
                        "request_id": req.id
                    }
                )
                await self.quote_service.emit_event("quote.approved", quote)

        # Reload with all relationship options
        return await self.approval_repo.get_request_by_id(req.id)

