from fastapi import APIRouter, Depends, status, Query
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.core.database import get_db
from backend.app.domains.auth.routes import get_current_user
from backend.app.domains.auth.models import User
from backend.app.domains.approval.schemas import (
    ApprovalPolicyCreate, ApprovalPolicyRead, SubmitApprovalRequest,
    ApprovalRequestRead, DecideApprovalRequest
)
from backend.app.domains.approval.services import ApprovalService
from backend.app.core.exceptions import EntityNotFoundError

router = APIRouter(prefix="/approvals", tags=["approval-workflow"])

def _get_user_roles_and_permissions(user: User):
    roles = [r.name for r in (user.roles or [])]
    perms = {p.name for r in (user.roles or []) for p in getattr(r, "permissions", [])}
    return roles, perms

@router.post("/policies", response_model=ApprovalPolicyRead, status_code=status.HTTP_201_CREATED)
async def create_policy(
    schema: ApprovalPolicyCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Register a new approval policy (Admin / Manager).
    """
    service = ApprovalService(db)
    return await service.create_policy(schema)

@router.get("/policies", response_model=List[ApprovalPolicyRead])
async def list_policies(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List active approval policies.
    """
    service = ApprovalService(db)
    return await service.approval_repo.list_active_policies()

@router.post("/submit", response_model=List[ApprovalRequestRead])
async def submit_quote(
    request: SubmitApprovalRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Submit a quote for approval routing. If it triggers policies, pending tasks are created.
    """
    service = ApprovalService(db)
    reqs = await service.check_and_submit_quote(request, current_user=current_user)
    await db.commit()
    return reqs

@router.get("/requests", response_model=List[ApprovalRequestRead])
async def list_all_requests(
    status: Optional[str] = Query(None, description="Filter by status: PENDING, APPROVED, REJECTED"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List all approval requests across quotes with optional status filter.
    """
    service = ApprovalService(db)
    return await service.approval_repo.list_all_requests(status=status)

@router.get("/pending", response_model=List[ApprovalRequestRead])
async def list_pending_requests(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List pending approval requests waiting for sign-off.
    Administrators and Executives see all pending requests; other roles see requests matching their role.
    """
    service = ApprovalService(db)
    roles, perms = _get_user_roles_and_permissions(current_user)
    is_privileged = any(r.lower() in ("administrator", "admin", "executive") for r in roles) or "approval.manage" in perms

    if is_privileged:
        return await service.approval_repo.list_pending_requests()
    return await service.approval_repo.list_pending_requests(roles=roles)

@router.get("/history", response_model=List[ApprovalRequestRead])
async def list_completed_requests(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List completed (approved / rejected) approval history.
    """
    service = ApprovalService(db)
    return await service.approval_repo.list_history_requests()

@router.get("/requests/{request_id}", response_model=ApprovalRequestRead)
async def get_approval_request(
    request_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Retrieve full details for a single approval request including line items and customer info.
    """
    service = ApprovalService(db)
    req = await service.approval_repo.get_request_by_id(request_id)
    if not req:
        raise EntityNotFoundError(f"Approval request {request_id} not found.")
    return req

@router.post("/requests/{request_id}/decide", response_model=ApprovalRequestRead)
async def decide_approval_request(
    request_id: int,
    decision: DecideApprovalRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Sign off or reject a pending approval request.
    """
    service = ApprovalService(db)
    roles, perms = _get_user_roles_and_permissions(current_user)
    req = await service.decide_request(
        request_id=request_id,
        user_id=current_user.id,
        user_roles=roles,
        user_permissions=perms,
        decision=decision
    )
    await db.commit()
    return req

