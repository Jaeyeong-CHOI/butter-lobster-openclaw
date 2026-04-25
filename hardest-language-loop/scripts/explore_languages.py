#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from llm_failure_pl.agents import LanguageDesignerAgent, SolverAgent
from llm_failure_pl.data_store import FileStore
from llm_failure_pl.interpreter import LanguageSpec, PythonToyInterpreter
from llm_failure_pl.openai_client import OpenAIClientError, OpenAIResponsesClient
from llm_failure_pl.problems import default_problem_set
from llm_failure_pl.prompts import INTERPRETER_CONTRACT, LANGUAGE_DESIGNER_SYSTEM
from llm_failure_pl.secrets import get_provider_api_key
from llm_failure_pl.settings import AgentSettings, default_settings
from llm_failure_pl.strategy_tree import StrategyTree

ALLOWED_RULES = {
    "truthiness": {"python", "inverted", "zero_true", "empty_true", "nonempty_false"},
    "if_semantics": {"normal", "inverted"},
    "comparison_semantics": {"normal", "inverted", "swapped_order"},
    "arithmetic_semantics": {"normal", "plus_minus_swapped", "subtraction_reversed", "multiplication_as_addition"},
    "literal_semantics": {"normal", "numeric_negated", "bool_inverted"},
}

DEFAULT_RULES = {
    "truthiness": "python",
    "if_semantics": "normal",
    "comparison_semantics": "normal",
    "arithmetic_semantics": "normal",
    "literal_semantics": "normal",
}


def canonical_json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def stable_hash(data: Any) -> str:
    return hashlib.sha256(canonical_json(data).encode("utf-8")).hexdigest()[:16]


def file_sha256(path: Path) -> str | None:
    if not path.exists():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_info() -> dict[str, Any]:
    def run_git(*args: str) -> str | None:
        try:
            return subprocess.check_output(["git", *args], cwd=ROOT, text=True, stderr=subprocess.DEVNULL).strip()
        except Exception:
            return None

    status = run_git("status", "--short")
    return {
        "commit": run_git("rev-parse", "HEAD"),
        "branch": run_git("branch", "--show-current"),
        "dirty": bool(status),
        "status_short": status.splitlines()[:200] if status else [],
    }


def code_fingerprints() -> dict[str, str | None]:
    paths = [
        "scripts/explore_languages.py",
        "llm_failure_pl/interpreter.py",
        "llm_failure_pl/problems.py",
        "llm_failure_pl/prompts.py",
        "llm_failure_pl/settings.py",
        "llm_failure_pl/strategy_tree.py",
        "llm_failure_pl/openai_client.py",
    ]
    return {path: file_sha256(ROOT / path) for path in paths}


def fallback_candidates(limit: int) -> list[dict[str, Any]]:
    candidates = [
        {
            "title": "Comparison order is swapped",
            "hypothesis": "Solvers may emit familiar < and > branches from task priors even when the language swaps their ordering semantics.",
            "tags": ["comparison", "ordering", "seed", "surface-near"],
            "language_spec": {
                "name": "comparison-swapped-order-v0",
                "description": "JSON-AST language where < behaves like > and > behaves like <, while equality remains normal.",
                "semantic_rules": {**DEFAULT_RULES, "comparison_semantics": "swapped_order"},
            },
        },
        {
            "title": "Plus and minus are swapped",
            "hypothesis": "Arithmetic operator priors are very strong; swapping + and - tests whether solvers construct expressions from semantics rather than symbols.",
            "tags": ["arithmetic", "operator-prior", "seed", "surface-near"],
            "language_spec": {
                "name": "arith-plus-minus-swapped-v0",
                "description": "JSON-AST language where + performs subtraction and - performs addition.",
                "semantic_rules": {**DEFAULT_RULES, "arithmetic_semantics": "plus_minus_swapped"},
            },
        },
        {
            "title": "Numeric literals are negated",
            "hypothesis": "Models may treat literal constants as stable anchors; negating numeric literals forces them to reason about constants operationally.",
            "tags": ["literal", "numeric", "seed", "surface-far"],
            "language_spec": {
                "name": "literal-numeric-negated-v0",
                "description": "JSON-AST language where every numeric literal evaluates to its negated value.",
                "semantic_rules": {**DEFAULT_RULES, "literal_semantics": "numeric_negated"},
            },
        },
        {
            "title": "All truthiness is inverted",
            "hypothesis": "A broad truthiness inversion tests whether solvers operationalize the spec or rely on ordinary truthy/falsey intuition.",
            "tags": ["truthiness", "semantic-inversion", "seed", "surface-near"],
            "language_spec": {
                "name": "truthiness-inverted-v0",
                "description": "JSON-AST language where every value's truthiness is the opposite of Python truthiness.",
                "semantic_rules": {**DEFAULT_RULES, "truthiness": "inverted"},
            },
        },
        {
            "title": "If branch is inverted",
            "hypothesis": "Control-flow priors are strong; even if the solver forms a correct condition it may forget the language chooses the opposite branch.",
            "tags": ["control-flow", "if", "seed", "surface-near"],
            "language_spec": {
                "name": "control-if-inverted-v0",
                "description": "JSON-AST language where if selects the else branch when the condition is truthy and then branch otherwise.",
                "semantic_rules": {**DEFAULT_RULES, "if_semantics": "inverted"},
            },
        },
        {
            "title": "Multiplication behaves like addition",
            "hypothesis": "A non-invertible arithmetic rule tests whether solvers can avoid a familiar operator or compensate with repeated structure.",
            "tags": ["arithmetic", "nonstandard", "seed", "surface-far"],
            "language_spec": {
                "name": "arith-multiplication-as-addition-v0",
                "description": "JSON-AST language where * evaluates as addition rather than multiplication.",
                "semantic_rules": {**DEFAULT_RULES, "arithmetic_semantics": "multiplication_as_addition"},
            },
        },
    ]
    return candidates[:limit]


def load_candidate_file(path: Path, limit: int) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    raw_candidates = data.get("candidate_languages") if isinstance(data, dict) else data
    if not isinstance(raw_candidates, list):
        raise ValueError(f"candidate file must contain a list or candidate_languages list: {path}")
    candidates: list[dict[str, Any]] = []
    seen_rules: set[tuple[tuple[str, str], ...]] = set()
    for idx, raw in enumerate(raw_candidates):
        if not isinstance(raw, dict):
            continue
        candidate = normalize_candidate(raw, idx)
        if not candidate:
            continue
        key = tuple(sorted(candidate["language_spec"]["semantic_rules"].items()))
        if key in seen_rules:
            continue
        seen_rules.add(key)
        candidates.append(candidate)
        if len(candidates) >= limit:
            break
    if not candidates:
        raise ValueError(f"candidate file did not contain any executable candidates: {path}")
    return candidates


def normalize_candidate(raw: dict[str, Any], index: int) -> dict[str, Any] | None:
    spec = raw.get("language_spec") or raw.get("spec") or {}
    rules = dict(spec.get("semantic_rules") or {})
    normalized_rules = {key: rules.get(key, default) for key, default in DEFAULT_RULES.items()}
    for key, allowed in ALLOWED_RULES.items():
        if normalized_rules[key] not in allowed:
            return None
    return {
        "title": str(raw.get("title") or raw.get("name") or f"candidate-{index}"),
        "hypothesis": str(raw.get("hypothesis") or raw.get("rationale") or "No hypothesis provided."),
        "tags": list(raw.get("tags") or []),
        "language_spec": {
            "name": str(spec.get("name") or f"candidate-language-{index}"),
            "description": str(spec.get("description") or raw.get("hypothesis") or "Candidate language."),
            "semantic_rules": normalized_rules,
        },
    }


def designer_prompt(tree: StrategyTree, candidate_count: int) -> str:
    payload = {
        "goal": (
            "Propose candidate language semantics that may make LLM solvers fail on implementation tasks. "
            "Do not assume Python-near is the answer; cover multiple semantic families and surface distances."
        ),
        "candidate_count": candidate_count,
        "strategy_tree": tree.compact(),
        "allowed_semantic_rules": {key: sorted(values) for key, values in ALLOWED_RULES.items()},
        "interpreter_contract": INTERPRETER_CONTRACT,
        "benchmark_problem_summary": [
            {"problem_id": p.problem_id, "title": p.title, "tags": p.tags, "inputs": p.inputs}
            for p in default_problem_set()
        ],
        "selection_guidance": [
            "Preserve breadth: choose candidates from different semantic families before exploiting a single family.",
            "Keep each candidate auditable: one primary surprising rule unless combining rules is the explicit hypothesis.",
            "Surface syntax is fixed as JSON AST for now, but semantics may be Python-near, Python-far, or abstract.",
            "Each candidate must be executable by the existing PythonToyInterpreter semantic_rules.",
        ],
        "requested_output_schema": {
            "candidate_languages": [
                {
                    "title": "short node title",
                    "hypothesis": "why this semantic rule may expose LLM failure",
                    "tags": ["short", "tags"],
                    "language_spec": {
                        "name": "short-language-id",
                        "description": "one sentence",
                        "semantic_rules": {
                            "truthiness": "python | inverted | zero_true | empty_true | nonempty_false",
                            "if_semantics": "normal | inverted",
                            "comparison_semantics": "normal | inverted | swapped_order",
                            "arithmetic_semantics": "normal | plus_minus_swapped | subtraction_reversed | multiplication_as_addition",
                            "literal_semantics": "normal | numeric_negated | bool_inverted",
                        },
                    },
                }
            ],
            "rationale": "brief selection rationale",
        },
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def generate_candidates(
    client: OpenAIResponsesClient | None,
    tree: StrategyTree,
    settings: AgentSettings,
    candidate_count: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if client is None:
        return fallback_candidates(candidate_count), {"source": "fallback", "error": "no OpenAI client"}
    prompt = designer_prompt(tree, candidate_count)
    try:
        response = client.call_json(system=LANGUAGE_DESIGNER_SYSTEM, user=prompt, settings=settings)
        parsed = response["parsed"]
        raw_candidates = parsed.get("candidate_languages") if isinstance(parsed, dict) else None
        if not isinstance(raw_candidates, list):
            raise ValueError("candidate_languages missing or not a list")
        candidates = []
        seen_rules: set[tuple[tuple[str, str], ...]] = set()
        for idx, raw in enumerate(raw_candidates):
            if not isinstance(raw, dict):
                continue
            candidate = normalize_candidate(raw, idx)
            if not candidate:
                continue
            rules = candidate["language_spec"]["semantic_rules"]
            key = tuple(sorted(rules.items()))
            if key in seen_rules:
                continue
            seen_rules.add(key)
            candidates.append(candidate)
            if len(candidates) >= candidate_count:
                break
        if len(candidates) < candidate_count:
            for fallback in fallback_candidates(candidate_count):
                rules = fallback["language_spec"]["semantic_rules"]
                key = tuple(sorted(rules.items()))
                if key not in seen_rules:
                    candidates.append(fallback)
                    seen_rules.add(key)
                if len(candidates) >= candidate_count:
                    break
        return candidates[:candidate_count], {"source": "agent", "response": {k: v for k, v in response.items() if k != "raw"}}
    except Exception as exc:  # noqa: BLE001 - fallback is intentional and recorded
        return fallback_candidates(candidate_count), {"source": "fallback", "error": f"{type(exc).__name__}: {exc}"}


def validate_solver_program(language_spec: dict[str, Any], problem: Any, program: dict[str, Any]) -> dict[str, Any]:
    interpreter = PythonToyInterpreter(LanguageSpec.from_dict(language_spec))
    results = interpreter.run_cases(problem.interpreter_cases_for(program))
    failed = [result for result in results if not result["success"]]
    return {
        "success": not failed,
        "num_tests": len(results),
        "num_failed": len(failed),
        "first_failure_case_id": failed[0]["case_id"] if failed else None,
        "results": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a small language-search pilot.")
    parser.add_argument("--candidates", type=int, default=3)
    parser.add_argument("--problem-limit", type=int, default=3)
    parser.add_argument("--max-evaluations", type=int, default=0, help="0 means no extra cap")
    parser.add_argument("--no-api", action="store_true", help="Generate artifacts without model calls")
    parser.add_argument("--generate-only", action="store_true", help="Stop after creating candidate language nodes")
    parser.add_argument("--candidate-source", choices=["agent", "seed", "file"], default="agent")
    parser.add_argument("--candidate-file", type=Path, help="Replay candidate languages from a previous run artifact")
    parser.add_argument("--run-id", help="Optional fixed run id; useful for scripted reproductions")
    parser.add_argument("--seed", type=int, help="Record an explicit experiment seed in the manifest")
    args = parser.parse_args()

    settings = default_settings()
    if args.seed is not None:
        settings.seed = args.seed
    settings.dry_run = bool(args.no_api)
    store = FileStore(settings.data_root)
    paths = store.start_run(settings=settings, run_id=args.run_id)
    tree = LanguageDesignerAgent.new_strategy_tree()
    solver = SolverAgent(settings.solver)

    api_key = None if args.no_api else get_provider_api_key("openai")
    client = OpenAIResponsesClient(api_key, timeout_seconds=120, max_attempts=3) if api_key else None

    if args.candidate_source == "seed":
        candidates, designer_info = fallback_candidates(args.candidates), {"source": "seed_catalog", "seed": settings.seed}
    elif args.candidate_source == "file":
        if not args.candidate_file:
            parser.error("--candidate-file is required when --candidate-source=file")
        candidate_file = args.candidate_file if args.candidate_file.is_absolute() else ROOT / args.candidate_file
        candidates = load_candidate_file(candidate_file, args.candidates)
        designer_info = {
            "source": "candidate_file",
            "path": str(candidate_file),
            "sha256": file_sha256(candidate_file),
            "seed": settings.seed,
        }
    else:
        candidates, designer_info = generate_candidates(client, tree, settings.language_designer, args.candidates)
    store.save_json_artifact(paths, "designer_response.json", designer_info)
    store.append_event(paths, "designer_candidates_ready", {"count": len(candidates), "source": designer_info.get("source")})

    node_by_candidate: dict[str, str] = {}
    for idx, candidate in enumerate(candidates):
        spec = candidate["language_spec"]
        node = tree.add_child(
            tree.root_id,
            title=candidate["title"],
            hypothesis=candidate["hypothesis"],
            tags=[*candidate.get("tags", []), "candidate-language"],
            artifacts={"language_spec": spec, "candidate_index": idx},
            note="Candidate language selected for exploration.",
        )
        node_by_candidate[spec["name"]] = node.id

    base_problems = default_problem_set()
    problems = base_problems[: max(1, min(args.problem_limit, len(base_problems)))]
    store.save_json_artifact(paths, "candidate_languages.json", candidates)
    store.save_json_artifact(
        paths,
        "problem_set.json",
        [problem.to_dict(include_reference=True, include_hidden=True) for problem in problems],
    )

    candidate_file_rel = Path(paths.root.name) / "artifacts" / "candidate_languages.json"
    replay_args = [
        "python3",
        "scripts/explore_languages.py",
        "--candidate-source",
        "file",
        "--candidate-file",
        str(Path(settings.data_root) / candidate_file_rel),
        "--candidates",
        str(len(candidates)),
        "--problem-limit",
        str(len(problems)),
        "--seed",
        str(settings.seed),
    ]
    if args.no_api:
        replay_args.append("--no-api")
    reproducibility = {
        "schema_version": 1,
        "seed": settings.seed,
        "args": vars(args) | {"candidate_file": str(args.candidate_file) if args.candidate_file else None},
        "candidate_source": designer_info.get("source"),
        "candidate_count": len(candidates),
        "candidate_hashes": {
            candidate["language_spec"]["name"]: stable_hash(candidate["language_spec"])
            for candidate in candidates
        },
        "candidate_set_hash": stable_hash([candidate["language_spec"] for candidate in candidates]),
        "problem_ids": [problem.problem_id for problem in problems],
        "problem_set_hash": stable_hash([problem.to_dict(include_reference=True, include_hidden=True) for problem in problems]),
        "solver_models": [model.to_dict() for model in settings.solver_models],
        "language_designer": settings.language_designer.to_dict(),
        "git": git_info(),
        "python": sys.version,
        "platform": platform.platform(),
        "code_fingerprints": code_fingerprints(),
        "replay_command": " ".join(replay_args),
        "notes": [
            "For exact candidate replay, use --candidate-source=file with artifacts/candidate_languages.json from this run.",
            "Solver calls use temperature=0.0, but hosted model APIs can still change over time; compare aggregate rankings, not byte-identical outputs.",
        ],
    }
    store.save_json_artifact(paths, "reproducibility.json", reproducibility)
    store.save_text_artifact(paths, "replay_command.txt", reproducibility["replay_command"] + "\n")

    if args.generate_only:
        summary = {
            "run_id": paths.run_id,
            "run_dir": str(paths.root),
            "designer_source": designer_info.get("source"),
            "candidate_count": len(candidates),
            "problem_count": len(problems),
            "candidate_set_hash": reproducibility["candidate_set_hash"],
            "problem_set_hash": reproducibility["problem_set_hash"],
            "requested_evaluations": 0,
            "completed_model_requests": 0,
            "infrastructure_errors": 0,
            "candidate_names": [candidate["language_spec"]["name"] for candidate in candidates],
            "tree_root": tree.get(tree.root_id).to_dict(),
        }
        store.save_json_artifact(paths, "summary.json", summary)
        store.save_tree(paths, tree)
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0

    combos: list[tuple[dict[str, Any], Any, Any]] = []
    for problem in problems:
        for candidate in candidates:
            for model in settings.solver_models:
                combos.append((candidate, problem, model))
    if args.max_evaluations and args.max_evaluations > 0:
        combos = combos[: args.max_evaluations]

    evaluations: list[dict[str, Any]] = []
    for eval_index, (candidate, problem, model) in enumerate(combos, start=1):
        spec = candidate["language_spec"]
        node_id = node_by_candidate[spec["name"]]
        rendered = solver.render(spec, problem.to_solver_task(), solver_model=model.to_dict())
        eval_id = f"eval-{eval_index:04d}-{spec['name']}-{problem.problem_id}-{model.model}"
        store.save_json_artifact(paths, f"prompts/{eval_id}.json", rendered)

        evaluation: dict[str, Any] = {
            "eval_id": eval_id,
            "candidate_name": spec["name"],
            "node_id": node_id,
            "problem_id": problem.problem_id,
            "model": model.model,
            "provider": model.provider,
            "request_ok": False,
            "success": False,
        }

        if client is None:
            evaluation.update({"error": "no OpenAI client/API key", "counted": False})
            tree.record_result(
                node_id,
                {
                    "success": False,
                    "counted": False,
                    "model": model.model,
                    "problem_id": problem.problem_id,
                    "note": "No API client; evaluation skipped.",
                },
            )
            evaluations.append(evaluation)
            continue

        try:
            response = client.call_json(system=rendered["system"], user=rendered["user"], settings=rendered["settings"])
            parsed = response["parsed"]
            program = parsed.get("program") if isinstance(parsed, dict) else parsed
            if not isinstance(program, dict):
                raise ValueError("solver response did not contain a JSON AST object")
            validation = validate_solver_program(spec, problem, program)
            evaluation.update(
                {
                    "request_ok": True,
                    "success": validation["success"],
                    "num_tests": validation["num_tests"],
                    "num_failed": validation["num_failed"],
                    "first_failure_case_id": validation["first_failure_case_id"],
                    "program": program,
                    "validation": validation,
                    "response_text": response["text"],
                    "retry_count": response["retry_count"],
                    "attempt_notes": response["attempt_notes"],
                }
            )
            tree.record_result(
                node_id,
                {
                    "success": validation["success"],
                    "model": model.model,
                    "problem_id": problem.problem_id,
                    "case_id": validation["first_failure_case_id"],
                    "note": f"{validation['num_failed']}/{validation['num_tests']} tests failed",
                },
            )
        except (OpenAIClientError, ValueError, KeyError) as exc:
            evaluation.update({"error": f"{type(exc).__name__}: {exc}", "counted": False})
            tree.record_result(
                node_id,
                {
                    "success": False,
                    "counted": False,
                    "model": model.model,
                    "problem_id": problem.problem_id,
                    "note": f"Infrastructure/model error: {type(exc).__name__}",
                },
            )
        evaluations.append(evaluation)
        store.save_json_artifact(paths, f"evaluations/{eval_id}.json", evaluation)
        store.save_tree(paths, tree)
        store.append_event(paths, "evaluation_completed", {k: evaluation.get(k) for k in ["eval_id", "success", "request_ok", "candidate_name", "problem_id", "model"]})

    summary_by_candidate: dict[str, dict[str, Any]] = {}
    for candidate in candidates:
        spec = candidate["language_spec"]
        node = tree.get(node_by_candidate[spec["name"]])
        candidate_evals = [item for item in evaluations if item["candidate_name"] == spec["name"] and item.get("request_ok")]
        summary_by_candidate[spec["name"]] = {
            "title": candidate["title"],
            "candidate_hash": reproducibility["candidate_hashes"][spec["name"]],
            "semantic_rules": spec["semantic_rules"],
            "evaluations": len(candidate_evals),
            "solver_failures": sum(1 for item in candidate_evals if not item.get("success")),
            "solver_failure_rate": (
                sum(1 for item in candidate_evals if not item.get("success")) / len(candidate_evals) if candidate_evals else None
            ),
            "tree_metrics": node.metrics,
        }

    summary = {
        "run_id": paths.run_id,
        "run_dir": str(paths.root),
        "designer_source": designer_info.get("source"),
        "candidate_count": len(candidates),
        "problem_count": len(problems),
        "candidate_set_hash": reproducibility["candidate_set_hash"],
        "problem_set_hash": reproducibility["problem_set_hash"],
        "requested_evaluations": len(combos),
        "completed_model_requests": sum(1 for item in evaluations if item.get("request_ok")),
        "infrastructure_errors": sum(1 for item in evaluations if not item.get("request_ok")),
        "by_candidate": summary_by_candidate,
        "best_node": tree.best_node_for_expansion().to_dict(),
    }
    store.save_json_artifact(paths, "evaluations.json", evaluations)
    store.save_json_artifact(paths, "summary.json", summary)
    store.save_tree(paths, tree)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["completed_model_requests"] > 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
