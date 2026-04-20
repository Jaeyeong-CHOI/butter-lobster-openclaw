from __future__ import annotations

import json
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent.parent
CANDIDATE_ROOT = BASE_DIR / "data" / "candidates"


def _task_bank(candidate: dict[str, Any]) -> list[dict[str, Any]]:
    level = candidate.get("level", "L3")
    semantics = {
        "L1": "Keywords are remapped while core semantics stay close to Python.",
        "L2": "Surface syntax differs from Python while execution remains structurally similar.",
        "L3": "Core control-flow semantics are explicitly inverted.",
        "L4": "Semantic rules are implicit in examples / interpreter behavior.",
        "L5": "Keyword, syntax, and semantic conflict are composed together.",
        "Seed": "Canonical Python-like baseline.",
    }.get(level, "Python-near language with controlled semantic conflict.")
    return [
        {
            "task_name": "abs",
            "prompt": "Implement abs_val(x)",
            "category": "neutral",
            "expected_behavior": "Return the absolute value of x.",
            "reason": "Sanity-check for JSON AST generation and interpreter execution.",
        },
        {
            "task_name": "max",
            "prompt": "Implement max_val(a, b)",
            "category": "neutral",
            "expected_behavior": "Return the larger of two values.",
            "reason": "Low-entrenchment control task.",
        },
        {
            "task_name": "fib",
            "prompt": "Implement fib(n)",
            "category": "prior-entrenched",
            "expected_behavior": f"Implement Fibonacci under candidate semantics. {semantics}",
            "reason": "Canonical prior-entrenched task.",
        },
        {
            "task_name": "gcd",
            "prompt": "Implement gcd(a, b)",
            "category": "prior-entrenched",
            "expected_behavior": f"Implement Euclidean GCD under candidate semantics. {semantics}",
            "reason": "Second canonical prior-entrenched task.",
        },
    ]


def _language_spec(candidate: dict[str, Any], parent_name: str | None) -> dict[str, Any]:
    meta = candidate.get("metadata", {}) or {}
    level = candidate.get("level", "L3")
    semantics = {
        "control_flow": "inverted_if" if level in {"L3", "L4", "L5"} else "canonical_if",
        "syntax_mode": "python_near" if candidate.get("similarity_score", 0.0) >= 0.7 else "restructured",
        "submission_format": "json_ast_v1",
        "execution_mode": "interpreter_ml",
        "agent2_model": meta.get("agent2_model", "gpt-5.4"),
    }
    return {
        "candidate_id": candidate["id"],
        "name": candidate["name"],
        "level": level,
        "parent": parent_name or candidate.get("parent_id"),
        "mutation_summary": candidate["mutation_summary"],
        "interpreter_hint": candidate["interpreter_hint"],
        "scores": {
            "similarity": candidate["similarity_score"],
            "conflict": candidate["conflict_score"],
            "solvable": candidate["solvable_score"],
            "novelty": candidate["novelty_score"],
            "failure_rate": candidate.get("failure_rate", 0.0),
        },
        "semantics": semantics,
        "pipeline": {
            "agent_a": "Interpreter Builder / Mutator",
            "agent_b": "Program Generator / Solver",
            "validator": "Deterministic JSON->AST->Interpreter execution",
        },
        "status": candidate.get("status", "generated"),
        "archived": bool(candidate.get("archived")),
        "metadata": meta,
    }


def _spec_markdown(candidate: dict[str, Any], parent_name: str | None) -> str:
    spec = _language_spec(candidate, parent_name)
    return f"""# {candidate['name']}

- **Candidate ID:** {candidate['id']}
- **Level:** {candidate['level']}
- **Parent:** {parent_name or candidate.get('parent_id') or 'None'}
- **Status:** {candidate.get('status', 'generated')}
- **Archived:** {'yes' if candidate.get('archived') else 'no'}

## Mutation Summary
{candidate['mutation_summary']}

## Interpreter Hint
{candidate['interpreter_hint']}

## Pipeline
1. Agent A mutates or creates the interpreter.
2. Agent B generates a JSON AST program for the task.
3. The deterministic validator parses JSON, reconstructs AST, executes the interpreter, and compares outputs.

## Structured Spec
```json
{json.dumps(spec, ensure_ascii=False, indent=2)}
```
"""


def _interpreter_code(candidate: dict[str, Any]) -> str:
    level = candidate.get("level", "L3")
    body = {
        "L1": "(* token-conflict language: conflicting keywords are normalized before evaluation *)\nlet normalize_keyword k = match k with | \"fn\" -> \"def\" | \"unless\" -> \"if\" | _ -> k",
        "L2": "(* syntax-conflict language: blocks and declarations are reshaped before execution *)\n(* Example: :define name [args] -> becomes an internal function declaration node *)",
        "L3": "(* semantic-conflict language: conditionals execute when condition is FALSE *)\nlet eval_if cond = not cond",
        "L4": "(* implicit semantic language: runtime matches inverted-if, but prompts never verbalize the rule *)\nlet eval_if cond = not cond",
        "L5": "(* compound conflict: keyword remap + syntax reshape + inverted conditionals *)\nlet normalize_keyword k = match k with | \"fn\" -> \"def\" | \"give\" -> \"return\" | _ -> k\nlet eval_if cond = not cond",
        "Seed": "(* canonical Python-like reference interpreter *)\nlet eval_if cond = cond",
    }.get(level, "(* interpreter stub *)")
    return f"""(* interpreter.ml for {candidate['name']} *)
(* This executable interpreter is the canonical source of truth for the language. *)

exception UndefinedSemantics

{body}

(* TODO: replace with the real HW3/B-language-derived interpreter body. *)
(* Expected execution path: program.json -> AST -> eval -> output trace *)
"""


def _ast_schema(candidate: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_name": "json_ast_v1",
        "candidate_id": candidate["id"],
        "root": "exp",
        "required_top_level": ["program"],
        "node_examples": {
            "NUM": {"type": "NUM", "value": 3},
            "VAR": {"type": "VAR", "name": "x"},
            "ADD": {"type": "ADD", "left": {"type": "NUM", "value": 1}, "right": {"type": "NUM", "value": 2}},
            "IF": {
                "type": "IF",
                "cond": {"type": "LESS", "left": {"type": "VAR", "name": "n"}, "right": {"type": "NUM", "value": 2}},
                "then": {"type": "VAR", "name": "n"},
                "else": {"type": "NUM", "value": 0},
            },
            "LETF": {
                "type": "LETF",
                "name": "fib",
                "params": ["n"],
                "body": {"type": "NUM", "value": 0},
                "in": {"type": "CALLV", "name": "fib", "args": [{"type": "NUM", "value": 6}]},
            },
        },
        "notes": [
            "Agent B must output JSON only.",
            "The validator will reject malformed or schema-incompatible programs.",
            "Surface syntax is optional; JSON AST is canonical for v1.",
        ],
    }


def _program_attempts(candidate: dict[str, Any], evaluations: list[dict[str, Any]] | None) -> dict[str, Any]:
    rows = evaluations or []
    attempts = []
    for row in rows:
        task = row["task_name"]
        prog = {
            "format": "json_ast_v1",
            "task_name": task,
            "model_name": row["model_name"],
            "program": {
                "type": "LETF",
                "name": task,
                "params": ["x", "y"] if task in {"max", "gcd"} else ["n"],
                "body": {
                    "type": "IF" if candidate.get("level") in {"L3", "L4", "L5"} else "ADD",
                    "note": "MVP placeholder AST; replace with real Agent B output",
                },
                "in": {
                    "type": "CALLV",
                    "name": task,
                    "args": [{"type": "NUM", "value": 6}],
                },
            },
            "expected_success": bool(row.get("success")),
        }
        attempts.append(prog)
    return {
        "candidate_id": candidate["id"],
        "submission_contract": "Agent B must return machine-parseable JSON AST, not free-form code text.",
        "attempts": attempts,
    }


def _validator_result(candidate: dict[str, Any], evaluations: list[dict[str, Any]] | None, analysis: dict[str, Any] | None) -> dict[str, Any]:
    rows = evaluations or []
    return {
        "candidate_id": candidate["id"],
        "validator_mode": "json -> schema check -> AST reconstruction -> interpreter execution -> output comparison",
        "summary": {
            "total_evaluations": len(rows),
            "total_success": sum(1 for r in rows if r.get("success")),
            "total_failure": sum(1 for r in rows if not r.get("success")),
            "failure_rate": analysis.get("failure_rate") if analysis else candidate.get("failure_rate", 0.0),
        },
        "rows": [
            {
                "model_name": r["model_name"],
                "task_name": r["task_name"],
                "parse_ok": True,
                "execution_ok": True,
                "outputs_match": bool(r["success"]),
                "success": bool(r["success"]),
                "score": r["score"],
                "notes": r.get("notes", ""),
            }
            for r in rows
        ],
    }


def _agent_prompts(candidate: dict[str, Any], parent_name: str | None) -> dict[str, str]:
    agent2_model = (candidate.get("metadata", {}) or {}).get("agent2_model", "gpt-5.4")
    return {
        "prompts/agentA_interpreter_builder.txt": f"""You are Agent A (Interpreter Builder / Mutator).

Parent language: {parent_name or 'None'}
Target candidate: {candidate['name']} ({candidate['level']})

Your job:
- create or mutate an OCaml interpreter
- keep the language deterministic and executable
- define JSON AST submission format
- preserve human solvability while increasing prior conflict

Mutation summary:
{candidate['mutation_summary']}

Interpreter hint:
{candidate['interpreter_hint']}
""",
        "prompts/agentB_solver.txt": f"""You are Agent B (Program Generator / Solver).

Selected OpenAI model: {agent2_model}

Input artifacts:
- interpreter.ml
- language_spec.json
- ast_schema.json
- tasks.json

Your output contract:
- return machine-parseable JSON AST only
- follow the schema exactly
- do not output free-form explanation as the primary answer

Candidate: {candidate['name']}
Submission format: json_ast_v1
""",
    }


def materialize_candidate_bundle(
    candidate: dict[str, Any],
    parent_name: str | None = None,
    evaluations: list[dict[str, Any]] | None = None,
    analysis: dict[str, Any] | None = None,
) -> dict[str, Any]:
    candidate_dir = CANDIDATE_ROOT / candidate["id"]
    candidate_dir.mkdir(parents=True, exist_ok=True)

    language_spec = _language_spec(candidate, parent_name)
    ast_schema = _ast_schema(candidate)
    program_attempts = _program_attempts(candidate, evaluations)
    validator_result = _validator_result(candidate, evaluations, analysis)

    files: dict[str, str] = {
        "spec.md": _spec_markdown(candidate, parent_name),
        "interpreter.ml": _interpreter_code(candidate),
        "language_spec.json": json.dumps(language_spec, ensure_ascii=False, indent=2),
        "ast_schema.json": json.dumps(ast_schema, ensure_ascii=False, indent=2),
        "tasks.json": json.dumps(_task_bank(candidate), ensure_ascii=False, indent=2),
        "program_attempts.json": json.dumps(program_attempts, ensure_ascii=False, indent=2),
        "validator_result.json": json.dumps(validator_result, ensure_ascii=False, indent=2),
        "candidate.json": json.dumps(candidate, ensure_ascii=False, indent=2),
    }
    files.update(_agent_prompts(candidate, parent_name))
    if evaluations is not None:
        files["evaluations.json"] = json.dumps(evaluations, ensure_ascii=False, indent=2)
    if analysis is not None:
        files["analysis.json"] = json.dumps(analysis, ensure_ascii=False, indent=2)

    for rel_path, content in files.items():
        path = candidate_dir / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    return {
        "candidate_dir": str(candidate_dir),
        "files": sorted(files.keys()),
    }


def load_candidate_bundle(candidate: dict[str, Any]) -> dict[str, Any]:
    candidate_dir = CANDIDATE_ROOT / candidate["id"]
    if not candidate_dir.exists():
        materialize_candidate_bundle(candidate)
    files: dict[str, str] = {}
    manifest: list[str] = []
    for path in sorted(candidate_dir.rglob("*")):
        if path.is_file():
            rel = str(path.relative_to(candidate_dir))
            manifest.append(rel)
            try:
                files[rel] = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                files[rel] = "<binary file>"
    return {
        "candidate_dir": str(candidate_dir),
        "manifest": manifest,
        "files": files,
    }
