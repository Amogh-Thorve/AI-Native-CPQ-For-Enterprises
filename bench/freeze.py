"""
Freeze and check the benchmark task files. No LLM calls.

    python -m bench.freeze write    # write bench/FREEZE.json (run once, after tuning)
    python -m bench.freeze check    # recompute everything and compare; exit 1 on any difference

Frozen: the SHA-256 of every file under bench/tasks and bench/redteam/tasks, the task counts per split (read from the
task files), the redteam count, and the catalog seed and product count from bench/tasks/MANIFEST.json.
The git commit at write time is recorded for reference only. check does not fail when the commit changes, because the
task files are what must stay the same.
"""
import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Sequence

BENCH_DIR = Path(__file__).resolve().parent
TASK_DIRS = ("tasks", "redteam/tasks")
FREEZE_NAME = "FREEZE.json"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def hash_task_files(bench_dir: Path) -> Dict[str, str]:
    hashes: Dict[str, str] = {}
    for rel in TASK_DIRS:
        for path in sorted((bench_dir / rel).rglob("*")):
            if path.is_file():
                hashes[path.relative_to(bench_dir).as_posix()] = _sha256(path)
    return hashes


def count_tasks(bench_dir: Path) -> Dict[str, int]:
    """Counts from the task files themselves, so the freeze does not depend on MANIFEST.json being up to date."""
    counts = {"dev": 0, "test": 0}
    for path in sorted((bench_dir / "tasks").glob("*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                counts[json.loads(line)["split"]] += 1
    counts["total"] = counts["dev"] + counts["test"]
    return counts


def count_redteam(bench_dir: Path) -> int:
    return sum(
        1 for path in sorted((bench_dir / "redteam" / "tasks").glob("*.jsonl"))
        for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    )


def manifest_facts(bench_dir: Path) -> Dict[str, int]:
    manifest = json.loads((bench_dir / "tasks" / "MANIFEST.json").read_text(encoding="utf-8"))
    return {"catalog_seed": manifest["catalog_seed"], "products": manifest["products"]}


def git_commit(bench_dir: Path) -> Optional[str]:
    try:
        out = subprocess.run(["git", "rev-parse", "HEAD"], cwd=bench_dir, capture_output=True, text=True, check=True)
    except (OSError, subprocess.CalledProcessError):
        return None
    return out.stdout.strip()


def snapshot(bench_dir: Path) -> Dict:
    return {
        "files": hash_task_files(bench_dir),
        "task_counts": count_tasks(bench_dir),
        "redteam_count": count_redteam(bench_dir),
        **manifest_facts(bench_dir),
        "git_commit": git_commit(bench_dir),
    }


def write(bench_dir: Path) -> Path:
    out = bench_dir / FREEZE_NAME
    out.write_text(json.dumps(snapshot(bench_dir), indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return out


def differences(frozen: Dict, current: Dict) -> List[str]:
    problems: List[str] = []
    for path in sorted(set(frozen["files"]) | set(current["files"])):
        before, after = frozen["files"].get(path), current["files"].get(path)
        if before is None:
            problems.append(f"added: {path}")
        elif after is None:
            problems.append(f"removed: {path}")
        elif before != after:
            problems.append(f"modified: {path}")
    for key in ("task_counts", "redteam_count", "catalog_seed", "products"):
        if frozen.get(key) != current.get(key):
            problems.append(f"{key} changed: {frozen.get(key)} -> {current.get(key)}")
    return problems


def check(bench_dir: Path) -> List[str]:
    frozen_path = bench_dir / FREEZE_NAME
    if not frozen_path.exists():
        return [f"{FREEZE_NAME} is missing; run `python -m bench.freeze write` first"]
    frozen = json.loads(frozen_path.read_text(encoding="utf-8"))
    return differences(frozen, snapshot(bench_dir))


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Freeze and check the CPQ-Bench task files.")
    ap.add_argument("command", choices=["write", "check"])
    ap.add_argument("--dir", type=Path, default=BENCH_DIR, help="bench directory (default: this package)")
    args = ap.parse_args(argv)
    if args.command == "write":
        print(f"wrote {write(args.dir)}")
        return 0
    problems = check(args.dir)
    if problems:
        print("FREEZE CHECK FAILED:")
        for problem in problems:
            print(f"  {problem}")
        return 1
    print("freeze check passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
