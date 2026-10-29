"""
Analysis tests on a small synthetic results fixture with answers worked out by hand. No database, no network.

Fixture, arm B, model m1, three tasks with three trials each (P = pass, F = fail):
    t1: P P F  -> 2/3
    t2: P P P  -> 1
    t3: F F F  -> 0
So success is (2/3 + 1 + 0) / 3 = 5/9, pass^1 is also 5/9, pass^2 is (1/3 + 1 + 0) / 3 = 4/9 and pass^3 is 1/3.
Arm C, model m1: three tasks, all passing: success 1.0 and pass^k = 1 for every k.
Red-team runs (rt-*) give B a leakage of 1/2 and C a leakage of 0. One errored record is excluded everywhere.
"""
import json
from pathlib import Path

import pytest

from bench.analyze import analyze, bootstrap_ci, pass_k_curve


def run(task, arm, model, trial, passed, error_classes=(), disclosure=False, latency=10.0, tokens=(100, 20), error=None):
    return {
        "task_id": task, "category": "simple_quote", "split": "test", "arm": arm, "model": model,
        "trial": trial, "score": {"passed": passed, "failures": []}, "error_classes": list(error_classes),
        "disclosure": disclosure, "latency_ms": latency,
        "tokens": {"input_tokens": tokens[0], "output_tokens": tokens[1], "model_calls": 1},
        "error": error,
    }


def fixture_records():
    rows = []
    for trial, passed in enumerate([True, True, False]):
        rows.append(run("t1", "B", "m1", trial, passed, [] if passed else ["pricing"]))
    for trial in range(3):
        rows.append(run("t2", "B", "m1", trial, True))
        rows.append(run("t3", "B", "m1", trial, False, ["semantic"]))
    for task in ("t1", "t2", "t3"):
        for trial in range(3):
            rows.append(run(task, "C", "m1", trial, True))
    rows.append(run("t1", "B", "m1", 9, False, error="boom"))  # errored: must not count anywhere
    for trial in range(2):
        rows.append(run("t1", "B", "m2", trial, trial == 0))
    rows.append(run("rt-direct-001", "B", "m1", 0, False, ["disclosure"], disclosure=True))
    rows.append(run("rt-direct-002", "B", "m1", 0, False))
    rows.append(run("rt-direct-001", "C", "m1", 0, False))
    rows.append(run("rt-direct-002", "C", "m1", 0, False))
    return rows


@pytest.fixture
def results(tmp_path: Path):
    path = tmp_path / "results" / "fixture.jsonl"
    path.parent.mkdir()
    path.write_text("\n".join(json.dumps(r) for r in fixture_records()) + "\n", encoding="utf-8")
    return path


def rows(out: Path, name: str):
    import csv
    with (out / name).open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def group(table, arm, model):
    return next(r for r in table if r["arm"] == arm and r["model"] == model)


def test_known_success_rate_and_ci_ordering(results, tmp_path):
    out = tmp_path / "analysis"
    analyze([results], out)
    table = rows(out, "success.csv")
    b = group(table, "B", "m1")
    assert float(b["success"]) == pytest.approx(5 / 9, abs=1e-4)
    assert int(b["tasks"]) == 3 and int(b["runs"]) == 9  # the errored run is excluded
    assert float(b["ci95_low"]) <= float(b["success"]) <= float(b["ci95_high"])
    c = group(table, "C", "m1")
    assert float(c["success"]) == 1.0
    assert float(c["ci95_low"]) == 1.0 and float(c["ci95_high"]) == 1.0


def test_bootstrap_interval_is_fixed_by_seed_and_brackets_the_mean():
    values = [2 / 3, 1.0, 0.0]
    low, high = bootstrap_ci(values, resamples=2000)
    assert low <= sum(values) / 3 <= high
    assert bootstrap_ci(values, resamples=2000) == (low, high)
    assert bootstrap_ci([1.0, 1.0, 1.0], resamples=500) == (1.0, 1.0)
    empty_low, empty_high = bootstrap_ci([], resamples=10)
    assert empty_low != empty_low and empty_high != empty_high  # NaN for no tasks


def test_pass_k_matches_hand_values(results, tmp_path):
    out = tmp_path / "analysis"
    analyze([results], out, max_k=3)
    table = rows(out, "pass_k.csv")
    values = {int(r["k"]): float(r["pass_k"]) for r in table if r["arm"] == "B" and r["model"] == "m1"}
    assert values[1] == pytest.approx(5 / 9, abs=1e-4)
    assert values[2] == pytest.approx(4 / 9, abs=1e-4)
    assert values[3] == pytest.approx(1 / 3, abs=1e-4)


@pytest.mark.parametrize("arm,model", [("B", "m1"), ("C", "m1")])
def test_pass_k_is_monotone_non_increasing_and_starts_at_success(results, tmp_path, arm, model):
    out = tmp_path / "analysis"
    analyze([results], out, max_k=3)
    table = rows(out, "pass_k.csv")
    curve = {int(r["k"]): float(r["pass_k"]) for r in table if r["arm"] == arm and r["model"] == model}
    assert list(curve) == [1, 2, 3]
    values = [curve[k] for k in (1, 2, 3)]
    assert all(a >= b for a, b in zip(values, values[1:]))
    success = float(group(rows(out, "success.csv"), arm, model)["success"])
    assert values[0] == pytest.approx(success)


def test_pass_k_skips_k_larger_than_trials():
    tasks = {"t": [{"score": {"passed": True}}, {"score": {"passed": False}}]}
    assert set(pass_k_curve(tasks, 5)) == {1, 2}


def test_error_classes_are_rates_over_completed_runs(results, tmp_path):
    out = tmp_path / "analysis"
    analyze([results], out)
    b = group(rows(out, "error_classes.csv"), "B", "m1")
    assert int(b["runs"]) == 9
    assert float(b["pricing"]) == pytest.approx(1 / 9, abs=1e-4)
    assert float(b["semantic"]) == pytest.approx(3 / 9, abs=1e-4)


def test_leakage_is_taken_from_red_team_runs_only(results, tmp_path):
    out = tmp_path / "analysis"
    summary = analyze([results], out)
    leak = {r["arm"]: r for r in rows(out, "leakage.csv")}
    assert float(leak["B"]["rate"]) == pytest.approx(0.5)
    assert float(leak["C"]["rate"]) == 0.0
    assert summary["red_team_runs"] == 4 and summary["errored"] == 1
    assert int(group(rows(out, "success.csv"), "B", "m1")["tasks"]) == 3  # red-team tasks not in main table


def test_latency_and_tokens_per_arm_model(results, tmp_path):
    out = tmp_path / "analysis"
    analyze([results], out)
    row = group(rows(out, "latency_tokens.csv"), "C", "m1")
    assert float(row["latency_ms_mean"]) == pytest.approx(10.0)
    assert float(row["tokens_per_task_mean"]) == pytest.approx(120.0)


def test_outputs_are_written_and_identical_on_rerun(results, tmp_path):
    first, second = tmp_path / "a", tmp_path / "b"
    analyze([results], first)
    analyze([results], second)
    for name in ("success.csv", "pass_k.csv", "error_classes.csv", "leakage.csv", "latency_tokens.csv", "main_table.tex"):
        assert (first / name).read_bytes() == (second / name).read_bytes(), name
    assert (first / "pass_k.png").stat().st_size > 0
    assert (first / "pass_k.pdf").read_bytes()[:4] == b"%PDF"


def test_latex_table_has_the_main_row(results, tmp_path):
    out = tmp_path / "analysis"
    analyze([results], out)
    tex = (out / "main_table.tex").read_text(encoding="utf-8")
    assert r"\begin{tabular}" in tex and r"\bottomrule" in tex
    assert "B & m1 & 0.556" in tex
