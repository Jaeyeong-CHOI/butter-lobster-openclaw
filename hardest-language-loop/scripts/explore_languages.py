#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import platform
import subprocess
import sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from llm_failure_pl.agents import LanguageDesignerAgent, SolverAgent
from llm_failure_pl.data_store import FileStore
from llm_failure_pl.interpreter import LanguageSpec, PythonToyInterpreter
from llm_failure_pl.openai_client import OpenAIChatCompletionsClient, OpenAIClientError, OpenAIResponsesClient
from llm_failure_pl.problems import default_problem_set
from llm_failure_pl.prompts import INTERPRETER_CONTRACT, LANGUAGE_DESIGNER_SYSTEM
from llm_failure_pl.secrets import get_provider_api_key, get_secret
from llm_failure_pl.settings import AgentSettings, SolverModelSettings, default_settings
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

RULE_VALUES = {
    "truthiness": ["python", "inverted", "zero_true", "empty_true", "nonempty_false"],
    "if_semantics": ["normal", "inverted"],
    "comparison_semantics": ["normal", "inverted", "swapped_order"],
    "arithmetic_semantics": ["normal", "plus_minus_swapped", "subtraction_reversed", "multiplication_as_addition"],
    "literal_semantics": ["normal", "numeric_negated", "bool_inverted"],
}


def canonical_json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def stable_hash(data: Any) -> str:
    return hashlib.sha256(canonical_json(data).encode("utf-8")).hexdigest()[:16]


def candidate_hashes(candidates: list[dict[str, Any]]) -> dict[str, str]:
    return {candidate["language_spec"]["name"]: stable_hash(candidate["language_spec"]) for candidate in candidates}


def candidate_set_hash(candidates: list[dict[str, Any]]) -> str:
    return stable_hash([candidate["language_spec"] for candidate in candidates])


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
    seen_rules = {tuple(sorted(candidate["language_spec"]["semantic_rules"].items())) for candidate in candidates}

    rule_keys = list(DEFAULT_RULES.keys())
    for values in itertools.product(*(RULE_VALUES[key] for key in rule_keys)):
        rules = dict(zip(rule_keys, values, strict=True))
        if rules == DEFAULT_RULES:
            continue
        key = tuple(sorted(rules.items()))
        if key in seen_rules:
            continue
        changed = {rule_key: value for rule_key, value in rules.items() if value != DEFAULT_RULES[rule_key]}
        slug = "__".join(f"{rule_key.replace('_semantics', '').replace('_', '-')}-{value.replace('_', '-')}" for rule_key, value in changed.items())
        title = ", ".join(f"{rule_key.replace('_semantics', '').replace('_', ' ')}={value}" for rule_key, value in changed.items())
        tags = ["seed", "grid", *[rule_key.replace("_semantics", "") for rule_key in changed]]
        candidates.append(
            {
                "title": title,
                "hypothesis": (
                    "A deterministic grid candidate testing whether solvers can operationalize "
                    f"the combined semantic shifts: {', '.join(f'{k}={v}' for k, v in changed.items())}."
                ),
                "tags": tags,
                "language_spec": {
                    "name": f"grid-{slug}-v0",
                    "description": "JSON-AST language with deterministic seed-catalog semantic shifts: "
                    + ", ".join(f"{k}={v}" for k, v in changed.items())
                    + ".",
                    "semantic_rules": rules,
                },
            }
        )
        seen_rules.add(key)
        if len(candidates) >= limit:
            break
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
        if limit > 0 and len(candidates) >= limit:
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


def solver_client_for_model(model: SolverModelSettings, *, no_api: bool) -> OpenAIResponsesClient | OpenAIChatCompletionsClient | None:
    if no_api:
        return None
    if model.base_url:
        api_key = get_secret(model.api_key_env) if model.api_key_env else None
        return OpenAIChatCompletionsClient(
            api_key=api_key or "EMPTY",
            base_url=model.base_url,
            timeout_seconds=model.timeout_seconds,
            max_attempts=1,
        )
    if model.provider == "openai":
        api_key = get_provider_api_key("openai")
        if not api_key:
            return None
        return OpenAIResponsesClient(api_key, timeout_seconds=model.timeout_seconds, max_attempts=3)
    return None


def run_solver_evaluation(job: dict[str, Any]) -> dict[str, Any]:
    evaluation = dict(job["evaluation"])
    client = job.get("client")
    rendered = job["rendered"]
    spec = job["language_spec"]
    problem = job["problem"]

    if client is None:
        evaluation.update({"error": "no API client/API key", "counted": False})
        return evaluation

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
    except (OpenAIClientError, ValueError, KeyError) as exc:
        evaluation.update({"error": f"{type(exc).__name__}: {exc}", "counted": False})
    return evaluation


def candidate_nodes_by_name(tree: StrategyTree) -> dict[str, str]:
    nodes: dict[str, str] = {}
    for node_id, node in tree.nodes.items():
        spec = node.artifacts.get("language_spec") if isinstance(node.artifacts, dict) else None
        if isinstance(spec, dict) and isinstance(spec.get("name"), str):
            nodes[spec["name"]] = node_id
    return nodes


EvaluationKey = tuple[str, str, str, int]


def evaluation_key(candidate_name: Any, problem_id: Any, model: Any, repeat_index: Any) -> EvaluationKey | None:
    if not candidate_name or not problem_id or not model:
        return None
    try:
        repeat = int(repeat_index or 1)
    except Exception:
        repeat = 1
    return (str(candidate_name), str(problem_id), str(model), repeat)


def evaluation_key_from_item(item: dict[str, Any]) -> EvaluationKey | None:
    return evaluation_key(item.get("candidate_name"), item.get("problem_id"), item.get("model"), item.get("repeat_index"))


def reuse_existing_evaluation(existing: dict[str, Any], current: dict[str, Any]) -> dict[str, Any]:
    reused = dict(existing)
    if existing.get("eval_id") != current.get("eval_id"):
        reused["source_eval_id"] = existing.get("eval_id")
    if existing.get("eval_index") != current.get("eval_index"):
        reused["source_eval_index"] = existing.get("eval_index")
    for key in ["eval_index", "eval_id", "candidate_name", "node_id", "problem_id", "model", "provider", "base_url", "repeat_index"]:
        reused[key] = current.get(key)
    return reused


def load_existing_evaluations(paths: Any) -> dict[EvaluationKey, dict[str, Any]]:
    evaluations: dict[EvaluationKey, dict[str, Any]] = {}

    def add_item(item: Any, *, source: str, tree_recorded: bool) -> None:
        if not isinstance(item, dict):
            return
        key = evaluation_key_from_item(item)
        if key is None:
            return
        enriched = dict(item)
        enriched["_existing_source"] = source
        enriched["_tree_recorded"] = tree_recorded
        previous = evaluations.get(key)
        if previous is None or (enriched.get("request_ok") and not previous.get("request_ok")):
            evaluations[key] = enriched

    evaluations_path = paths.artifacts / "evaluations.json"
    if evaluations_path.exists():
        try:
            data = json.loads(evaluations_path.read_text(encoding="utf-8"))
            if isinstance(data, list):
                for item in data:
                    add_item(item, source="evaluations.json", tree_recorded=True)
        except Exception:
            pass

    partial_path = paths.artifacts / "evaluations.partial.json"
    if partial_path.exists():
        try:
            data = json.loads(partial_path.read_text(encoding="utf-8"))
            if isinstance(data, list):
                for item in data:
                    add_item(item, source="evaluations.partial.json", tree_recorded=False)
        except Exception:
            pass

    evaluations_dir = paths.artifacts / "evaluations"
    if evaluations_dir.exists():
        for path in evaluations_dir.glob("eval-*.json"):
            try:
                add_item(json.loads(path.read_text(encoding="utf-8")), source="evaluations/*.json", tree_recorded=False)
            except Exception:
                continue

    return evaluations


def save_incremental_evaluation(
    store: FileStore,
    paths: Any,
    evaluation: dict[str, Any],
    *,
    completed: list[dict[str, Any]],
    skipped_existing: list[dict[str, Any]],
    flush_every: int,
) -> None:
    store.save_json_artifact(paths, f"evaluations/{evaluation['eval_id']}.json", evaluation)
    if flush_every > 0 and len(completed) % flush_every == 0:
        store.save_json_artifact(
            paths,
            "evaluations.partial.json",
            sorted([*skipped_existing, *completed], key=lambda item: item.get("eval_index", 0)),
        )


def changed_semantic_rules(rules: dict[str, str]) -> dict[str, str]:
    return {key: value for key, value in rules.items() if DEFAULT_RULES.get(key) != value}


def summarize_evaluations_by_candidate(evaluations: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    summaries: dict[str, dict[str, Any]] = {}
    for item in evaluations:
        name = item.get("candidate_name")
        if not name or not item.get("request_ok"):
            continue
        summary = summaries.setdefault(
            name,
            {
                "candidate_name": name,
                "trials": 0,
                "successes": 0,
                "failures": 0,
                "failure_rate": None,
                "model_stats": {},
                "problem_stats": {},
                "first_failure_case_ids": [],
            },
        )
        success = bool(item.get("success"))
        summary["trials"] += 1
        summary["successes"] += int(success)
        summary["failures"] += int(not success)
        if not success and item.get("first_failure_case_id"):
            failure_case = item["first_failure_case_id"]
            if failure_case not in summary["first_failure_case_ids"]:
                summary["first_failure_case_ids"].append(failure_case)

        for bucket, key in (("model_stats", item.get("model")), ("problem_stats", item.get("problem_id"))):
            if not key:
                continue
            stats = summary[bucket].setdefault(key, {"trials": 0, "successes": 0, "failures": 0, "failure_rate": None})
            stats["trials"] += 1
            stats["successes"] += int(success)
            stats["failures"] += int(not success)
            stats["failure_rate"] = stats["failures"] / stats["trials"] if stats["trials"] else None

    for summary in summaries.values():
        summary["failure_rate"] = summary["failures"] / summary["trials"] if summary["trials"] else None
    return summaries


def annotate_tree_with_result_summaries(
    tree: StrategyTree,
    node_by_candidate: dict[str, str],
    candidate_summaries: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    ranked = sorted(
        candidate_summaries.values(),
        key=lambda item: (float(item.get("failure_rate") or 0.0), int(item.get("trials") or 0)),
        reverse=True,
    )
    for name, summary in candidate_summaries.items():
        node_id = node_by_candidate.get(name)
        if not node_id:
            continue
        node = tree.attach_artifact(node_id, "latest_evaluation_summary", summary)
        rate = summary.get("failure_rate")
        rate_text = "n/a" if rate is None else f"{rate:.3f}"
        note = f"aggregate_result: trials={summary['trials']} failures={summary['failures']} failure_rate={rate_text}"
        if not node.notes or node.notes[-1] != note:
            node.notes.append(note)

    global_summary = {
        "evaluated_candidates": len(candidate_summaries),
        "top_failure_candidates": [
            {
                "candidate_name": item["candidate_name"],
                "trials": item["trials"],
                "failures": item["failures"],
                "failure_rate": item["failure_rate"],
            }
            for item in ranked[:20]
        ],
    }
    tree.attach_artifact(tree.root_id, "latest_evaluation_summary", global_summary)
    return global_summary


def hamming_rules(left: dict[str, str], right: dict[str, str]) -> int:
    return sum(1 for key in DEFAULT_RULES if left.get(key) != right.get(key))


def result_guided_expansion_candidates(
    candidates: list[dict[str, Any]],
    node_by_candidate: dict[str, str],
    candidate_summaries: dict[str, dict[str, Any]],
    limit: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if limit <= 0:
        return [], {"reason": "disabled", "requested": limit}

    existing_rules = {tuple(sorted(candidate["language_spec"]["semantic_rules"].items())) for candidate in candidates}
    existing_names = {candidate["language_spec"]["name"] for candidate in candidates}
    all_grid = fallback_candidates(1000)
    pool = [
        candidate
        for candidate in all_grid
        if candidate["language_spec"]["name"] not in existing_names
        and tuple(sorted(candidate["language_spec"]["semantic_rules"].items())) not in existing_rules
    ]
    if not pool:
        return [], {"reason": "candidate_grid_exhausted", "requested": limit}

    candidate_by_name = {candidate["language_spec"]["name"]: candidate for candidate in candidates}
    evaluated = [
        summary
        for summary in candidate_summaries.values()
        if summary.get("trials") and summary.get("candidate_name") in candidate_by_name
    ]
    high_failure = sorted(
        evaluated,
        key=lambda item: (float(item.get("failure_rate") or 0.0), int(item.get("trials") or 0)),
        reverse=True,
    )[:50]

    family_counts: dict[str, int] = defaultdict(int)
    pair_counts: dict[tuple[str, ...], int] = defaultdict(int)
    for candidate in candidates:
        changed = changed_semantic_rules(candidate["language_spec"]["semantic_rules"])
        families = tuple(sorted(changed)) or ("baseline",)
        pair_counts[families] += 1
        for family in families:
            family_counts[family] += 1

    scored: list[tuple[float, dict[str, Any], dict[str, Any]]] = []
    for candidate in pool:
        rules = candidate["language_spec"]["semantic_rules"]
        changed = changed_semantic_rules(rules)
        families = tuple(sorted(changed)) or ("baseline",)
        diversity_score = sum(1.0 / (1 + family_counts[family]) for family in families)
        combo_score = 1.0 / (1 + pair_counts[families])
        exploit_score = 0.0
        parent_id = None
        parent_candidate = None
        nearest_distance = None
        for summary in high_failure:
            base_candidate = candidate_by_name[summary["candidate_name"]]
            distance = hamming_rules(rules, base_candidate["language_spec"]["semantic_rules"])
            if distance == 0:
                continue
            score = float(summary.get("failure_rate") or 0.0) / distance
            if score > exploit_score:
                exploit_score = score
                parent_candidate = summary["candidate_name"]
                parent_id = node_by_candidate.get(parent_candidate)
                nearest_distance = distance
        score = exploit_score + diversity_score + combo_score + (0.03 * len(changed))
        scored.append(
            (
                score,
                candidate,
                {
                    "score": round(score, 6),
                    "exploit_score": round(exploit_score, 6),
                    "diversity_score": round(diversity_score, 6),
                    "combo_score": round(combo_score, 6),
                    "changed_families": list(families),
                    "parent_candidate": parent_candidate,
                    "parent_id": parent_id,
                    "nearest_distance": nearest_distance,
                },
            )
        )

    selected: list[dict[str, Any]] = []
    selected_meta: list[dict[str, Any]] = []
    selected_family_counts: dict[str, int] = defaultdict(int)
    for _, candidate, meta in sorted(scored, key=lambda item: item[0], reverse=True):
        families = meta["changed_families"]
        if selected and all(selected_family_counts[family] >= max(2, limit // 5) for family in families):
            continue
        selected.append(candidate)
        selected_meta.append(meta)
        for family in families:
            selected_family_counts[family] += 1
        if len(selected) >= limit:
            break

    if len(selected) < limit:
        selected_names = {candidate["language_spec"]["name"] for candidate in selected}
        for _, candidate, meta in sorted(scored, key=lambda item: item[0], reverse=True):
            if candidate["language_spec"]["name"] in selected_names:
                continue
            selected.append(candidate)
            selected_meta.append(meta)
            if len(selected) >= limit:
                break

    plan = {
        "requested": limit,
        "selected": len(selected),
        "pool_size": len(pool),
        "evaluated_candidates": len(evaluated),
        "selection_policy": "exploit high-failure neighborhoods while giving underrepresented semantic families a diversity bonus",
        "candidates": [
            {
                "candidate_name": candidate["language_spec"]["name"],
                "semantic_rules": candidate["language_spec"]["semantic_rules"],
                **meta,
            }
            for candidate, meta in zip(selected, selected_meta, strict=True)
        ],
    }
    return selected, plan


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a small language-search pilot.")
    parser.add_argument("--candidates", type=int, default=3)
    parser.add_argument("--problem-limit", type=int, default=3)
    parser.add_argument("--max-evaluations", type=int, default=0, help="0 means no extra cap")
    parser.add_argument("--no-api", action="store_true", help="Generate artifacts without model calls")
    parser.add_argument("--generate-only", action="store_true", help="Stop after creating candidate language nodes")
    parser.add_argument("--candidate-source", choices=["agent", "seed", "file"], default="agent")
    parser.add_argument("--candidate-file", type=Path, help="Replay candidate languages from a previous run artifact")
    parser.add_argument("--result-root", type=Path, help="Root folder for versioned loop results. Defaults to loop_result.")
    parser.add_argument("--run-id", help="Optional version/run id. Defaults to the next vN folder under result-root.")
    parser.add_argument("--resume", action="store_true", help="Resume an existing result folder. With no --run-id, resumes latest vN.")
    parser.add_argument("--seed", type=int, help="Record an explicit experiment seed in the manifest")
    parser.add_argument(
        "--expand-after-eval",
        type=int,
        default=25,
        help="Append this many result-guided diverse candidate languages after an evaluation batch. Use 0 to disable.",
    )
    parser.add_argument(
        "--parallel-workers",
        type=int,
        help="Maximum parallel solver requests. Defaults to RunSettings.max_parallel_solver_requests.",
    )
    parser.add_argument(
        "--flush-every",
        type=int,
        default=50,
        help="Write completed evaluation artifacts every N finished solver jobs.",
    )
    args = parser.parse_args()
    candidate_source_explicit = any(arg == "--candidate-source" or arg.startswith("--candidate-source=") for arg in sys.argv[1:])
    candidates_explicit = any(arg == "--candidates" or arg.startswith("--candidates=") for arg in sys.argv[1:])

    settings = default_settings()
    if args.result_root is not None:
        settings.data_root = str(args.result_root)
    if args.seed is not None:
        settings.seed = args.seed
    settings.dry_run = bool(args.no_api)
    if args.parallel_workers is not None:
        settings.max_parallel_solver_requests = max(1, args.parallel_workers)
    store = FileStore(settings.data_root)
    run_id = args.run_id
    if args.resume and run_id is None:
        run_id = store.latest_version_id()
        if run_id is None:
            parser.error("--resume requested but no vN folders exist under result-root")
    paths = store.start_run(settings=settings, run_id=run_id, resume=args.resume)
    tree = store.load_tree(paths) if args.resume and paths.strategy_tree.exists() else LanguageDesignerAgent.new_strategy_tree()
    solver = SolverAgent(settings.solver)

    existing_candidate_file = paths.artifacts / "candidate_languages.json"
    if args.resume and not candidate_source_explicit and not args.candidate_file and existing_candidate_file.exists():
        args.candidate_source = "file"
        args.candidate_file = existing_candidate_file
        if not candidates_explicit:
            args.candidates = 0

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

    node_by_candidate: dict[str, str] = candidate_nodes_by_name(tree)
    for idx, candidate in enumerate(candidates):
        spec = candidate["language_spec"]
        if spec["name"] in node_by_candidate:
            continue
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
        "--result-root",
        str(settings.data_root),
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
        "--parallel-workers",
        str(settings.max_parallel_solver_requests),
    ]
    if args.no_api:
        replay_args.append("--no-api")
    args_payload = {key: (str(value) if isinstance(value, Path) else value) for key, value in vars(args).items()}
    args_payload["candidate_file"] = str(args.candidate_file) if args.candidate_file else None
    args_payload["result_root"] = str(args.result_root) if args.result_root else None
    reproducibility = {
        "schema_version": 1,
        "seed": settings.seed,
        "args": args_payload,
        "result_root": str(settings.data_root),
        "run_id": paths.run_id,
        "resume": args.resume,
        "candidate_source": designer_info.get("source"),
        "candidate_count": len(candidates),
        "candidate_hashes": candidate_hashes(candidates),
        "candidate_set_hash": candidate_set_hash(candidates),
        "problem_ids": [problem.problem_id for problem in problems],
        "problem_set_hash": stable_hash([problem.to_dict(include_reference=True, include_hidden=True) for problem in problems]),
        "solver_models": [model.to_dict() for model in settings.solver_models],
        "max_parallel_solver_requests": settings.max_parallel_solver_requests,
        "language_designer": settings.language_designer.to_dict(),
        "git": git_info(),
        "python": sys.version,
        "platform": platform.platform(),
        "code_fingerprints": code_fingerprints(),
        "replay_command": " ".join(replay_args),
        "notes": [
            "For exact candidate replay, use --candidate-source=file with artifacts/candidate_languages.json from this run.",
            "Solver calls use temperature=0.0, but hosted model APIs can still change over time; compare aggregate rankings, not byte-identical outputs.",
            "Local vLLM solver endpoints are OpenAI-compatible chat-completions servers and are safe to evaluate in parallel.",
            "Fresh runs auto-create the next loop_result/vN folder. Use --resume --run-id vN to continue an existing folder.",
            "After evaluation, aggregate results are attached to strategy-tree nodes and a result-guided diversity expansion can append new candidates for the next loop round.",
        ],
    }
    store.save_json_artifact(paths, "reproducibility.json", reproducibility)
    store.save_text_artifact(paths, "replay_command.txt", reproducibility["replay_command"] + "\n")

    if args.generate_only:
        summary = {
            "run_id": paths.run_id,
            "run_dir": str(paths.root),
            "resumed": args.resume,
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

    combos: list[tuple[dict[str, Any], Any, SolverModelSettings, int]] = []
    for problem in problems:
        for candidate in candidates:
            for model in settings.solver_models:
                for repeat_index in range(1, max(1, model.repeats) + 1):
                    combos.append((candidate, problem, model, repeat_index))
    if args.max_evaluations and args.max_evaluations > 0:
        combos = combos[: args.max_evaluations]

    existing_evaluations = load_existing_evaluations(paths) if args.resume else {}
    skipped_existing: list[dict[str, Any]] = []
    skipped_existing_ids: set[str] = set()
    clients_by_model: dict[tuple[str, str, str | None], OpenAIResponsesClient | OpenAIChatCompletionsClient | None] = {}
    jobs: list[dict[str, Any]] = []
    for eval_index, (candidate, problem, model, repeat_index) in enumerate(combos, start=1):
        spec = candidate["language_spec"]
        node_id = node_by_candidate[spec["name"]]
        rendered = solver.render(spec, problem.to_solver_task(), solver_model=model.to_dict())
        repeat_suffix = f"-r{repeat_index:02d}" if max(1, model.repeats) > 1 else ""
        eval_id = f"eval-{eval_index:04d}-{spec['name']}-{problem.problem_id}-{model.model}{repeat_suffix}"
        store.save_json_artifact(paths, f"prompts/{eval_id}.json", rendered)

        evaluation: dict[str, Any] = {
            "eval_index": eval_index,
            "eval_id": eval_id,
            "candidate_name": spec["name"],
            "node_id": node_id,
            "problem_id": problem.problem_id,
            "model": model.model,
            "provider": model.provider,
            "base_url": model.base_url,
            "repeat_index": repeat_index,
            "request_ok": False,
            "success": False,
        }

        existing_evaluation = existing_evaluations.get(evaluation_key(spec["name"], problem.problem_id, model.model, repeat_index))
        if existing_evaluation and existing_evaluation.get("request_ok"):
            skipped_existing.append(reuse_existing_evaluation(existing_evaluation, evaluation))
            skipped_existing_ids.add(eval_id)
            continue

        client_key = (model.provider, model.model, model.base_url)
        if client_key not in clients_by_model:
            clients_by_model[client_key] = solver_client_for_model(model, no_api=args.no_api)

        jobs.append(
            {
                "evaluation": evaluation,
                "rendered": rendered,
                "language_spec": spec,
                "problem": problem,
                "client": clients_by_model[client_key],
            }
        )

    evaluations: list[dict[str, Any]] = []
    max_workers = max(1, min(settings.max_parallel_solver_requests, len(jobs) or 1))
    flush_every = max(0, args.flush_every)
    if max_workers == 1:
        completed = []
        for job in jobs:
            evaluation = run_solver_evaluation(job)
            completed.append(evaluation)
            save_incremental_evaluation(
                store,
                paths,
                evaluation,
                completed=completed,
                skipped_existing=skipped_existing,
                flush_every=flush_every,
            )
    else:
        completed = []
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_by_evaluation = {executor.submit(run_solver_evaluation, job): job["evaluation"] for job in jobs}
            for future in as_completed(future_by_evaluation):
                try:
                    completed.append(future.result())
                except Exception as exc:  # noqa: BLE001 - preserve the failed evaluation record instead of aborting the run
                    evaluation = dict(future_by_evaluation[future])
                    evaluation.update({"error": f"Unexpected worker error: {type(exc).__name__}: {exc}", "counted": False})
                    completed.append(evaluation)
                save_incremental_evaluation(
                    store,
                    paths,
                    completed[-1],
                    completed=completed,
                    skipped_existing=skipped_existing,
                    flush_every=flush_every,
                )

    if completed:
        store.save_json_artifact(
            paths,
            "evaluations.partial.json",
            sorted([*skipped_existing, *completed], key=lambda item: item.get("eval_index", 0)),
        )

    for evaluation in sorted([*skipped_existing, *completed], key=lambda item: item.get("eval_index", 0)):
        node_id = evaluation["node_id"]
        evaluations.append(evaluation)
        already_recorded = evaluation.get("eval_id") in skipped_existing_ids and evaluation.get("_tree_recorded")
        if already_recorded:
            store.save_json_artifact(paths, f"evaluations/{evaluation['eval_id']}.json", evaluation)
            continue
        if evaluation.get("request_ok"):
            tree.record_result(
                node_id,
                {
                    "success": evaluation["success"],
                    "model": evaluation["model"],
                    "provider": evaluation["provider"],
                    "problem_id": evaluation["problem_id"],
                    "case_id": evaluation.get("first_failure_case_id"),
                    "note": f"{evaluation.get('num_failed')}/{evaluation.get('num_tests')} tests failed",
                },
            )
        else:
            tree.record_result(
                node_id,
                {
                    "success": False,
                    "counted": False,
                    "model": evaluation["model"],
                    "provider": evaluation["provider"],
                    "problem_id": evaluation["problem_id"],
                    "note": f"Infrastructure/model error: {evaluation.get('error', 'unknown error')}",
                },
            )
        store.save_json_artifact(paths, f"evaluations/{evaluation['eval_id']}.json", evaluation)
        store.save_tree(paths, tree)
        store.append_event(
            paths,
            "evaluation_completed",
            {k: evaluation.get(k) for k in ["eval_id", "success", "request_ok", "candidate_name", "problem_id", "model", "provider"]},
        )

    candidate_summaries = summarize_evaluations_by_candidate(evaluations)
    global_result_summary = annotate_tree_with_result_summaries(tree, node_by_candidate, candidate_summaries)
    store.save_json_artifact(paths, "candidate_result_summary.json", candidate_summaries)

    expansion_plan: dict[str, Any] = {
        "requested": args.expand_after_eval,
        "selected": 0,
        "reason": "no_counted_evaluation_results" if not candidate_summaries else "disabled",
    }
    expanded_candidates: list[dict[str, Any]] = []
    if candidate_summaries and args.expand_after_eval > 0:
        expanded_candidates, expansion_plan = result_guided_expansion_candidates(
            candidates,
            node_by_candidate,
            candidate_summaries,
            args.expand_after_eval,
        )
        meta_by_name = {item["candidate_name"]: item for item in expansion_plan.get("candidates", [])}
        for idx, candidate in enumerate(expanded_candidates, start=len(candidates)):
            spec = candidate["language_spec"]
            meta = meta_by_name.get(spec["name"], {})
            parent_id = meta.get("parent_id") or tree.root_id
            tags = [*candidate.get("tags", []), "candidate-language", "result-guided-expansion"]
            for family in meta.get("changed_families", []):
                tag = f"family:{family}"
                if tag not in tags:
                    tags.append(tag)
            node = tree.add_child(
                parent_id,
                title=candidate["title"],
                hypothesis=candidate["hypothesis"],
                tags=tags,
                artifacts={"language_spec": spec, "candidate_index": idx, "expansion_meta": meta},
                note="Result-guided diversity expansion candidate for the next loop round.",
            )
            node_by_candidate[spec["name"]] = node.id
        if expanded_candidates:
            candidates.extend(expanded_candidates)
            store.save_json_artifact(paths, "candidate_languages.json", candidates)
            store.append_event(paths, "result_guided_expansion", {"added": len(expanded_candidates), "requested": args.expand_after_eval})
    store.save_json_artifact(paths, "expansion_plan.json", expansion_plan)
    store.save_tree(paths, tree)

    reproducibility["candidate_count"] = len(candidates)
    reproducibility["candidate_hashes"] = candidate_hashes(candidates)
    reproducibility["candidate_set_hash"] = candidate_set_hash(candidates)
    reproducibility["result_guided_expansion"] = {
        "requested": args.expand_after_eval,
        "added": len(expanded_candidates),
        "candidate_names": [candidate["language_spec"]["name"] for candidate in expanded_candidates],
    }
    store.save_json_artifact(paths, "reproducibility.json", reproducibility)

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
        "resumed": args.resume,
        "designer_source": designer_info.get("source"),
        "candidate_count": len(candidates),
        "initial_candidate_count": len(candidates) - len(expanded_candidates),
        "expanded_candidate_count": len(expanded_candidates),
        "problem_count": len(problems),
        "candidate_set_hash": reproducibility["candidate_set_hash"],
        "problem_set_hash": reproducibility["problem_set_hash"],
        "requested_evaluations": len(combos),
        "skipped_existing_evaluations": len(skipped_existing),
        "completed_model_requests": sum(1 for item in evaluations if item.get("request_ok")),
        "infrastructure_errors": sum(1 for item in evaluations if not item.get("request_ok")),
        "result_summary": global_result_summary,
        "expansion_plan": expansion_plan,
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
