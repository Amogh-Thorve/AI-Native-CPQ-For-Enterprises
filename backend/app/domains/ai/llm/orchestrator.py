"""
Runs the model/tool loop: model -> tool calls -> executor -> tool results -> model, until a final answer
or a stop condition. The executor is used exactly as it is; this module only sequences calls.
"""
import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence

from backend.app.domains.ai.llm.types import Message, ProviderError
from backend.app.domains.ai.prompts import SYSTEM_PROMPT
from backend.app.domains.ai.tools.executor import ToolExecutor

QUOTE_TOOLS = {
    "create_quote", "add_quote_item", "update_quote_item", "remove_quote_item",
    "get_quote", "submit_quote", "revise_quote",
}

STOP_FINAL = "final"
STOP_MAX_STEPS = "max_steps"
STOP_PROVIDER_ERROR = "provider_error"

MAX_STEPS_REPLY = "I could not finish that within the allowed number of steps. Please narrow the request and try again."
PROVIDER_ERROR_REPLY = "The quote assistant is unavailable right now. Please try again shortly."


@dataclass
class OrchestratorResult:
    reply: str
    trace: List[Dict[str, Any]]
    usage: Dict[str, int]
    stopped_reason: str
    quote_id: Optional[int] = None
    model_version: str = ""


class Orchestrator:
    def __init__(self, provider, executor: ToolExecutor, *, max_steps: int = 8, temperature: float = 0.0, seed: Optional[int] = None):
        if max_steps < 1:
            raise ValueError("max_steps must be at least 1")
        self.provider = provider
        self.executor = executor
        self.max_steps = max_steps
        self.temperature = temperature
        self.seed = seed

    async def run(self, user_message: str, history: Sequence[Message] = ()) -> OrchestratorResult:
        messages: List[Message] = [Message("system", SYSTEM_PROMPT), *history, Message("user", user_message)]
        tools = self.executor.json_schemas()
        usage = {"input_tokens": 0, "output_tokens": 0, "model_calls": 0}
        model_version = ""

        for _ in range(self.max_steps):
            try:
                response = await self.provider.generate(messages, tools, temperature=self.temperature, seed=self.seed)
            except ProviderError:
                return self._result(PROVIDER_ERROR_REPLY, STOP_PROVIDER_ERROR, usage, model_version)

            usage["model_calls"] += 1
            usage["input_tokens"] += response.input_tokens
            usage["output_tokens"] += response.output_tokens
            model_version = response.model_version or model_version

            if not response.tool_calls:
                return self._result(response.text, STOP_FINAL, usage, model_version)

            messages.append(Message("assistant", content=response.text, tool_calls=list(response.tool_calls)))
            for call in response.tool_calls:
                result = await self.executor.call(call.name, call.args)
                messages.append(Message(
                    "tool", content=json.dumps(result, default=str), tool_call_id=call.id, name=call.name,
                ))

        return self._result(MAX_STEPS_REPLY, STOP_MAX_STEPS, usage, model_version)

    def _result(self, reply: str, stopped_reason: str, usage: Dict[str, int], model_version: str) -> OrchestratorResult:
        return OrchestratorResult(
            reply=reply.strip(),
            trace=[self._trace_dict(t) for t in self.executor.trace],
            usage=usage,
            stopped_reason=stopped_reason,
            quote_id=self._last_quote_id(),
            model_version=model_version,
        )

    def _last_quote_id(self) -> Optional[int]:
        for entry in reversed(self.executor.trace):
            if entry.tool in QUOTE_TOOLS and entry.ok and isinstance(entry.result, dict):
                quote_id = entry.result.get("id")
                if isinstance(quote_id, int):
                    return quote_id
        return None

    @staticmethod
    def _trace_dict(entry) -> Dict[str, Any]:
        return {
            "tool": entry.tool, "args": entry.args, "ok": entry.ok, "error_code": entry.error_code,
            "duration_ms": entry.duration_ms, "result": entry.result,
        }
