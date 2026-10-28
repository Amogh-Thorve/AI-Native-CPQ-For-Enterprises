"""
Orchestrator tests. MockProvider only: no network and no real model. The tools run against the local dev
database, as the tool tests do.
"""
import pytest

from backend.app.core.database import SessionLocal
from backend.app.domains.ai.llm import (
    LLMResponse, Message, MockProvider, Orchestrator, ProviderError, ToolCall, build_provider,
)
from backend.app.domains.ai.prompts import SYSTEM_PROMPT
from backend.app.domains.ai.tests.test_tools import build_world, load_user
from backend.app.domains.ai.tools import ToolExecutor


def call(tool_id: str, name: str, args: dict, text: str = "") -> LLMResponse:
    return LLMResponse(text=text, tool_calls=[ToolCall(id=tool_id, name=name, args=args)], input_tokens=10, output_tokens=5)


def final(text: str) -> LLMResponse:
    return LLMResponse(text=text, input_tokens=7, output_tokens=3, model_version="mock-1")


@pytest.mark.asyncio
async def test_scripted_flow_creates_quote_with_priced_lines():
    async with SessionLocal() as db:
        w = await build_world(db)
        rep = await load_user(db, w["rep_a"])
        script = [
            call("c1", "search_products", {"query": w["sku"]}),
            call("c2", "price_item", {"product_id": w["product_id"], "quantity": 2}),
            call("c3", "create_quote", {"customer_id": w["cust_a"], "title": "Assistant quote",
                                        "items": [{"product_id": w["product_id"], "quantity": 2}]}),
            final("Created the quote with two laptops."),
        ]
        provider = MockProvider(script)
        executor = ToolExecutor(rep, db)
        result = await Orchestrator(provider, executor).run("Quote two laptops for Tools Co A")

        assert result.stopped_reason == "final"
        assert result.reply == "Created the quote with two laptops."
        assert [t["tool"] for t in result.trace] == ["search_products", "price_item", "create_quote"]
        assert all(t["ok"] for t in result.trace)
        assert result.quote_id is not None

        priced = result.trace[1]["result"]["total_price"]
        quote = result.trace[2]["result"]
        assert quote["subtotal"] == priced, "quote line must carry the pricing engine's total, not a model figure"
        assert quote["items"][0]["quantity"] == 2

        assert result.usage == {"input_tokens": 10 * 3 + 7, "output_tokens": 5 * 3 + 3, "model_calls": 4}
        assert result.model_version == "mock-1"
        assert provider.temperatures == [0.0, 0.0, 0.0, 0.0]


@pytest.mark.asyncio
async def test_max_steps_stops_a_model_that_keeps_calling_tools():
    async with SessionLocal() as db:
        w = await build_world(db)
        rep = await load_user(db, w["rep_a"])
        script = [call(f"c{i}", "get_quote", {"quote_id": w["quote_a"]}) for i in range(3)]
        provider = MockProvider(script)
        result = await Orchestrator(provider, ToolExecutor(rep, db), max_steps=3).run("loop forever")

        assert result.stopped_reason == "max_steps"
        assert result.usage["model_calls"] == 3
        assert len(result.trace) == 3
        assert len(provider.calls) == 3


@pytest.mark.asyncio
async def test_tool_error_is_passed_back_to_the_model():
    async with SessionLocal() as db:
        w = await build_world(db)
        rep = await load_user(db, w["rep_a"])
        script = [
            call("c1", "add_quote_item", {"quote_id": w["quote_b"], "product_id": w["product_id"], "quantity": 1}),
            final("I can't change that quote, because it isn't yours."),
        ]
        provider = MockProvider(script)
        result = await Orchestrator(provider, ToolExecutor(rep, db)).run("Add a laptop to Rep B's quote")

        assert result.stopped_reason == "final"
        assert result.trace[0]["error_code"] == "FORBIDDEN"
        second_call_messages = provider.calls[1]
        tool_messages = [m for m in second_call_messages if m.role == "tool"]
        assert len(tool_messages) == 1
        assert tool_messages[0].tool_call_id == "c1"
        assert '"error_code": "FORBIDDEN"' in tool_messages[0].content


@pytest.mark.asyncio
async def test_provider_failure_stops_with_a_plain_reply_and_keeps_the_trace():
    async with SessionLocal() as db:
        w = await build_world(db)
        rep = await load_user(db, w["rep_a"])
        provider = MockProvider([call("c1", "get_quote", {"quote_id": w["quote_a"]})])  # script runs out on step 2
        result = await Orchestrator(provider, ToolExecutor(rep, db)).run("hi")

        assert result.stopped_reason == "provider_error"
        assert "unavailable" in result.reply
        assert [t["tool"] for t in result.trace] == ["get_quote"]


@pytest.mark.asyncio
async def test_plain_answer_needs_no_tools_and_uses_temperature_zero():
    async with SessionLocal() as db:
        w = await build_world(db)
        rep = await load_user(db, w["rep_a"])
        provider = MockProvider([final("Hello.")])
        result = await Orchestrator(provider, ToolExecutor(rep, db)).run("hello")
        assert result.stopped_reason == "final" and result.trace == []
        assert provider.temperatures == [0.0]


@pytest.mark.asyncio
async def test_history_is_sent_before_the_new_message():
    async with SessionLocal() as db:
        w = await build_world(db)
        rep = await load_user(db, w["rep_a"])
        provider = MockProvider([final("ok")])
        history = [Message("user", "earlier question"), Message("assistant", "earlier answer")]
        await Orchestrator(provider, ToolExecutor(rep, db)).run("new question", history)
        sent = provider.calls[0]
        assert [m.role for m in sent] == ["system", "user", "assistant", "user"]
        assert sent[-1].content == "new question"


def test_orchestrator_rejects_a_zero_step_budget():
    with pytest.raises(ValueError):
        Orchestrator(MockProvider([]), executor=None, max_steps=0)


def test_system_prompt_names_the_real_error_codes_and_forbids_money_maths():
    for code in ("FORBIDDEN", "NEEDS_APPROVAL", "INVALID_INPUT", "POLICY_DENIED"):
        assert code in SYSTEM_PROMPT
    assert "Never compute" in SYSTEM_PROMPT and "never reveal cost or margin" in SYSTEM_PROMPT.lower()


def test_build_provider_is_off_by_default_and_rejects_incomplete_config():
    assert build_provider("none", api_key="", model="m", base_url="") is None
    with pytest.raises(ProviderError):
        build_provider("gemini", api_key="", model="m", base_url="")
    with pytest.raises(ProviderError):
        build_provider("openai_compatible", api_key="", model="m", base_url="")
