"""
Runs tools as a user. Every call is validated, permission-checked, executed through services, masked,
and recorded in `trace`. Nothing raises past `call()`; failures come back as structured errors.
"""
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.core.exceptions import CPQException
from backend.app.domains.ai.tools.definitions import TOOL_BY_NAME, TOOLS, ToolContext, ToolError, Tool
from backend.app.domains.ai.tools.masking import mask_fields, user_permissions
from backend.app.domains.ai.tools.policy import AllowAllPolicy, PolicyChecker
from backend.app.domains.auth.models import Role, User

logger = logging.getLogger(__name__)


@dataclass
class TraceEntry:
    tool: str
    args: Dict[str, Any]
    ok: bool
    error_code: Optional[str]
    duration_ms: float
    result: Optional[Dict[str, Any]] = None


@dataclass
class ToolExecutor:
    user: User
    db: AsyncSession
    enforce_policy: bool = True
    mask_outputs: bool = True
    policy_checker: Optional[PolicyChecker] = None
    trace: List[TraceEntry] = field(default_factory=list)

    def __post_init__(self) -> None:
        self._user_id = self.user.id
        self.permissions = user_permissions(self.user)
        self.role = self.user.roles[0].name if self.user.roles else "Unknown"
        self.policy = self.policy_checker or AllowAllPolicy()

    async def _rollback(self) -> None:
        """
        A rollback expires every ORM object in the session, including the caller. Reload the user with
        roles and permissions so later calls never touch an expired attribute outside the async context.
        """
        await self.db.rollback()
        res = await self.db.execute(
            select(User).where(User.id == self._user_id)
            .options(selectinload(User.roles).selectinload(Role.permissions))
            .execution_options(populate_existing=True)
        )
        self.user = res.scalars().one()

    def json_schemas(self) -> List[Dict[str, Any]]:
        """Function-calling schemas for every tool, generated from the input models."""
        return [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.input_model.model_json_schema(),
                },
            }
            for t in TOOLS
        ]

    async def call(self, name: str, args: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        started = time.perf_counter()
        args = dict(args or {})
        tool = TOOL_BY_NAME.get(name)
        if tool is None:
            return self._finish(name, args, started, None, "UNKNOWN_TOOL", f"Unknown tool '{name}'.")

        try:
            parsed = tool.input_model.model_validate(args)
        except ValidationError as exc:
            # Report field names and reasons only; never echo the offending value back.
            problems = "; ".join(f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors())
            return self._finish(name, args, started, tool, "INVALID_INPUT", problems)

        if tool.permission not in self.permissions:
            return self._finish(name, args, started, tool, "FORBIDDEN", f"Missing permission: {tool.permission}.")

        try:
            ctx = ToolContext(
                db=self.db, user=self.user, permissions=self.permissions, role=self.role,
                enforce_policy=self.enforce_policy, policy=self.policy,
            )
            output = await tool.handler(ctx, parsed)
            if tool.write:
                await self.db.commit()
            payload = output.model_dump(mode="json")
            if self.mask_outputs:
                payload = mask_fields(payload, self.permissions)
            return self._finish(name, args, started, tool, None, None, payload)
        except ToolError as exc:
            await self._rollback()
            return self._finish(name, args, started, tool, exc.error_code, exc.message)
        except HTTPException as exc:
            await self._rollback()
            return self._finish(name, args, started, tool, _code_for_status(exc.status_code), str(exc.detail))
        except CPQException as exc:
            await self._rollback()
            return self._finish(name, args, started, tool, exc.error_code, exc.detail)
        except Exception:
            await self._rollback()
            logger.exception("Tool %s failed", name)
            return self._finish(name, args, started, tool, "INTERNAL_ERROR", "The operation could not be completed.")

    def _finish(
        self, name: str, args: Dict[str, Any], started: float, tool: Optional[Tool],
        error_code: Optional[str], message: Optional[str], payload: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        self.trace.append(TraceEntry(
            tool=name, args=args, ok=error_code is None, error_code=error_code,
            duration_ms=duration_ms, result=payload,
        ))
        if error_code is None:
            return {"ok": True, "data": payload}
        return {"ok": False, "error_code": error_code, "message": message}


def _code_for_status(status_code: int) -> str:
    return {400: "INVALID_INPUT", 401: "UNAUTHENTICATED", 403: "FORBIDDEN", 404: "NOT_FOUND", 409: "CONFLICT"}.get(
        status_code, "ERROR"
    )
