"""
Swappable model providers. Each converts the neutral Message list to its own wire format and back.

Tool schemas come from ToolExecutor.json_schemas() (OpenAI style). Gemini takes the same parameter
schema under a different envelope, so the Gemini provider converts them.
"""
import json
import time
import uuid
from typing import Any, Dict, List, Optional, Protocol, Sequence

import httpx

from backend.app.domains.ai.llm.types import LLMResponse, Message, ProviderError, ToolCall


class LLMProvider(Protocol):
    name: str

    async def generate(
        self, messages: Sequence[Message], tools: Sequence[Dict[str, Any]], *,
        temperature: float = 0.0, seed: Optional[int] = None,
    ) -> LLMResponse: ...


def _system_text(messages: Sequence[Message]) -> str:
    return "\n\n".join(m.content for m in messages if m.role == "system")


# ─── Gemini (google-genai, native function calling) ─────────────────────────

class GeminiProvider:
    name = "gemini"

    def __init__(self, api_key: str, model: str):
        from google import genai
        self._client = genai.Client(api_key=api_key)
        self._model = model

    async def generate(self, messages, tools, *, temperature=0.0, seed=None) -> LLMResponse:
        from google.genai import types

        declarations = [
            types.FunctionDeclaration(
                name=t["function"]["name"],
                description=t["function"]["description"],
                parameters_json_schema=t["function"]["parameters"],
            )
            for t in tools
        ]
        contents = self._contents(messages)
        config = types.GenerateContentConfig(
            system_instruction=_system_text(messages) or None,
            temperature=temperature,
            seed=seed,
            tools=[types.Tool(function_declarations=declarations)] if declarations else None,
        )
        started = time.perf_counter()
        try:
            resp = await self._client.aio.models.generate_content(model=self._model, contents=contents, config=config)
        except Exception as exc:
            raise ProviderError(f"Gemini call failed: {type(exc).__name__}") from exc
        latency = round((time.perf_counter() - started) * 1000, 2)

        calls: List[ToolCall] = []
        text_parts: List[str] = []
        candidates = resp.candidates or []
        parts = (candidates[0].content.parts if candidates and candidates[0].content else None) or []
        for part in parts:
            if part.function_call:
                fc = part.function_call
                calls.append(ToolCall(id=fc.id or uuid.uuid4().hex, name=fc.name, args=dict(fc.args or {})))
            elif part.text:
                text_parts.append(part.text)
        usage = resp.usage_metadata
        return LLMResponse(
            text="".join(text_parts).strip(), tool_calls=calls,
            input_tokens=(usage.prompt_token_count or 0) if usage else 0,
            output_tokens=(usage.candidates_token_count or 0) if usage else 0,
            model_version=resp.model_version or self._model, latency_ms=latency,
        )

    @staticmethod
    def _contents(messages: Sequence[Message]):
        from google.genai import types

        names: Dict[str, str] = {}
        out = []
        for m in messages:
            if m.role == "system":
                continue
            if m.role == "user":
                out.append(types.Content(role="user", parts=[types.Part(text=m.content)]))
            elif m.role == "assistant":
                parts = []
                if m.content:
                    parts.append(types.Part(text=m.content))
                for tc in m.tool_calls:
                    names[tc.id] = tc.name
                    parts.append(types.Part(function_call=types.FunctionCall(id=tc.id, name=tc.name, args=tc.args)))
                out.append(types.Content(role="model", parts=parts or [types.Part(text="")]))
            elif m.role == "tool":
                name = m.name or names.get(m.tool_call_id or "", "tool")
                out.append(types.Content(role="user", parts=[types.Part(function_response=types.FunctionResponse(
                    id=m.tool_call_id, name=name, response={"result": json.loads(m.content or "{}")},
                ))]))
        return out


# ─── OpenAI-compatible HTTP (Ollama, vLLM, LM Studio, OpenAI itself) ────────

class OpenAICompatibleProvider:
    name = "openai_compatible"

    def __init__(self, base_url: str, model: str, api_key: str = "", timeout: float = 120.0,
                 transport: Optional[httpx.AsyncBaseTransport] = None):
        self._url = base_url.rstrip("/") + "/chat/completions"
        self._model = model
        self._headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        self._timeout = timeout
        self._transport = transport

    async def generate(self, messages, tools, *, temperature=0.0, seed=None) -> LLMResponse:
        body: Dict[str, Any] = {
            "model": self._model,
            "messages": [self._message(m) for m in messages],
            "temperature": temperature,
        }
        if tools:
            body["tools"] = list(tools)
        if seed is not None:
            body["seed"] = seed
        started = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=self._timeout, transport=self._transport) as client:
                r = await client.post(self._url, json=body, headers=self._headers)
            r.raise_for_status()
            data = r.json()
            choice = data["choices"][0]["message"]
        except Exception as exc:
            raise ProviderError(f"Model server call failed: {type(exc).__name__}") from exc
        latency = round((time.perf_counter() - started) * 1000, 2)

        calls = []
        for tc in choice.get("tool_calls") or []:
            try:
                args = json.loads(tc["function"].get("arguments") or "{}")
            except json.JSONDecodeError:
                args = {"__malformed__": tc["function"].get("arguments", "")}
            calls.append(ToolCall(id=tc.get("id") or uuid.uuid4().hex, name=tc["function"]["name"], args=args))
        usage = data.get("usage") or {}
        return LLMResponse(
            text=(choice.get("content") or "").strip(), tool_calls=calls,
            input_tokens=int(usage.get("prompt_tokens") or 0), output_tokens=int(usage.get("completion_tokens") or 0),
            model_version=str(data.get("model") or self._model), latency_ms=latency,
        )

    @staticmethod
    def _message(m: Message) -> Dict[str, Any]:
        if m.role == "tool":
            return {"role": "tool", "tool_call_id": m.tool_call_id, "content": m.content}
        out: Dict[str, Any] = {"role": m.role, "content": m.content}
        if m.tool_calls:
            out["tool_calls"] = [
                {"id": tc.id, "type": "function", "function": {"name": tc.name, "arguments": json.dumps(tc.args)}}
                for tc in m.tool_calls
            ]
        return out


# ─── Scripted mock (tests only) ─────────────────────────────────────────────

class MockProvider:
    """Plays back scripted responses in order and records every message list it was sent."""
    name = "mock"

    def __init__(self, script: Sequence[LLMResponse]):
        self._script = list(script)
        self.calls: List[List[Message]] = []
        self.tool_names_seen: List[List[str]] = []
        self.temperatures: List[float] = []

    async def generate(self, messages, tools, *, temperature=0.0, seed=None) -> LLMResponse:
        self.calls.append(list(messages))
        self.tool_names_seen.append([t["function"]["name"] for t in tools])
        self.temperatures.append(temperature)
        if not self._script:
            raise ProviderError("MockProvider script exhausted")
        step = self._script.pop(0)
        return step


def build_provider(provider: str, *, api_key: str, model: str, base_url: str) -> Optional[LLMProvider]:
    if provider == "gemini":
        if not api_key:
            raise ProviderError("LLM_PROVIDER=gemini needs GEMINI_API_KEY.")
        return GeminiProvider(api_key=api_key, model=model)
    if provider == "openai_compatible":
        if not base_url:
            raise ProviderError("LLM_PROVIDER=openai_compatible needs LLM_BASE_URL.")
        return OpenAICompatibleProvider(base_url=base_url, model=model)
    return None
