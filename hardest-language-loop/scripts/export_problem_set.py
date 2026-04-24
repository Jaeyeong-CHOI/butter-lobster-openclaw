#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from llm_failure_pl.problems import default_problem_set, validate_problem_set


def main() -> int:
    problems = default_problem_set()
    payload = {
        "problem_count": len(problems),
        "problems": [problem.to_dict(include_reference=True, include_hidden=True) for problem in problems],
        "reference_validation": validate_problem_set(problems),
    }
    out_path = ROOT / "data" / "problem_set_preview.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(out_path), "problem_count": len(problems)}, ensure_ascii=False, indent=2))
    return 0 if all(item["success"] for item in payload["reference_validation"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
