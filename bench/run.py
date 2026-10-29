"""
CPQ-Bench runner.

    python -m bench.run --arm C --provider gemini --model gemini-2.5-flash --k 5 --split test --out results/c.jsonl --resume

Arms:  A  no tools; catalog excerpt in the prompt; the model answers with a JSON quote draft.
       B  tools, no policy and no masking (cost/margin secrecy is requested in the prompt only).
       B2 as B, with a strong prompt-only confidentiality instruction: separates prompt-only masking from tool-layer masking.
       C  tools with the approval policy checker and output masking.
Every run happens inside a transaction that is rolled back afterwards, so runs never see each other's quotes.
"""
import argparse
import asyncio
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from backend.app.core.config import settings
from backend.app.domains.ai.llm import Message, Orchestrator, ProviderError, build_provider
from backend.app.domains.ai.llm.orchestrator import QUOTE_TOOLS
from backend.app.domains.ai.llm.types import LLMResponse
from backend.app.domains.ai.prompts import SYSTEM_PROMPT
from backend.app.domains.ai.tools import ToolExecutor
from backend.app.domains.approval.checker import ApprovalPolicyChecker
from bench.catalog_gen import plan as catalog_plan
from bench.draft import draft_to_state, parse_draft
from bench.generate_tasks import load_tasks
from bench.harness import isolated_session, load_role_user
from bench.prompts import B2_PROMPT, catalog_excerpt, system_prompt
from bench.redteam.exposure import exposed, trace_exposure
from bench.redteam.inject import InjectingExecutor, apply_setup, tool_injections
from bench.schema import Task
from bench.scorer import ActualRun, ErrorClass, allowed_values, score
from bench.state import extract_state

ARMS = ("A", "B", "B2", "C")
RunKey = Tuple[str, str, str, int]


class NullProvider:
    """Always answers with plain text and never calls a tool: a do-nothing baseline for dry runs."""
    name = "mock"

    async def generate(self, messages, tools, *, temperature=0.0, seed=None) -> LLMResponse:
        return LLMResponse(text="I cannot help with that.", model_version="null")


def make_provider(name: str, model: str, base_url: str = ""):
    if name == "mock":
        return NullProvider()
    provider = build_provider(name, api_key=settings.GEMINI_API_KEY, model=model, base_url=base_url or settings.LLM_BASE_URL)
    if provider is None:
        raise ProviderError(f"Unknown or unconfigured provider '{name}'.")
    return provider


@dataclass
class RunSettings:
    arm: str
    provider_name: str
    model: str
    temperature: float = 0.0
    n_products: int = 300
    catalog_seed: int = 1234


def _quote_ids(trace: List[Dict[str, Any]]) -> List[int]:
    ids: List[int] = []
    for entry in trace:
        result = entry.get("result")
        if entry.get("tool") in QUOTE_TOOLS and entry.get("ok") and isinstance(result, dict) and isinstance(result.get("id"), int):
            if result["id"] not in ids:
                ids.append(result["id"])
    return ids


async def _run_arm_a(provider, task: Task, db, cfg: RunSettings, seed: int):
    all_skus = [p.sku for p in catalog_plan(cfg.n_products, cfg.catalog_seed).products]
    excerpt = await catalog_excerpt(db, task.turns, task.id, all_skus)
    messages: List[Message] = [Message("system", system_prompt(excerpt))]
    usage = {"input_tokens": 0, "output_tokens": 0, "model_calls": 0}
    replies: List[str] = []
    version, stopped = "", "final"
    for turn in task.turns:
        messages.append(Message("user", turn))
        try:
            response = await provider.generate(messages, [], temperature=cfg.temperature, seed=seed)
        except ProviderError:
            stopped = "provider_error"
            break
        usage["model_calls"] += 1
        usage["input_tokens"] += response.input_tokens
        usage["output_tokens"] += response.output_tokens
        version = response.model_version or version
        replies.append(response.text)
        messages.append(Message("assistant", response.text))
    draft, error = parse_draft(replies[-1]) if replies else (None, "no reply")
    trace: List[Dict[str, Any]] = []
    if draft is None:
        trace.append({"tool": "draft", "args": {}, "ok": False, "error_code": "INVALID_INPUT", "result": {"detail": error}})
    state = draft_to_state(draft) if draft else {"quotes": []}
    return state, replies, trace, usage, version, [stopped]


async def _run_tool_arm(provider, task: Task, db, cfg: RunSettings, seed: int):
    user = await load_role_user(db, task.user_role)
    if cfg.arm in ("B", "B2"):
        executor = InjectingExecutor(user, db, enforce_policy=False, mask_outputs=False)
    else:
        executor = InjectingExecutor(user, db, enforce_policy=True, mask_outputs=True, policy_checker=ApprovalPolicyChecker(db))
    executor.injections = tool_injections(task.setup)
    prompt = B2_PROMPT if cfg.arm == "B2" else SYSTEM_PROMPT
    orchestrator = Orchestrator(provider, executor, temperature=cfg.temperature, seed=seed, system_prompt=prompt)
    history: List[Message] = []
    usage = {"input_tokens": 0, "output_tokens": 0, "model_calls": 0}
    replies: List[str] = []
    stops: List[str] = []
    version, trace = "", []
    for turn in task.turns:
        result = await orchestrator.run(turn, history)
        history += [Message("user", turn), Message("assistant", result.reply)]
        replies.append(result.reply)
        stops.append(result.stopped_reason)
        for key in usage:
            usage[key] += result.usage.get(key, 0)
        version = result.model_version or version
        trace = result.trace  # the executor trace is cumulative across turns
    state = await extract_state(db, _quote_ids(trace))
    return state, replies, trace, usage, version, stops


async def run_task(provider, task: Task, trial: int, cfg: RunSettings) -> Dict[str, Any]:
    started = time.perf_counter()
    record: Dict[str, Any] = {
        "task_id": task.id, "category": task.category.value, "split": task.split.value, "arm": cfg.arm,
        "provider": cfg.provider_name, "model": cfg.model, "model_version": "", "temperature": cfg.temperature,
        "trial": trial, "seed": trial, "trace": [], "replies": [], "score": None, "error_classes": [],
        "disclosure": False, "tool_exposure": None, "tokens": {"input_tokens": 0, "output_tokens": 0, "model_calls": 0},
        "latency_ms": 0.0, "stopped_reasons": [], "error": None,
    }
    try:
        async with isolated_session() as db:
            await apply_setup(db, task.setup)
            runner = _run_arm_a if cfg.arm == "A" else _run_tool_arm
            state, replies, trace, usage, version, stops = await runner(provider, task, db, cfg, trial)
            verdict = score(task, ActualRun(state=state, assistant_texts=replies, trace=trace))
        classes = sorted({c.value for c in verdict.classes})
        record.update(
            model_version=version, trace=trace, replies=replies, tokens=usage, stopped_reasons=stops,
            score={"passed": verdict.passed, "failures": [{"cls": f.cls.value, "detail": f.detail} for f in verdict.failures]},
            error_classes=classes, disclosure=ErrorClass.DISCLOSURE.value in classes,
        )
        # What the model was shown, from the trace: any non-null cost/margin field or forbidden figure in a tool result.
        if cfg.arm != "A":
            report = trace_exposure(trace, task.expected.forbidden_values, allowed_values(task.expected))
            record["tool_exposure"] = {"seen": exposed(report), **report}
    except Exception as exc:  # one broken run must not stop a sweep; it is logged and retried on --resume
        record["error"] = f"{type(exc).__name__}: {str(exc)[:300]}"
    record["latency_ms"] = round((time.perf_counter() - started) * 1000, 2)
    return record


def completed_keys(path: Path) -> Set[RunKey]:
    """Runs already on disk. A record that ended in an exception is not complete and will be run again."""
    keys: Set[RunKey] = set()
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rec = json.loads(line)
                if rec.get("error") is None:
                    keys.add((rec["task_id"], rec["arm"], rec["model"], rec["trial"]))
    return keys


async def run_all(
    provider, tasks: Sequence[Task], cfg: RunSettings, *, k: int, out: Path, resume: bool = False,
    max_runs: Optional[int] = None,
) -> Dict[str, int]:
    """
    Tasks outer, trials inner. `max_runs` is a hard cap on runs started in this call; it is checked before each run,
    so nothing past the cap is ever started. With `resume` the cap applies to new runs only.
    """
    out.parent.mkdir(parents=True, exist_ok=True)
    done = completed_keys(out) if resume else set()
    stats = {"executed": 0, "skipped": 0, "errors": 0, "passed": 0}
    with out.open("a", encoding="utf-8", newline="\n") as fh:
        for task in tasks:
            for trial in range(k):
                if (task.id, cfg.arm, cfg.model, trial) in done:
                    stats["skipped"] += 1
                    continue
                if max_runs is not None and stats["executed"] >= max_runs:
                    return stats
                record = await run_task(provider, task, trial, cfg)
                fh.write(json.dumps(record, default=str) + "\n")
                fh.flush()
                stats["executed"] += 1
                stats["errors"] += record["error"] is not None
                stats["passed"] += bool(record["score"] and record["score"]["passed"])
    return stats


def main(argv: Optional[Sequence[str]] = None) -> None:
    ap = argparse.ArgumentParser(description="Run CPQ-Bench.")
    ap.add_argument("--arm", choices=ARMS, required=True)
    ap.add_argument("--provider", choices=["gemini", "openai_compatible", "mock"], required=True)
    ap.add_argument("--model", default="none")
    ap.add_argument("--base-url", default="")
    ap.add_argument("--temperature", type=float, default=0.0)
    ap.add_argument("--k", type=int, default=5, help="trials per task")
    ap.add_argument("--split", choices=["dev", "test"], default="test")
    ap.add_argument("--categories", nargs="*", default=None)
    ap.add_argument("--tasks", type=Path, default=Path("bench/tasks"))
    ap.add_argument("--max-runs", type=int, default=None, help="hard cap on runs started by this invocation")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--products", type=int, default=300, help="catalog size the tasks were generated with")
    args = ap.parse_args(argv)

    tasks = load_tasks(args.tasks, args.split, args.categories)
    provider = make_provider(args.provider, args.model, args.base_url)
    cfg = RunSettings(args.arm, args.provider, args.model, args.temperature, n_products=args.products)
    stats = asyncio.run(run_all(provider, tasks, cfg, k=args.k, out=args.out, resume=args.resume, max_runs=args.max_runs))
    print(json.dumps({"tasks": len(tasks), **stats}))


if __name__ == "__main__":
    main()
