"""
Task draws must not depend on the per-process hash seed. Each check runs the draw loop in two subprocesses with
different PYTHONHASHSEED values and compares the turns. No database, no LLM.
"""
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]

DRAW_SCRIPT = """
import hashlib, random
from bench.catalog_gen import plan
from bench.templates import TEMPLATES, Ctx
pl = plan(300, 1234)
turns = []
for cat in TEMPLATES:
    ctx = Ctx(pl, random.Random(f"7:{cat}"))
    turns += [TEMPLATES[cat](ctx).turns for _ in range(40)]
print(hashlib.sha256(repr(turns).encode()).hexdigest())
"""


def _digest(hash_seed: int) -> str:
    env = {**os.environ, "PYTHONHASHSEED": str(hash_seed)}
    out = subprocess.run([sys.executable, "-c", DRAW_SCRIPT], cwd=REPO, env=env, capture_output=True, text=True, check=True)
    return out.stdout.strip().splitlines()[-1]


def test_task_draws_are_identical_across_hash_seeds():
    assert _digest(0) == _digest(1)


def test_ctx_product_order_does_not_follow_the_input_container():
    from bench.catalog_gen import plan
    from bench.templates import Ctx
    import random

    pl = plan(300, 1234)
    as_set = Ctx(pl, random.Random("x"))
    as_list = Ctx(pl, random.Random("x"))
    methods = {"STANDARD", "LINE_DISCOUNT", "COST_PLUS_MARKUP"}
    assert as_set.product(methods).sku == as_list.product(sorted(methods)).sku
