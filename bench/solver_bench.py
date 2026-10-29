"""
Latency of the configuration solvers against the number of constraints. In-memory models only (no database), so the
numbers are solver cost: building the model and solving, per validate call.

    python -m bench.solver_bench --sizes 100 1000 5000 --selections 200

Prints CSV: implementation,constraints,selections,p50_ms,p95_ms,mean_ms
"""
import argparse
import csv
import random
import statistics
import sys
import time
from typing import List, Sequence, Tuple

from backend.app.domains.configuration.solver import ProductModel, Selection
from backend.app.domains.configuration.solver.cpsat_solver import CpSatSolver
from backend.app.domains.configuration.solver.rules_validator import RulesValidator
from bench.catalog_gen import plan
from bench.solver_models import constraint_count, plan_models, random_selection

RULES_PER_CONFIGURABLE_PRODUCT = 18
CONFIGURABLE_FRACTION = 0.4


def products_for(target_constraints: int) -> int:
    per_product = RULES_PER_CONFIGURABLE_PRODUCT * CONFIGURABLE_FRACTION
    return max(1, round(target_constraints / per_product))


def workload(n_products: int, selections: int, seed: int) -> Tuple[int, List[Tuple[ProductModel, List[Selection]]]]:
    models = list(plan_models(plan(n_products, 1234)).values())
    rng = random.Random(seed)
    cases = [(m, random_selection(m, rng)) for m in (models[i % len(models)] for i in range(selections))]
    constraints = sum(constraint_count(m) for m in models)
    return constraints, cases


def time_solver(solver, cases) -> List[float]:
    samples = []
    for model, selections in cases:
        started = time.perf_counter()
        solver.validate(model, selections)
        samples.append((time.perf_counter() - started) * 1000)
    return samples


def percentile(values: Sequence[float], q: float) -> float:
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round(q * (len(ordered) - 1))))
    return ordered[index]


def run(sizes: Sequence[int], selections: int, seed: int, out) -> None:
    writer = csv.writer(out)
    writer.writerow(["implementation", "constraints", "selections", "p50_ms", "p95_ms", "mean_ms"])
    for target in sizes:
        constraints, cases = workload(products_for(target), selections, seed)
        for solver in (RulesValidator(), CpSatSolver()):
            time_solver(solver, cases[:5])  # warm up imports and caches
            samples = time_solver(solver, cases)
            writer.writerow([
                solver.name, constraints, len(cases),
                round(percentile(samples, 0.50), 3), round(percentile(samples, 0.95), 3), round(statistics.fmean(samples), 3),
            ])


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description="Configuration solver latency vs constraint count.")
    ap.add_argument("--sizes", type=int, nargs="+", default=[100, 1000, 5000])
    ap.add_argument("--selections", type=int, default=200)
    ap.add_argument("--seed", type=int, default=1)
    args = ap.parse_args(argv)
    run(args.sizes, args.selections, args.seed, sys.stdout)


if __name__ == "__main__":
    main()
