"""
Seeded task generator.

    python -m bench.generate_tasks --per-category 40 --dev-fraction 0.3 --seed 7 --out bench/tasks

Natural-language turns come from templates; the expected state is computed by running each task's reference
script through the real services inside a transaction that is rolled back, so generation leaves no quotes behind.
"""
import argparse
import asyncio
import json
import random
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from backend.app.core.database import SessionLocal
from bench.catalog_gen import generate, plan
from bench.harness import expected_from, isolated_session, run_reference
from bench.schema import Category, Expected, Split, Task
from bench.templates import TEMPLATES, Ctx, Spec

DEFAULT_PER_CATEGORY = 40
DEFAULT_DEV_FRACTION = 0.3
MAX_DRAWS = 8


def build_expected(spec: Spec, result: dict) -> Expected:
    """A task where the right behaviour is to change nothing expects no quote lines; forbidden figures still apply."""
    if spec.no_quote:
        return Expected(clarification_expected=True, forbidden_values=result["sensitive"] if spec.forbidden else [])
    return expected_from(result, forbidden=spec.forbidden)


async def _one(ctx: Ctx, report, category: str, index: int, split: Split) -> Task:
    last: Optional[Exception] = None
    for _ in range(MAX_DRAWS):
        spec = TEMPLATES[category](ctx)
        try:
            async with isolated_session() as db:
                result = await run_reference(db, report, spec.role, spec.ops)
        except Exception as exc:  # a draw the services reject (e.g. an invalid revision) is simply redrawn
            last = exc
            continue
        return Task(
            id=f"{category}-{index:03d}", category=Category(category), split=split, user_role=spec.role,
            turns=spec.turns, expected=build_expected(spec, result),
        )
    raise RuntimeError(f"{category}-{index:03d}: no valid draw after {MAX_DRAWS} tries: {last!r}")


async def generate_tasks(
    per_category: int = DEFAULT_PER_CATEGORY, dev_fraction: float = DEFAULT_DEV_FRACTION, seed: int = 7,
    n_products: int = 300, catalog_seed: int = 1234, categories: Optional[Sequence[str]] = None,
) -> List[Task]:
    async with SessionLocal() as db:
        report = await generate(db, n_products, catalog_seed)
    catalog = plan(n_products, catalog_seed)
    tasks: List[Task] = []
    for category in categories or list(TEMPLATES):
        rng = random.Random(f"{seed}:{category}")
        ctx = Ctx(catalog, rng)
        order = list(range(per_category))
        random.Random(f"{seed}:{category}:split").shuffle(order)
        dev_count = round(per_category * dev_fraction)
        dev_indices = set(order[:dev_count])
        for i in range(per_category):
            split = Split.DEV if i in dev_indices else Split.TEST
            tasks.append(await _one(ctx, report, category, i + 1, split))
    return tasks


def write_tasks(tasks: Sequence[Task], out: Path, meta: Dict) -> None:
    out.mkdir(parents=True, exist_ok=True)
    by_category: Dict[str, List[Task]] = {}
    for t in tasks:
        by_category.setdefault(t.category.value, []).append(t)
    counts = {}
    for category, items in by_category.items():
        items.sort(key=lambda t: t.id)
        (out / f"{category}.jsonl").write_text("".join(t.model_dump_json() + "\n" for t in items), encoding="utf-8", newline="\n")
        counts[category] = {
            "total": len(items), "dev": sum(t.split == Split.DEV for t in items), "test": sum(t.split == Split.TEST for t in items),
        }
    manifest = {**meta, "counts": counts}
    (out / "MANIFEST.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def load_tasks(directory: Path, split: Optional[str] = None, categories: Optional[Sequence[str]] = None) -> List[Task]:
    tasks: List[Task] = []
    for path in sorted(Path(directory).glob("*.jsonl")):
        if categories and path.stem not in categories:
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                task = Task.model_validate_json(line)
                if split is None or task.split.value == split:
                    tasks.append(task)
    return tasks


def main(argv: Optional[Sequence[str]] = None) -> None:
    ap = argparse.ArgumentParser(description="Generate CPQ-Bench tasks.")
    ap.add_argument("--per-category", type=int, default=DEFAULT_PER_CATEGORY)
    ap.add_argument("--dev-fraction", type=float, default=DEFAULT_DEV_FRACTION)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--products", type=int, default=300)
    ap.add_argument("--catalog-seed", type=int, default=1234)
    ap.add_argument("--categories", nargs="*", default=None)
    ap.add_argument("--out", type=Path, default=Path("bench/tasks"))
    args = ap.parse_args(argv)
    tasks = asyncio.run(generate_tasks(
        args.per_category, args.dev_fraction, args.seed, args.products, args.catalog_seed, args.categories,
    ))
    meta = {"seed": args.seed, "catalog_seed": args.catalog_seed, "products": args.products,
            "per_category": args.per_category, "dev_fraction": args.dev_fraction}
    write_tasks(tasks, args.out, meta)
    print(json.dumps(json.loads((args.out / "MANIFEST.json").read_text())["counts"], indent=2))


if __name__ == "__main__":
    main()
