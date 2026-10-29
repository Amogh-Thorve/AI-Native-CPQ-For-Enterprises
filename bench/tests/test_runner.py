"""
Generator and runner tests. MockProvider only: no network, no LLM. Database tests use the local dev DB like the
other domain tests, and every run inside the runner is rolled back.
"""
import json
import re
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import func, select

from backend.app.core.database import SessionLocal
from backend.app.domains.ai.llm.providers import MockProvider
from backend.app.domains.ai.llm.types import LLMResponse, ToolCall
from backend.app.domains.catalog.models import Product
from backend.app.domains.quotes.models import Quote
from bench.catalog_gen import PREFIX, generate, sku_for
from bench.generate_tasks import generate_tasks, load_tasks, write_tasks
from bench.run import NullProvider, RunSettings, completed_keys, run_all, run_task
from bench.templates import TEMPLATES

N = 40
CATEGORIES = list(TEMPLATES)
_CACHE = {}


async def one_task(category: str, pick=None):
    """A generated task of this category (cached; generation runs the real services)."""
    if category not in _CACHE:
        _CACHE[category] = await generate_tasks(
            per_category=8, dev_fraction=0.5, seed=3, n_products=N, categories=[category],
        )
    tasks = _CACHE[category]
    return next(t for t in tasks if pick is None or pick(t))


async def world():
    async with SessionLocal() as db:
        return await generate(db, N)


async def quote_count() -> int:
    async with SessionLocal() as db:
        return (await db.execute(select(func.count()).select_from(Quote))).scalar_one()


def customer_of(task) -> str:
    return re.search(rf"{PREFIX}C\d{{3}}", " ".join(task.turns)).group(0)


def cfg(arm: str, model: str = "mock-model") -> RunSettings:
    return RunSettings(arm=arm, provider_name="mock", model=model, n_products=N)


def say(text: str) -> LLMResponse:
    return LLMResponse(text=text, model_version="mock-1", input_tokens=10, output_tokens=5)


def call(name: str, **args) -> LLMResponse:
    return LLMResponse(tool_calls=[ToolCall(id=f"c-{name}", name=name, args=args)], input_tokens=10, output_tokens=5)


def draft_json(task) -> str:
    e = task.expected
    return "Here you go.\n```json\n" + json.dumps({
        "clarification": None, "customer_number": customer_of(task), "status": e.status.value,
        "approval_required": e.approval_required,
        "lines": [{"sku": l.sku, "qty": l.qty, "unit_price": str(l.unit_price), "line_total": str(l.line_total)} for l in e.lines],
        "totals": {k: str(v) for k, v in e.totals.model_dump().items()},
    }) + "\n```"


# ─── Generator ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_generator_counts_split_determinism_and_leaves_no_quotes(tmp_path):
    before = await quote_count()
    kwargs = dict(per_category=4, dev_fraction=0.5, seed=11, n_products=N)
    first = await generate_tasks(**kwargs)
    second = await generate_tasks(**kwargs)
    assert await quote_count() == before

    for name, tasks in (("a", first), ("b", second)):
        write_tasks(tasks, tmp_path / name, {"seed": 11})
    files = sorted(p.name for p in (tmp_path / "a").iterdir())
    assert files == sorted([f"{c}.jsonl" for c in CATEGORIES] + ["MANIFEST.json"])
    for f in files:
        assert (tmp_path / "a" / f).read_bytes() == (tmp_path / "b" / f).read_bytes()

    manifest = json.loads((tmp_path / "a" / "MANIFEST.json").read_text())
    assert all(v == {"total": 4, "dev": 2, "test": 2} for v in manifest["counts"].values())
    loaded = load_tasks(tmp_path / "a")
    assert len(loaded) == 4 * len(CATEGORIES)
    assert len(load_tasks(tmp_path / "a", split="dev")) == 2 * len(CATEGORIES)
    for t in loaded:
        if t.category.value == "ambiguity":
            assert t.expected.clarification_expected and not t.expected.lines
        if t.expected.lines:
            assert t.expected.totals is not None and t.expected.status is not None


@pytest.mark.asyncio
async def test_generated_expectations_cover_the_awkward_cases():
    traps = await generate_tasks(per_category=12, dev_fraction=0.3, seed=5, n_products=N, categories=["permission_trap"])
    assert any(t.expected.forbidden_values for t in traps)
    policy = await generate_tasks(per_category=12, dev_fraction=0.3, seed=5, n_products=N, categories=["policy_limit"])
    assert any(t.expected.approval_required for t in policy) and any(not t.expected.approval_required for t in policy)
    edge = await generate_tasks(per_category=12, dev_fraction=0.3, seed=5, n_products=N, categories=["pricing_edge"])
    assert {l.qty for t in edge for l in t.expected.lines} & {9, 10, 49, 50, 51, 11}


# ─── Arm A ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_arm_a_correct_draft_passes_wrong_total_is_pricing_garbage_is_syntactic():
    task = await one_task("simple_quote")
    good = await run_task(MockProvider([say(draft_json(task))]), task, 0, cfg("A"))
    assert good["error"] is None and good["score"]["passed"], good["score"]
    assert good["tokens"]["model_calls"] == 1 and good["model_version"] == "mock-1"

    wrong = draft_json(task).replace(str(task.expected.totals.total_amount), "1.23")
    bad = await run_task(MockProvider([say(wrong)]), task, 0, cfg("A"))
    assert bad["error_classes"] == ["pricing"]

    garbage = await run_task(MockProvider([say("sure, quote done")]), task, 0, cfg("A"))
    assert "syntactic" in garbage["error_classes"]


@pytest.mark.asyncio
async def test_arm_a_prompt_has_catalog_and_no_tools():
    task = await one_task("simple_quote")
    provider = MockProvider([say(draft_json(task))])
    await run_task(provider, task, 0, cfg("A"))
    system = provider.calls[0][0].content
    assert task.expected.lines[0].sku in system and "Tax:" in system and "```json" in system
    assert provider.tool_names_seen == [[]]


# ─── Arms B and C ───────────────────────────────────────────────────────────

async def scripted_create(task, report):
    items = [{"product_id": report.product_ids[l.sku], "quantity": l.qty} for l in task.expected.lines]
    return [
        call("create_quote", customer_id=report.customer_ids[customer_of(task)], title="bench", items=items),
        say("Created."),
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize("arm", ["B", "C"])
async def test_tool_arms_reproduce_the_expected_state(arm):
    report = await world()
    task = await one_task("simple_quote", lambda t: t.user_role == "Sales Representative")
    before = await quote_count()
    rec = await run_task(MockProvider(await scripted_create(task, report)), task, 0, cfg(arm))
    assert rec["error"] is None and rec["score"]["passed"], rec["score"]
    assert rec["trace"][0]["tool"] == "create_quote" and rec["trace"][0]["ok"]
    assert await quote_count() == before


@pytest.mark.asyncio
async def test_masking_is_the_difference_between_arm_b_and_arm_c():
    report = await world()
    task = await one_task("simple_quote", lambda t: t.user_role == "Sales Representative")
    steps = await scripted_create(task, report)
    # get_quote needs the id of the quote just made; the executor result carries it, so read it from the trace via a tiny provider.

    class CreateThenGet(MockProvider):
        async def generate(self, messages, tools, *, temperature=0.0, seed=None):
            for m in reversed(messages):
                if m.role == "tool" and '"ok": true' in m.content and not getattr(self, "_asked", False):
                    self._asked = True
                    qid = json.loads(m.content)["data"]["id"]
                    return call("get_quote", quote_id=qid)
            return await super().generate(messages, tools, temperature=temperature, seed=seed)

    seen = {}
    for arm in ("B", "C"):
        rec = await run_task(CreateThenGet(list(steps[:1]) + [say("Done.")]), task, 0, cfg(arm))
        got = next(t for t in rec["trace"] if t["tool"] == "get_quote")
        seen[arm] = got["result"]["items"][0]["margin_amount"]
    assert seen["B"] is not None
    assert seen["C"] is None


@pytest.mark.asyncio
async def test_policy_checker_blocks_over_limit_line_in_arm_c_only():
    report = await world()
    task = await one_task("simple_quote", lambda t: t.user_role == "Sales Representative")
    pid = report.product_ids[sku_for(1)]  # LINE_DISCOUNT product

    def script():
        return [
            call("create_quote", customer_id=report.customer_ids[customer_of(task)], title="bench", items=[]),
            LLMResponse(tool_calls=[ToolCall(id="c2", name="add_quote_item", args={"quote_id": 0, "product_id": pid, "quantity": 1, "discount_percent": 25})]),
            say("Done."),
        ]

    class FixQuoteId(MockProvider):
        async def generate(self, messages, tools, *, temperature=0.0, seed=None):
            resp = await super().generate(messages, tools, temperature=temperature, seed=seed)
            for tc in resp.tool_calls:
                if tc.name == "add_quote_item":
                    for m in reversed(messages):
                        if m.role == "tool" and m.name == "create_quote":
                            tc.args["quote_id"] = json.loads(m.content)["data"]["id"]
            return resp

    codes = {}
    for arm in ("B", "C"):
        rec = await run_task(FixQuoteId(script()), task, 0, cfg(arm))
        codes[arm] = next(t for t in rec["trace"] if t["tool"] == "add_quote_item")["error_code"]
    assert codes["B"] is None
    assert codes["C"] == "NEEDS_APPROVAL"


@pytest.mark.asyncio
async def test_disclosure_is_flagged_in_the_run_record():
    task = await one_task("permission_trap", lambda t: t.expected.forbidden_values and t.user_role == "Sales Representative")
    leaked = max(task.expected.forbidden_values)
    assert leaked >= 10
    leak = await run_task(MockProvider([say(f"Our cost is {leaked}.")]), task, 0, cfg("B"))
    assert leak["disclosure"] is True and "disclosure" in leak["error_classes"]
    clean = await run_task(MockProvider([say("I cannot share cost or margin.")]), task, 0, cfg("B"))
    assert clean["disclosure"] is False


# ─── Resume, cap, isolation ─────────────────────────────────────────────────

class CountingProvider(NullProvider):
    def __init__(self):
        self.calls = 0

    async def generate(self, messages, tools, *, temperature=0.0, seed=None):
        self.calls += 1
        return await super().generate(messages, tools, temperature=temperature, seed=seed)


@pytest.mark.asyncio
async def test_cap_and_resume(tmp_path):
    tasks = [await one_task(c) for c in ("simple_quote", "pricing_edge", "ambiguity")]
    out = tmp_path / "results" / "r.jsonl"
    provider = CountingProvider()

    stats = await run_all(provider, tasks, cfg("B"), k=1, out=out, max_runs=2)
    assert stats["executed"] == 2 and provider.calls == 2
    assert len(out.read_text().splitlines()) == 2

    stats = await run_all(provider, tasks, cfg("B"), k=1, out=out, resume=True)
    assert stats["executed"] == 1 and stats["skipped"] == 2 and provider.calls == 3

    stats = await run_all(provider, tasks, cfg("B"), k=1, out=out, resume=True)
    assert stats["executed"] == 0 and stats["skipped"] == 3 and provider.calls == 3
    assert len(completed_keys(out)) == 3

    # A different arm or model is a different key: nothing is skipped.
    stats = await run_all(provider, tasks[:1], cfg("C"), k=2, out=out, resume=True)
    assert stats["executed"] == 2

    rec = json.loads(out.read_text().splitlines()[0])
    for key in ("task_id", "arm", "model", "model_version", "temperature", "trial", "trace", "score",
                "error_classes", "disclosure", "tokens", "latency_ms"):
        assert key in rec


@pytest.mark.asyncio
async def test_errored_runs_are_retried_on_resume(tmp_path):
    task = await one_task("simple_quote")
    out = tmp_path / "e.jsonl"
    out.write_text(json.dumps({"task_id": task.id, "arm": "B", "model": "mock-model", "trial": 0, "error": "boom"}) + "\n")
    assert completed_keys(out) == set()
    stats = await run_all(CountingProvider(), [task], cfg("B"), k=1, out=out, resume=True)
    assert stats["executed"] == 1


@pytest.mark.asyncio
async def test_runs_are_isolated_from_each_other_and_from_the_database():
    report = await world()
    task = await one_task("simple_quote", lambda t: t.user_role == "Sales Representative")
    marker = "iso-marker-" + task.id
    before = await quote_count()

    first = await run_task(MockProvider([
        call("create_quote", customer_id=report.customer_ids[customer_of(task)], title=marker, items=[]), say("Made it."),
    ]), task, 0, cfg("B"))
    made = first["trace"][0]["result"]["id"]
    async with SessionLocal() as db:
        assert (await db.execute(select(func.count()).select_from(Quote).where(Quote.title == marker))).scalar_one() == 0
    assert await quote_count() == before

    second = await run_task(MockProvider([call("get_quote", quote_id=made), say("Looked.")]), task, 0, cfg("B"))
    lookup = second["trace"][0]
    assert lookup["ok"] is False and lookup["error_code"] == "NOT_FOUND"
