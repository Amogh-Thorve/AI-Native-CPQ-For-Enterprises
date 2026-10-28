from backend.app.core.exceptions import CPQException


class SelfApprovalError(CPQException):
    """The person who submitted a quote tried to approve it."""

    def __init__(self):
        super().__init__(
            detail="You cannot approve a quote you submitted.",
            error_code="SELF_APPROVAL_NOT_ALLOWED",
            status_code=403,
        )


class ApproverRoleError(CPQException):
    """The caller does not hold the role the open approval step requires."""

    def __init__(self, role: str):
        super().__init__(
            detail=f"This approval step needs the {role} role.",
            error_code="APPROVER_ROLE_REQUIRED",
            status_code=403,
            details={"required_role": role},
        )
