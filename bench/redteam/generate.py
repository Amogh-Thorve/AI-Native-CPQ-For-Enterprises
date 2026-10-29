"""
    python -m bench.redteam.generate --per-family 20 --seed 21 --out bench/redteam/tasks

Seeded attack tasks. The forbidden figures are computed from the real cost data behind each quote, so they follow the catalog.
"""
import argparse
import asyncio
import json
import random
from decimal import Decimal
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from backend.app.core.database import SessionLocal
from bench.catalog_gen import generate, plan
from bench.harness import isolated_session, run_reference
from bench.redteam.groundtruth import derived_secrets
from bench.redteam.templates import FAMILIES, ROLE
from bench.harness import expected_from
from bench.schema import Category, Expected, Split, Task
from bench.templates import Ctx

DEFAULT_PER_FAMILY = 20


def family_of(task_id: str) -> str:
    """Task ids are rt-<family>-<n>."""
    return task_id.split("-")[1]


async def _one(ctx: Ctx, report, family: str, index: int) -> Task:
    attack = FAMILIES[family](ctx)
    async with isolated_session() as db:
        result = await run_reference(db, report, ROLE, attack.ops)
        forbidden: List[Decimal] = await derived_secrets(db, result["quote_ids"])
    if attack.no_quote:
        expected = Expected(clarification_expected=True, forbidden_values=forbidden)
    else:
        expected = expected_from(result)
        expected.forbidden_values = forbidden
    return Task(
        id=f"rt-{family}-{index:03d}", category=Category.PERMISSION_TRAP, split=Split.TEST, user_role=ROLE,
        turns=attack.turns, expected=expected, setup=attack.setup,
    )


async def generate_attacks(
    per_family: int = DEFAULT_PER_FAMILY, seed: int = 21, n_products: int = 300, catalog_seed: int = 1234,
    families: Optional[Sequence[str]] = None,
) -> List[Task]:
    async with SessionLocal() as db:
        report = await generate(db, n_products, catalog_seed)
    catalog = plan(n_products, catalog_seed)
    tasks: List[Task] = []
    for family in families or list(FAMILIES):
        ctx = Ctx(catalog, random.Random(f"rt:{seed}:{family}"))
        for i in range(per_family):
            tasks.append(await _one(ctx, report, family, i + 1))
    return tasks


def write_attacks(tasks: Sequence[Task], out: Path, meta: Dict) -> None:
    out.mkdir(parents=True, exist_ok=True)
    by_family: Dict[str, List[Task]] = {}
    for t in tasks:
        by_family.setdefault(family_of(t.id), []).append(t)
    counts = {}
    for family, items in by_family.items():
        (out / f"{family}.jsonl").write_text("".join(t.model_dump_json() + "\n" for t in sorted(items, key=lambda t: t.id)),
                                              encoding="utf-8", newline="\n")
        counts[family] = len(items)
    (out / "MANIFEST.json").write_text(json.dumps({**meta, "counts": counts}, indent=2, sort_keys=True) + "\n",
                                       encoding="utf-8", newline="\n")


def main(argv: Optional[Sequence[str]] = None) -> None:
    ap = argparse.ArgumentParser(description="Generate CPQ-Bench red-team tasks.")
    ap.add_argument("--per-family", type=int, default=DEFAULT_PER_FAMILY)
    ap.add_argument("--seed", type=int, default=21)
    ap.add_argument("--products", type=int, default=300)
    ap.add_argument("--out", type=Path, default=Path("bench/redteam/tasks"))
    args = ap.parse_args(argv)
    tasks = asyncio.run(generate_attacks(args.per_family, args.seed, args.products))
    write_attacks(tasks, args.out, {"seed": args.seed, "products": args.products, "per_family": args.per_family})
    print((args.out / "MANIFEST.json").read_text())


if __name__ == "__main__":
    main()
