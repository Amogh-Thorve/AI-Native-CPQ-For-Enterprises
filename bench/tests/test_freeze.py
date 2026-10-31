"""
Freeze tests run on temporary copies of the task files. They never write bench/FREEZE.json.
"""
import json
import shutil
from pathlib import Path

import pytest

from bench.freeze import BENCH_DIR, FREEZE_NAME, check, main, write


@pytest.fixture
def copy_dir(tmp_path: Path) -> Path:
    bench = tmp_path / "bench"
    (bench / "redteam").mkdir(parents=True)
    shutil.copytree(BENCH_DIR / "tasks", bench / "tasks")
    shutil.copytree(BENCH_DIR / "redteam" / "tasks", bench / "redteam" / "tasks")
    return bench


def test_check_passes_when_nothing_has_changed(copy_dir):
    write(copy_dir)
    assert check(copy_dir) == []
    assert main(["check", "--dir", str(copy_dir)]) == 0


def test_check_fails_after_a_task_file_is_altered(copy_dir):
    write(copy_dir)
    target = copy_dir / "tasks" / "simple_quote.jsonl"
    target.write_bytes(target.read_bytes() + b" ")
    assert check(copy_dir) == ["modified: tasks/simple_quote.jsonl"]
    assert main(["check", "--dir", str(copy_dir)]) == 1


def test_check_fails_when_a_redteam_file_is_altered(copy_dir):
    write(copy_dir)
    target = copy_dir / "redteam" / "tasks" / "direct.jsonl"
    target.write_bytes(target.read_bytes().replace(b"\n", b"\n ", 1))
    assert check(copy_dir) == ["modified: redteam/tasks/direct.jsonl"]


def test_check_reports_added_and_removed_files(copy_dir):
    write(copy_dir)
    (copy_dir / "tasks" / "extra.jsonl").write_bytes(b"")
    (copy_dir / "redteam" / "tasks" / "roleplay.jsonl").unlink()
    problems = check(copy_dir)
    assert "added: tasks/extra.jsonl" in problems
    assert "removed: redteam/tasks/roleplay.jsonl" in problems
    assert main(["check", "--dir", str(copy_dir)]) == 1


def test_check_fails_without_a_freeze_file(copy_dir):
    problems = check(copy_dir)
    assert len(problems) == 1 and FREEZE_NAME in problems[0]
    assert main(["check", "--dir", str(copy_dir)]) == 1


def test_frozen_facts_match_the_manifests(copy_dir):
    write(copy_dir)
    frozen = json.loads((copy_dir / FREEZE_NAME).read_text(encoding="utf-8"))
    manifest = json.loads((BENCH_DIR / "tasks" / "MANIFEST.json").read_text(encoding="utf-8"))
    redteam = json.loads((BENCH_DIR / "redteam" / "tasks" / "MANIFEST.json").read_text(encoding="utf-8"))
    assert frozen["catalog_seed"] == manifest["catalog_seed"]
    assert frozen["products"] == manifest["products"]
    assert frozen["task_counts"]["dev"] == sum(c["dev"] for c in manifest["counts"].values())
    assert frozen["task_counts"]["test"] == sum(c["test"] for c in manifest["counts"].values())
    assert frozen["redteam_count"] == sum(redteam["counts"].values())
    assert all(path.startswith(("tasks/", "redteam/tasks/")) for path in frozen["files"])


def test_a_different_commit_alone_does_not_fail_the_check(copy_dir):
    write(copy_dir)
    freeze = json.loads((copy_dir / FREEZE_NAME).read_text(encoding="utf-8"))
    freeze["git_commit"] = "0" * 40
    (copy_dir / FREEZE_NAME).write_text(json.dumps(freeze), encoding="utf-8")
    assert check(copy_dir) == []
