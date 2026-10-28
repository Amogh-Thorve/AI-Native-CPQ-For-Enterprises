from typing import List, Optional
from sqlalchemy import select, or_, func, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from backend.app.domains.approval.models import ApprovalPolicy, ApprovalRequest, ApprovalRequestStep, ApprovalStatus
from backend.app.domains.approval.engine import RequiredApproval, STEP_ROLES
from backend.app.domains.approval.schemas import ApprovalPolicyCreate, ApprovalPolicyUpdate, ApprovalRequestCreate
from backend.app.domains.quotes.models import Quote
from backend.app.domains.auth.models import User

class ApprovalRepository:
    """
    Handles persistence logic for approval requests and discount limits.
    """
    def __init__(self, db: AsyncSession):
        self.db = db

    def _request_options(self):
        return (
            selectinload(ApprovalRequest.policy),
            selectinload(ApprovalRequest.quote).selectinload(Quote.customer),
            selectinload(ApprovalRequest.quote).selectinload(Quote.created_by).selectinload(User.roles),
            selectinload(ApprovalRequest.quote).selectinload(Quote.items)
        )

    async def get_policy_by_id(self, policy_id: int) -> Optional[ApprovalPolicy]:
        result = await self.db.execute(select(ApprovalPolicy).where(ApprovalPolicy.id == policy_id))
        return result.scalars().first()

    async def list_active_policies(self) -> List[ApprovalPolicy]:
        result = await self.db.execute(
            select(ApprovalPolicy).where(ApprovalPolicy.is_active == True).order_by(ApprovalPolicy.discount_threshold.asc())
        )
        return list(result.scalars().all())

    async def list_all_policies(self) -> List[ApprovalPolicy]:
        result = await self.db.execute(
            select(ApprovalPolicy).order_by(ApprovalPolicy.discount_threshold.asc())
        )
        return list(result.scalars().all())

    async def create_policy(self, schema: ApprovalPolicyCreate) -> ApprovalPolicy:
        db_policy = ApprovalPolicy(**schema.model_dump())
        self.db.add(db_policy)
        await self.db.flush()
        return db_policy

    async def get_request_by_id(self, request_id: int) -> Optional[ApprovalRequest]:
        result = await self.db.execute(
            select(ApprovalRequest)
            .where(ApprovalRequest.id == request_id)
            .options(*self._request_options())
        )
        return result.scalars().first()

    async def list_pending_requests(self, roles: Optional[List[str]] = None) -> List[ApprovalRequest]:
        query = select(ApprovalRequest).where(
            or_(
                ApprovalRequest.status == "PENDING",
                ApprovalRequest.status == "pending"
            )
        )
        if roles:
            roles_lower = [r.lower() for r in roles]
            query = query.where(func.lower(ApprovalRequest.assigned_role).in_(roles_lower))

        query = query.order_by(ApprovalRequest.created_at.desc()).options(*self._request_options())
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def list_pending_requests_for_role(self, role: str) -> List[ApprovalRequest]:
        return await self.list_pending_requests([role])

    async def list_history_requests(self) -> List[ApprovalRequest]:
        query = select(ApprovalRequest).where(
            or_(
                ApprovalRequest.status == "APPROVED",
                ApprovalRequest.status == "approved",
                ApprovalRequest.status == "REJECTED",
                ApprovalRequest.status == "rejected"
            )
        ).order_by(ApprovalRequest.decided_at.desc(), ApprovalRequest.created_at.desc()).options(*self._request_options())
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def list_all_requests(self, status: Optional[str] = None) -> List[ApprovalRequest]:
        query = select(ApprovalRequest)
        if status:
            s = status.upper()
            if s == "PENDING":
                query = query.where(or_(ApprovalRequest.status == "PENDING", ApprovalRequest.status == "pending"))
            elif s == "APPROVED":
                query = query.where(or_(ApprovalRequest.status == "APPROVED", ApprovalRequest.status == "approved"))
            elif s == "REJECTED":
                query = query.where(or_(ApprovalRequest.status == "REJECTED", ApprovalRequest.status == "rejected"))
        query = query.order_by(ApprovalRequest.created_at.desc()).options(*self._request_options())
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def list_requests_for_quote(self, quote_id: int) -> List[ApprovalRequest]:
        result = await self.db.execute(
            select(ApprovalRequest)
            .where(ApprovalRequest.quote_id == quote_id)
            .options(*self._request_options())
        )
        return list(result.scalars().all())

    async def create_request(self, schema: ApprovalRequestCreate) -> ApprovalRequest:
        db_req = ApprovalRequest(
            quote_id=schema.quote_id,
            policy_id=schema.policy_id,
            assigned_role=schema.assigned_role,
            status=ApprovalStatus.PENDING
        )
        self.db.add(db_req)
        await self.db.flush()
        return await self.get_request_by_id(db_req.id)

    async def list_active_rules(self) -> List[ApprovalPolicy]:
        """Rule-engine rows (rule_group > 0) that are switched on."""
        result = await self.db.execute(
            select(ApprovalPolicy)
            .where(ApprovalPolicy.is_active.is_(True), ApprovalPolicy.rule_group > 0)
            .order_by(ApprovalPolicy.rule_group, ApprovalPolicy.id)
        )
        return list(result.scalars().all())

    async def next_rule_group(self) -> int:
        result = await self.db.execute(select(func.max(ApprovalPolicy.rule_group)))
        return int(result.scalar() or 0) + 1

    async def supersede_pending(self, quote_id: int) -> None:
        await self.db.execute(
            update(ApprovalRequest)
            .where(ApprovalRequest.quote_id == quote_id, ApprovalRequest.status == ApprovalStatus.PENDING.value)
            .values(status=ApprovalStatus.SUPERSEDED.value)
            .execution_options(synchronize_session=False)
        )
        await self.db.flush()

    async def create_routed_request(
        self, *, quote_id: int, policy_id: int, quote_version: int, snapshot_hash: str,
        required: RequiredApproval, requested_by_id, reason: str,
    ) -> ApprovalRequest:
        steps = [
            ApprovalRequestStep(step_order=i + 1, level=level.name, role=STEP_ROLES[level], status="PENDING")
            for i, level in enumerate(required.steps)
        ]
        req = ApprovalRequest(
            quote_id=quote_id, policy_id=policy_id, assigned_role=steps[0].role,
            status=ApprovalStatus.PENDING.value, quote_version=quote_version, snapshot_hash=snapshot_hash,
            required_level=required.level.name, requested_by_id=requested_by_id, request_reason=reason, steps=steps,
        )
        self.db.add(req)
        await self.db.flush()
        return await self.get_request_by_id(req.id)

