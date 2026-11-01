"""
Gemini 3 models reject a tool-call follow-up unless the thought signature from the function call is sent back.
These tests use a fake client, so they need no network or API key.
"""
import asyncio
from types import SimpleNamespace

from google.genai import types

from backend.app.domains.ai.llm.providers import GeminiProvider
from backend.app.domains.ai.llm.types import Message, ToolCall


class _FakeModels:
    def __init__(self, response):
        self.response = response
        self.sent = None

    async def generate_content(self, *, model, contents, config):
        self.sent = contents
        return self.response


def _provider(response) -> GeminiProvider:
    provider = GeminiProvider.__new__(GeminiProvider)
    provider._model = "gemini-3.5-flash-lite"
    provider._client = SimpleNamespace(aio=SimpleNamespace(models=_FakeModels(response)))
    return provider


def _function_call_response(signature: bytes) -> types.GenerateContentResponse:
    part = types.Part(
        function_call=types.FunctionCall(id="call-1", name="search_products", args={"query": "BENCH"}),
        thought_signature=signature,
    )
    return types.GenerateContentResponse(
        candidates=[types.Candidate(content=types.Content(role="model", parts=[part]))],
        model_version="gemini-3.5-flash-lite",
    )


def test_signature_is_kept_on_the_parsed_tool_call():
    provider = _provider(_function_call_response(b"sig-abc"))
    response = asyncio.run(provider.generate([Message("user", "hi")], []))
    assert response.tool_calls[0].thought_signature == b"sig-abc"


def test_signature_is_sent_back_on_the_function_call_part():
    provider = _provider(_function_call_response(b"sig-abc"))
    messages = [
        Message("user", "hi"),
        Message("assistant", tool_calls=[ToolCall(id="call-1", name="search_products", args={"query": "BENCH"},
                                                  thought_signature=b"sig-abc")]),
        Message("tool", content="{}", tool_call_id="call-1", name="search_products"),
    ]
    asyncio.run(provider.generate(messages, []))
    model_turn = provider._client.aio.models.sent[1]
    assert model_turn.parts[0].function_call.name == "search_products"
    assert model_turn.parts[0].thought_signature == b"sig-abc"


def test_calls_without_a_signature_are_unchanged():
    provider = _provider(_function_call_response(b"x"))
    contents = provider._contents([Message("assistant", tool_calls=[ToolCall(id="c", name="n", args={})])])
    assert contents[0].parts[0].thought_signature is None
