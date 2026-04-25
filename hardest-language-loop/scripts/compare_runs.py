#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RUN_ROOT = ROOT / "data" / "runs"


def resolve_run(value: str) -> Path:
    path = Path(value)
    if path.exists():
        return path
    candidate = DEFAULT_RUN_ROOT / value
    if candidate.exists():
        return candidate
    raise FileNotFoundError(f"run not found: {value}")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_run(path: Path) -> dict[str, Any]:
    summary = load_json(path / "artifacts" / "summary.json")
    repro_path = path / "artifacts" / "reproducibility.json"
    reproducibility = load_json(repro_path) if repro_path.exists() else {}
    return {"path": str(path), "summary": summary, "reproducibility": reproducibility}


def candidate_rows(run: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = dict((run["summary"].get("by_candidate") or {}).items())
    if rows:
        return rows
    hashes = run.get("reproducibility", {}).get("candidate_hashes") or {}
    return {name: {"candidate_hash": digest, "solver_failure_rate": None} for name, digest in hashes.items()}


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare two language-search runs for reproducibility.")
    parser.add_argument("baseline")
    parser.add_argument("replay")
    args = parser.parse_args()

    left = load_run(resolve_run(args.baseline))
    right = load_run(resolve_run(args.replay))
    left_candidates = candidate_rows(left)
    right_candidates = candidate_rows(right)
    names = sorted(set(left_candidates) | set(right_candidates))

    rows = []
    for name in names:
        a = left_candidates.get(name)
        b = right_candidates.get(name)
        a_rate = None if not a else a.get("solver_failure_rate")
        b_rate = None if not b else b.get("solver_failure_rate")
        rows.append(
            {
                "candidate": name,
                "baseline_failure_rate": a_rate,
                "replay_failure_rate": b_rate,
                "delta": None if a_rate is None or b_rate is None else round(b_rate - a_rate, 6),
                "baseline_hash": None if not a else a.get("candidate_hash"),
                "replay_hash": None if not b else b.get("candidate_hash"),
                "hash_match": bool(a and b and a.get("candidate_hash") == b.get("candidate_hash")),
            }
        )

    result = {
        "baseline": left["path"],
        "replay": right["path"],
        "candidate_set_hash_match": left["summary"].get("candidate_set_hash") == right["summary"].get("candidate_set_hash"),
        "problem_set_hash_match": left["summary"].get("problem_set_hash") == right["summary"].get("problem_set_hash"),
        "completed_model_requests": {
            "baseline": left["summary"].get("completed_model_requests"),
            "replay": right["summary"].get("completed_model_requests"),
        },
        "rows": rows,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
