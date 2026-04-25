#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RULES = {
    "truthiness": "python",
    "if_semantics": "normal",
    "comparison_semantics": "normal",
    "arithmetic_semantics": "normal",
    "literal_semantics": "normal",
}


def load_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def pct(value: float | None) -> str:
    if value is None or math.isnan(value):
        return "n/a"
    return f"{value * 100:.1f}%"


def changed_rules(rules: dict[str, str]) -> dict[str, str]:
    return {key: value for key, value in rules.items() if DEFAULT_RULES.get(key) != value}


def summarize_attempts(evaluations: list[dict[str, Any]]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    by_candidate: dict[str, dict[str, Any]] = {}
    by_model: dict[str, dict[str, Any]] = {}
    by_problem: dict[str, dict[str, Any]] = {}

    def bump(bucket: dict[str, dict[str, Any]], key: str | None, success: bool) -> None:
        if not key:
            return
        row = bucket.setdefault(key, {"trials": 0, "successes": 0, "failures": 0, "accuracy": None, "failure_rate": None})
        row["trials"] += 1
        row["successes"] += int(success)
        row["failures"] += int(not success)
        row["accuracy"] = row["successes"] / row["trials"] if row["trials"] else None
        row["failure_rate"] = row["failures"] / row["trials"] if row["trials"] else None

    for item in evaluations:
        if not item.get("request_ok"):
            continue
        success = bool(item.get("success"))
        candidate = item.get("candidate_name")
        model = item.get("model")
        problem = item.get("problem_id")
        if candidate:
            row = by_candidate.setdefault(
                candidate,
                {
                    "candidate_name": candidate,
                    "trials": 0,
                    "successes": 0,
                    "failures": 0,
                    "accuracy": None,
                    "failure_rate": None,
                    "model_stats": {},
                    "problem_stats": {},
                    "first_failure_case_ids": [],
                },
            )
            row["trials"] += 1
            row["successes"] += int(success)
            row["failures"] += int(not success)
            row["accuracy"] = row["successes"] / row["trials"] if row["trials"] else None
            row["failure_rate"] = row["failures"] / row["trials"] if row["trials"] else None
            if not success and item.get("first_failure_case_id"):
                case_id = item["first_failure_case_id"]
                if case_id not in row["first_failure_case_ids"]:
                    row["first_failure_case_ids"].append(case_id)

            for sub_bucket, sub_key in ((row["model_stats"], model), (row["problem_stats"], problem)):
                bump(sub_bucket, sub_key, success)

        bump(by_model, model, success)
        bump(by_problem, problem, success)

    return by_candidate, by_model, by_problem


def candidate_lookup(candidates: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        item.get("language_spec", {}).get("name"): item
        for item in candidates
        if isinstance(item, dict) and item.get("language_spec", {}).get("name")
    }


def family_distribution(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    family_counts: Counter[str] = Counter()
    combo_counts: Counter[str] = Counter()
    for candidate in candidates:
        rules = candidate.get("language_spec", {}).get("semantic_rules", {})
        changed = changed_rules(rules)
        families = tuple(sorted(changed)) or ("baseline",)
        combo_counts[" + ".join(families)] += 1
        for family in families:
            family_counts[family] += 1
    return {
        "family_counts": dict(family_counts.most_common()),
        "top_combinations": dict(combo_counts.most_common(20)),
    }


def render_model_table(by_model: dict[str, dict[str, Any]]) -> str:
    lines = ["| Model | Attempts | Correct | Failed | Accuracy |", "|---|---:|---:|---:|---:|"]
    for model, row in sorted(by_model.items(), key=lambda item: item[0]):
        lines.append(
            f"| `{model}` | {row['trials']} | {row['successes']} | {row['failures']} | {pct(row['accuracy'])} |"
        )
    return "\n".join(lines)


def render_problem_table(by_problem: dict[str, dict[str, Any]]) -> str:
    lines = ["| Problem | Attempts | Correct | Failed | Accuracy |", "|---|---:|---:|---:|---:|"]
    for problem, row in sorted(by_problem.items(), key=lambda item: (item[1].get("accuracy") or 0.0, item[0])):
        lines.append(
            f"| `{problem}` | {row['trials']} | {row['successes']} | {row['failures']} | {pct(row['accuracy'])} |"
        )
    return "\n".join(lines)


def render_candidate(candidate_name: str, row: dict[str, Any], candidate: dict[str, Any] | None, rank: int) -> str:
    spec = (candidate or {}).get("language_spec", {})
    rules = spec.get("semantic_rules", {})
    changed = changed_rules(rules)
    title = (candidate or {}).get("title") or candidate_name
    desc = spec.get("description") or ""
    model_stats = row.get("model_stats") or {}
    model_bits = []
    for model, stats in sorted(model_stats.items()):
        model_bits.append(f"`{model}` {stats['successes']}/{stats['trials']} ({pct(stats['accuracy'])})")
    problem_stats = row.get("problem_stats") or {}
    hardest_problem = None
    if problem_stats:
        hardest_problem = sorted(problem_stats.items(), key=lambda item: (item[1].get("accuracy") or 0.0, item[0]))[0]
    lines = [
        f"### {rank}. `{candidate_name}` — failure {pct(row.get('failure_rate'))}",
        f"- Title: {title}",
        f"- Attempts: {row['trials']} / Correct: {row['successes']} / Failed: {row['failures']} / Accuracy: {pct(row.get('accuracy'))}",
        f"- Changed semantics: `{json.dumps(changed or {'baseline': 'python'}, ensure_ascii=False)}`",
    ]
    if desc:
        lines.append(f"- Description: {desc}")
    if hardest_problem:
        problem, stats = hardest_problem
        lines.append(f"- Hardest problem for this language: `{problem}` ({stats['failures']}/{stats['trials']} failed)")
    if row.get("first_failure_case_ids"):
        lines.append(f"- Example failed cases: {', '.join(f'`{x}`' for x in row['first_failure_case_ids'][:5])}")
    if model_bits:
        lines.append("- Model accuracies: " + "; ".join(model_bits))
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a final/partial report for a loop_result run.")
    parser.add_argument("run", nargs="?", default="v1", help="Run id under loop_result or a direct run directory path.")
    parser.add_argument("--result-root", default="loop_result")
    parser.add_argument("--top", type=int, default=10)
    args = parser.parse_args()

    run_path = Path(args.run)
    if not run_path.exists():
        result_root = Path(args.result_root)
        if not result_root.is_absolute():
            result_root = ROOT / result_root
        run_path = result_root / args.run
    if not run_path.exists():
        raise SystemExit(f"run not found: {args.run}")

    artifacts = run_path / "artifacts"
    summary = load_json(artifacts / "summary.json", {}) or {}
    state = load_json(artifacts / "iterative_loop_state.json", {}) or {}
    manifest = load_json(run_path / "manifest.json", {}) or {}
    reproducibility = load_json(artifacts / "reproducibility.json", {}) or {}
    candidates = load_json(artifacts / "candidate_languages.json", []) or []
    evaluations = load_json(artifacts / "evaluations.json", []) or []
    expansion_plan = load_json(artifacts / "expansion_plan.json", {}) or {}

    by_candidate, by_model, by_problem = summarize_attempts(evaluations)
    lookup = candidate_lookup(candidates)
    ranked_candidates = sorted(
        by_candidate.items(),
        key=lambda item: (item[1].get("failure_rate") or 0.0, item[1].get("trials") or 0),
        reverse=True,
    )
    family = family_distribution(candidates)

    settings = manifest.get("latest_settings") or manifest.get("settings") or {}
    solver_models = settings.get("solver_models") or reproducibility.get("solver_models") or []
    solver_pool = [
        {
            "provider": model.get("provider"),
            "model": model.get("model"),
            "repeats": model.get("repeats"),
            "base_url": model.get("base_url"),
        }
        for model in solver_models
    ]

    total_trials = sum(row["trials"] for row in by_model.values())
    total_successes = sum(row["successes"] for row in by_model.values())
    total_failures = sum(row["failures"] for row in by_model.values())
    overall_accuracy = total_successes / total_trials if total_trials else None

    report_json = {
        "run_dir": str(run_path),
        "status": state.get("status") or ("completed" if summary else "unknown"),
        "candidate_count": len(candidates),
        "evaluated_candidate_count": len(by_candidate),
        "problem_count": summary.get("problem_count") or len(load_json(artifacts / "problem_set.json", []) or []),
        "total_trials": total_trials,
        "total_successes": total_successes,
        "total_failures": total_failures,
        "overall_accuracy": overall_accuracy,
        "candidate_set_hash": summary.get("candidate_set_hash") or reproducibility.get("candidate_set_hash"),
        "problem_set_hash": summary.get("problem_set_hash") or reproducibility.get("problem_set_hash"),
        "solver_pool": solver_pool,
        "iterative_strategy": {
            "target_candidates": state.get("target_candidates"),
            "batch_size": state.get("batch_size"),
            "problem_limit": state.get("problem_limit"),
            "parallel_workers": state.get("parallel_workers"),
            "iterations": len(state.get("iterations", [])),
            "expansion_policy": expansion_plan.get("selection_policy")
            or "exploit high-failure neighborhoods while adding diversity bonus for underrepresented semantic families",
        },
        "model_accuracy": by_model,
        "problem_accuracy": by_problem,
        "language_family_distribution": family,
        "hardest_candidates": [
            {
                **row,
                "title": (lookup.get(name) or {}).get("title"),
                "description": (lookup.get(name) or {}).get("language_spec", {}).get("description"),
                "semantic_rules": (lookup.get(name) or {}).get("language_spec", {}).get("semantic_rules"),
                "changed_rules": changed_rules((lookup.get(name) or {}).get("language_spec", {}).get("semantic_rules", {})),
            }
            for name, row in ranked_candidates[: args.top]
        ],
    }

    status_label = report_json["status"]
    md_lines = [
        f"# LLM Failure PL Loop Report — `{run_path.name}`",
        "",
        "## 1. Run status",
        "",
        f"- Status: **{status_label}**",
        f"- Run dir: `{run_path}`",
        f"- Candidate languages: **{len(candidates)}**",
        f"- Evaluated candidate languages: **{len(by_candidate)}**",
        f"- Total solver attempts completed: **{total_trials}**",
        f"- Overall accuracy: **{pct(overall_accuracy)}** ({total_successes}/{total_trials})",
        f"- Candidate set hash: `{report_json['candidate_set_hash']}`",
        f"- Problem set hash: `{report_json['problem_set_hash']}`",
        "",
        "## 2. Exploration strategy",
        "",
        "- Loop pattern: generate 10 languages → evaluate solvers → write results into the strategy tree → expand 10 new languages from the result-guided diversity policy.",
        f"- Target candidates: {state.get('target_candidates', 'n/a')}",
        f"- Batch size: {state.get('batch_size', 'n/a')}",
        f"- Problem limit per evaluation pass: {state.get('problem_limit') or summary.get('problem_count') or 'n/a'}",
        f"- Expansion policy: {report_json['iterative_strategy']['expansion_policy']}",
        "- Solver pool:",
    ]
    for model in solver_pool:
        md_lines.append(f"  - `{model['model']}` ({model['provider']}), repeats={model['repeats']}")

    md_lines.extend(
        [
            "",
            "## 3. Model accuracy",
            "",
            render_model_table(by_model) if by_model else "No completed model attempts yet.",
            "",
            "## 4. Problem accuracy",
            "",
            render_problem_table(by_problem) if by_problem else "No completed problem attempts yet.",
            "",
            "## 5. Language family coverage",
            "",
            "### Semantic family counts",
        ]
    )
    if family["family_counts"]:
        for name, count in family["family_counts"].items():
            md_lines.append(f"- `{name}`: {count}")
    else:
        md_lines.append("- n/a")

    md_lines.extend(["", "### Top semantic combinations"])
    if family["top_combinations"]:
        for name, count in list(family["top_combinations"].items())[:10]:
            md_lines.append(f"- `{name}`: {count}")
    else:
        md_lines.append("- n/a")

    md_lines.extend(["", "## 6. Hardest candidate languages"])
    if ranked_candidates:
        for idx, (name, row) in enumerate(ranked_candidates[: args.top], start=1):
            md_lines.extend(["", render_candidate(name, row, lookup.get(name), idx)])
    else:
        md_lines.append("\nNo completed candidate evaluations yet.")

    md_lines.extend(
        [
            "",
            "## 7. Notes",
            "",
            "- Accuracy here means full validator pass rate for a solver attempt on a candidate/problem pair.",
            "- A candidate is 'hard' when it has a high solver failure rate after successful API/model requests, not when requests fail infrastructurally.",
            "- The strategy tree and artifacts should be inspected alongside this report for exact prompts, programs, and failed test cases.",
        ]
    )

    artifacts.mkdir(parents=True, exist_ok=True)
    (artifacts / "final_report.json").write_text(json.dumps(report_json, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (artifacts / "final_report.md").write_text("\n".join(md_lines) + "\n", encoding="utf-8")

    print("\n".join(md_lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
