from __future__ import annotations

import json
from typing import Any

from .strategy_tree import StrategyTree


LANGUAGE_DESIGNER_SYSTEM = """You are the Language Designer agent.
Your job is to propose small candidate programming-language semantics that may expose LLM failure.
Keep the language executable by the provided Python JSON-AST interpreter.
Maintain a strategy tree: create, revise, pause, or extend strategy nodes based on results.
Do not overfit to many rules yet. Prefer one clear hypothesis per candidate.
Return JSON only."""

SOLVER_SYSTEM = """You are the Solver agent.
Given a candidate language spec, a JSON-AST interpreter contract, and a task, produce a JSON AST program.
Do not write free-form source code. Return JSON only."""

CURATOR_SYSTEM = """You are the Curator agent.
Read experiment results and recommend what to do with the strategy tree next.
Prefer small auditable edits: add_child, mutate_node, or record_result.
Return JSON only."""

INTERPRETER_CONTRACT = {
    "program_format": "JSON AST",
    "supported_nodes": {
        "literal": {"type": "literal", "value": "any JSON scalar/list/object"},
        "var": {"type": "var", "name": "variable name"},
        "let": {"type": "let", "name": "x", "value": "expr", "body": "expr"},
        "seq": {"type": "seq", "body": ["expr", "..."]},
        "if": {"type": "if", "cond": "expr", "then": "expr", "else": "expr"},
        "binop": {"type": "binop", "op": "+|-|*|==|<|>", "left": "expr", "right": "expr"},
    },
}


def tree_summary(tree: StrategyTree) -> dict[str, Any]:
    return tree.compact()


def language_designer_user_prompt(tree: StrategyTree, recent_results: list[dict[str, Any]] | None = None) -> str:
    payload = {
        "goal": "Find Python-near language semantics that make LLMs fail for semantic, not syntax, reasons.",
        "strategy_tree": tree_summary(tree),
        "recent_results": recent_results or [],
        "interpreter_contract": INTERPRETER_CONTRACT,
        "requested_output_schema": {
            "tree_ops": [
                {
                    "op": "add_child | mutate_node | record_result",
                    "parent_id": "for add_child",
                    "node_id": "for mutate_node/record_result",
                    "title": "short strategy title",
                    "hypothesis": "why this may induce failure",
                    "tags": ["optional"],
                    "note": "optional audit note",
                }
            ],
            "language_spec": {
                "name": "candidate language name",
                "description": "brief semantics summary",
                "semantic_rules": {
                    "truthiness": "python | inverted | zero_true | empty_true",
                    "if_semantics": "normal | inverted",
                    "comparison_semantics": "normal | inverted",
                },
            },
            "task_ideas": [
                {"task_id": "short id", "intent": "what ability this tests", "expected_failure_mode": "why LLM may miss it"}
            ],
            "rationale": "brief explanation",
        },
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def solver_user_prompt(
    language_spec: dict[str, Any],
    task: dict[str, Any],
    solver_model: dict[str, Any] | None = None,
) -> str:
    payload = {
        "language_spec": language_spec,
        "interpreter_contract": INTERPRETER_CONTRACT,
        "task": task,
        "solver_model": solver_model or {},
        "requested_output_schema": {
            "program": "JSON AST expression accepted by the interpreter",
            "notes": "brief explanation; not used for grading",
        },
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def curator_user_prompt(tree: StrategyTree, evaluation_results: list[dict[str, Any]]) -> str:
    payload = {
        "strategy_tree": tree_summary(tree),
        "evaluation_results": evaluation_results,
        "requested_output_schema": {
            "tree_ops": [
                {
                    "op": "add_child | mutate_node | record_result",
                    "parent_id": "for add_child",
                    "node_id": "for mutate_node/record_result",
                    "result": "for record_result",
                    "note": "audit note",
                }
            ],
            "summary": "what changed and why",
            "next_experiment": "one concrete next step",
        },
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)
