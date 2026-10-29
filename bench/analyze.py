"""
Paper outputs from run logs. No LLM calls.

    python -m bench.analyze results/*.jsonl --out results/analysis

Writes, under --out:
  success.csv          task success by arm x model, with a 95% bootstrap CI over tasks
  error_classes.csv    rate of each error class by arm x model (over completed runs)
  pass_k.csv           pass^k for k = 1..K by arm x model, plus pass_k.png and pass_k.pdf
  leakage.csv          red-team leakage rate per arm (runs whose task id starts with rt-)
  latency_tokens.csv   per-task latency and token use by arm x model
  main_table.tex       LaTeX table of the main results

Conventions
- Red-team runs (task id rt-*) are kept out of the main tables and go only to leakage.csv.
- Runs that ended in an exception are counted in `errored` and excluded from every rate.
- A task's success is the fraction of its completed trials that passed. Bootstrap resamples tasks, not runs.
- pass^k for a task with n trials and c passes is C(c,k)/C(n,k), averaged over tasks with n >= k.
"""
import argparse
import csv
import json
import math
from collections import defaultdict
from pathlib import Path
from statistics import fmean, median
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from bench.redteam.report import leakage_report

BOOTSTRAP_RESAMPLES = 10_000
BOOTSTRAP_SEED = 20261029
ERROR_CLASSES = ("syntactic", "semantic", "producibility", "intent", "pricing", "disclosure")
RED_TEAM_PREFIX = "rt-"

Key = Tuple[str, str]  # (arm, model)


def load(paths: Iterable[Path]) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    for path in paths:
        for line in Path(path).read_text(encoding="utf-8").splitlines():
            if line.strip():
                records.append(json.loads(line))
    return records


def split_records(records: Sequence[Dict[str, Any]]):
    """Main-table runs, red-team runs and the count of errored runs (excluded from all rates)."""
    errored = sum(1 for r in records if r.get("error") is not None)
    ok = [r for r in records if r.get("error") is None]
    main = [r for r in ok if not r["task_id"].startswith(RED_TEAM_PREFIX)]
    red = [r for r in ok if r["task_id"].startswith(RED_TEAM_PREFIX)]
    return main, red, errored


def bootstrap_ci(values: Sequence[float], seed: int = BOOTSTRAP_SEED, resamples: int = BOOTSTRAP_RESAMPLES) -> Tuple[float, float]:
    """Percentile 95% CI of the mean, resampling the per-task values with replacement."""
    import numpy as np

    data = np.asarray(values, dtype=float)
    if data.size == 0:
        return (math.nan, math.nan)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, data.size, size=(resamples, data.size))
    means = data[idx].mean(axis=1)
    low, high = np.percentile(means, [2.5, 97.5])
    return (float(low), float(high))


def per_task(records: Sequence[Dict[str, Any]]) -> Dict[Key, Dict[str, List[Dict[str, Any]]]]:
    grouped: Dict[Key, Dict[str, List[Dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    for r in records:
        grouped[(r["arm"], r["model"])][r["task_id"]].append(r)
    return grouped


def success_table(records: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows = []
    for key, tasks in sorted(per_task(records).items()):
        rates = [sum(1 for r in runs if r["score"]["passed"]) / len(runs) for runs in tasks.values()]
        low, high = bootstrap_ci(rates)
        point = fmean(rates)
        rows.append({
            "arm": key[0], "model": key[1], "tasks": len(rates), "runs": sum(len(v) for v in tasks.values()),
            "success": round(point, 4), "ci95_low": round(low, 4), "ci95_high": round(high, 4),
        })
    return rows


def error_class_table(records: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows = []
    grouped: Dict[Key, List[Dict[str, Any]]] = defaultdict(list)
    for r in records:
        grouped[(r["arm"], r["model"])].append(r)
    for key, runs in sorted(grouped.items()):
        row: Dict[str, Any] = {"arm": key[0], "model": key[1], "runs": len(runs)}
        for cls in ERROR_CLASSES:
            row[cls] = round(sum(1 for r in runs if cls in r.get("error_classes", [])) / len(runs), 4)
        rows.append(row)
    return rows


def pass_k_curve(tasks: Dict[str, List[Dict[str, Any]]], max_k: int) -> Dict[int, float]:
    """pass^k for each k with at least one task holding k trials. Averages C(c,k)/C(n,k) over those tasks."""
    curve: Dict[int, float] = {}
    for k in range(1, max_k + 1):
        values = []
        for runs in tasks.values():
            n = len(runs)
            if n < k:
                continue
            c = sum(1 for r in runs if r["score"]["passed"])
            values.append(math.comb(c, k) / math.comb(n, k))
        if values:
            curve[k] = fmean(values)
    return curve


def pass_k_table(records: Sequence[Dict[str, Any]], max_k: int) -> Tuple[List[Dict[str, Any]], Dict[Key, Dict[int, float]]]:
    rows, curves = [], {}
    for key, tasks in sorted(per_task(records).items()):
        curve = pass_k_curve(tasks, max_k)
        curves[key] = curve
        for k, value in curve.items():
            rows.append({"arm": key[0], "model": key[1], "k": k, "pass_k": round(value, 4)})
    return rows, curves


def latency_tokens_table(records: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows = []
    grouped: Dict[Key, List[Dict[str, Any]]] = defaultdict(list)
    for r in records:
        grouped[(r["arm"], r["model"])].append(r)
    for key, runs in sorted(grouped.items()):
        latency = [r["latency_ms"] for r in runs]
        tokens = [r["tokens"]["input_tokens"] + r["tokens"]["output_tokens"] for r in runs]
        calls = [r["tokens"]["model_calls"] for r in runs]
        rows.append({
            "arm": key[0], "model": key[1], "runs": len(runs),
            "latency_ms_mean": round(fmean(latency), 2), "latency_ms_median": round(median(latency), 2),
            "tokens_per_task_mean": round(fmean(tokens), 1), "model_calls_per_task_mean": round(fmean(calls), 2),
        })
    return rows


def leakage_table(red: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    report = leakage_report(red)
    return [
        {"arm": arm, "runs": r["runs"], "leaks": r["leaks"], "rate": r["rate"],
         "ci95_low": r["ci95"][0], "ci95_high": r["ci95"][1], "exposed_runs": r["exposed_runs"]}
        for arm, r in report.items()
    ]


def write_csv(path: Path, rows: Sequence[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def latex_table(success: Sequence[Dict[str, Any]], pass_rows: Sequence[Dict[str, Any]]) -> str:
    k_max = {}
    for row in pass_rows:
        key = (row["arm"], row["model"])
        k_max[key] = max(k_max.get(key, 0), row["k"])
    pk = {(r["arm"], r["model"], r["k"]): r["pass_k"] for r in pass_rows}
    lines = [
        r"\begin{tabular}{llrrrr}",
        r"\toprule",
        r"Arm & Model & Success (95\% CI) & pass$^1$ & pass$^{K}$ & Tasks \\",
        r"\midrule",
    ]
    for row in success:
        key = (row["arm"], row["model"])
        kmax = k_max.get(key, 1)
        lines.append(
            f"{_tex(row['arm'])} & {_tex(row['model'])} & "
            f"{row['success']:.3f} [{row['ci95_low']:.3f}, {row['ci95_high']:.3f}] & "
            f"{pk.get((row['arm'], row['model'], 1), float('nan')):.3f} & "
            f"{pk.get((row['arm'], row['model'], kmax), float('nan')):.3f} (K={kmax}) & {row['tasks']} \\\\"
        )
    lines += [r"\bottomrule", r"\end{tabular}", ""]
    return "\n".join(lines)


def _tex(text: str) -> str:
    return str(text).replace("_", r"\_").replace("%", r"\%").replace("&", r"\&")


def plot_pass_k(curves: Dict[Key, Dict[int, float]], out: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    models = sorted({m for _, m in curves})
    arms = sorted({a for a, _ in curves})
    fig, axes = plt.subplots(1, max(1, len(models)), figsize=(4 * max(1, len(models)), 3.4), sharey=True, squeeze=False)
    for ax, model in zip(axes[0], models):
        for arm in arms:
            curve = curves.get((arm, model))
            if not curve:
                continue
            ks = sorted(curve)
            ax.plot(ks, [curve[k] for k in ks], marker="o", label=f"Arm {arm}")
        ax.set_title(model)
        ax.set_xlabel("k")
        ax.set_ylim(0, 1.02)
        ax.grid(alpha=0.3)
    axes[0][0].set_ylabel(r"pass$^k$")
    axes[0][-1].legend(frameon=False)
    fig.tight_layout()
    fig.savefig(out.with_suffix(".png"), dpi=200)
    fig.savefig(out.with_suffix(".pdf"))
    plt.close(fig)


def analyze(paths: Sequence[Path], out: Path, max_k: Optional[int] = None) -> Dict[str, Any]:
    records = load(paths)
    main, red, errored = split_records(records)
    k_limit = max_k or max((len(v) for tasks in per_task(main).values() for v in tasks.values()), default=1)

    success = success_table(main)
    errors = error_class_table(main)
    pass_rows, curves = pass_k_table(main, k_limit)
    leak = leakage_table(red)
    latency = latency_tokens_table(main)

    out.mkdir(parents=True, exist_ok=True)
    write_csv(out / "success.csv", success)
    write_csv(out / "error_classes.csv", errors)
    write_csv(out / "pass_k.csv", pass_rows)
    write_csv(out / "leakage.csv", leak)
    write_csv(out / "latency_tokens.csv", latency)
    (out / "main_table.tex").write_text(latex_table(success, pass_rows), encoding="utf-8", newline="\n")
    if curves:
        plot_pass_k(curves, out / "pass_k")
    summary = {"records": len(records), "main_runs": len(main), "red_team_runs": len(red), "errored": errored, "k": k_limit}
    (out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8", newline="\n")
    return summary


def main(argv: Optional[Sequence[str]] = None) -> None:
    ap = argparse.ArgumentParser(description="Paper-ready analysis of CPQ-Bench runs.")
    ap.add_argument("files", nargs="+", type=Path)
    ap.add_argument("--out", type=Path, default=Path("results/analysis"))
    ap.add_argument("--max-k", type=int, default=None, help="largest k for pass^k (default: largest trial count)")
    args = ap.parse_args(argv)
    print(json.dumps(analyze(args.files, args.out, args.max_k), indent=2))


if __name__ == "__main__":
    main()
