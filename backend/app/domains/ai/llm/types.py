"""Provider-neutral message and response types used by the orchestrator."""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    args: Dict[str, Any]
    # Gemini 3 models require the signature to be sent back with the function call that carried it.
    thought_signature: Optional[bytes] = None


@dataclass
class Message:
    role: Literal["system", "user", "assistant", "tool"]
    content: str = ""
    tool_calls: List[ToolCall] = field(default_factory=list)
    tool_call_id: Optional[str] = None
    name: Optional[str] = None


@dataclass
class LLMResponse:
    text: str = ""
    tool_calls: List[ToolCall] = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0
    model_version: str = ""
    latency_ms: float = 0.0


class ProviderError(Exception):
    """The model call failed (network, auth, quota, malformed response)."""
