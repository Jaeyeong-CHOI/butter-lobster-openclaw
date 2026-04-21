from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent.parent
CANDIDATE_ROOT = BASE_DIR / "data" / "candidates"


def _task_bank(candidate: dict[str, Any]) -> list[dict[str, Any]]:
    family = ((candidate.get("metadata", {}) or {}).get("strategy_family") or candidate.get("level") or "semantic_conflict")
    semantics = {
        "token_conflict": "Keywords are remapped while core semantics stay close to Python.",
        "syntax_conflict": "Surface syntax differs from Python while execution remains structurally similar.",
        "semantic_conflict": "Core control-flow semantics are explicitly inverted.",
        "implicit_semantic_conflict": "Semantic rules are implicit in examples / interpreter behavior.",
        "compound_conflict": "Keyword, syntax, and semantic conflict are composed together.",
    }.get(family, "Python-near language with controlled semantic conflict.")
    return [
        {
            "task_name": "abs",
            "entry_name": "abs_val",
            "params": ["x"],
            "prompt": "Implement abs_val(x)",
            "category": "neutral",
            "expected_behavior": "Return the absolute value of x.",
            "reason": "Sanity-check for JSON AST generation and interpreter execution.",
            "tests": [
                {"args": [-3], "expected": 3},
                {"args": [0], "expected": 0},
                {"args": [5], "expected": 5},
            ],
        },
        {
            "task_name": "max",
            "entry_name": "max_val",
            "params": ["a", "b"],
            "prompt": "Implement max_val(a, b)",
            "category": "neutral",
            "expected_behavior": "Return the larger of two values.",
            "reason": "Low-entrenchment control task.",
            "tests": [
                {"args": [3, 5], "expected": 5},
                {"args": [9, 2], "expected": 9},
                {"args": [4, 4], "expected": 4},
            ],
        },
        {
            "task_name": "fib",
            "entry_name": "fib",
            "params": ["n"],
            "prompt": "Implement fib(n)",
            "category": "prior-entrenched",
            "expected_behavior": f"Implement Fibonacci under candidate semantics. {semantics}",
            "reason": "Canonical prior-entrenched task.",
            "tests": [
                {"args": [0], "expected": 0},
                {"args": [1], "expected": 1},
                {"args": [6], "expected": 8},
            ],
        },
        {
            "task_name": "gcd",
            "entry_name": "gcd",
            "params": ["a", "b"],
            "prompt": "Implement gcd(a, b)",
            "category": "prior-entrenched",
            "expected_behavior": f"Implement Euclidean GCD under candidate semantics. {semantics}",
            "reason": "Second canonical prior-entrenched task.",
            "tests": [
                {"args": [12, 8], "expected": 4},
                {"args": [9, 6], "expected": 3},
                {"args": [7, 7], "expected": 7},
            ],
        },
    ]


INVERTED_IF_FAMILIES = {"semantic_conflict", "implicit_semantic_conflict", "compound_conflict"}


def _num(n: int) -> dict[str, Any]:
    return {"type": "NUM", "value": n}


def _bool(value: bool) -> dict[str, Any]:
    return {"type": "BOOL", "value": value}


def _var(name: str) -> dict[str, Any]:
    return {"type": "VAR", "name": name}


def _call(name: str, args: list[dict[str, Any]]) -> dict[str, Any]:
    return {"type": "CALLV", "name": name, "args": args}


def _binary(op: str, left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    return {"type": op, "left": left, "right": right}


def _if_expr(family: str, cond: dict[str, Any], then_expr: dict[str, Any], else_expr: dict[str, Any]) -> dict[str, Any]:
    if family in INVERTED_IF_FAMILIES:
        return {"type": "IF", "cond": cond, "then": else_expr, "else": then_expr}
    return {"type": "IF", "cond": cond, "then": then_expr, "else": else_expr}


def _task_body(task_name: str, family: str, success: bool) -> tuple[str, list[str], dict[str, Any]]:
    if task_name == "abs":
        if success:
            body = _if_expr(family, _binary("LESS", _var("x"), _num(0)), _binary("SUB", _num(0), _var("x")), _var("x"))
        else:
            body = _var("x")
        return "abs_val", ["x"], body

    if task_name == "max":
        if success:
            body = _if_expr(family, _binary("LESS", _var("a"), _var("b")), _var("b"), _var("a"))
        else:
            body = _var("a")
        return "max_val", ["a", "b"], body

    if task_name == "fib":
        if success:
            body = _if_expr(
                family,
                _binary("LESS", _var("n"), _num(2)),
                _var("n"),
                _binary(
                    "ADD",
                    _call("fib", [_binary("SUB", _var("n"), _num(1))]),
                    _call("fib", [_binary("SUB", _var("n"), _num(2))]),
                ),
            )
        else:
            body = _var("n")
        return "fib", ["n"], body

    if task_name == "gcd":
        if success:
            body = _if_expr(
                family,
                _binary("EQUAL", _var("a"), _var("b")),
                _var("a"),
                _if_expr(
                    family,
                    _binary("LESS", _var("a"), _var("b")),
                    _call("gcd", [_var("a"), _binary("SUB", _var("b"), _var("a"))]),
                    _call("gcd", [_binary("SUB", _var("a"), _var("b")), _var("b")]),
                ),
            )
        else:
            body = _var("a")
        return "gcd", ["a", "b"], body

    raise ValueError(f"Unknown task: {task_name}")


def _build_task_program(candidate: dict[str, Any], task: dict[str, Any], success: bool) -> dict[str, Any]:
    family = ((candidate.get("metadata", {}) or {}).get("strategy_family") or candidate.get("level") or "semantic_conflict")
    entry_name, params, body = _task_body(task["task_name"], family, success)
    first_case_args = task.get("tests", [{"args": []}])[0]["args"]
    return {
        "type": "LETF",
        "name": entry_name,
        "params": params,
        "body": body,
        "in": _call(entry_name, [_num(arg) for arg in first_case_args]),
    }


def _validate_json_ast(node: Any, path: str = "program") -> list[str]:
    if not isinstance(node, dict):
        return [f"{path}: node must be an object"]
    node_type = node.get("type")
    if not isinstance(node_type, str):
        return [f"{path}: missing string field 'type'"]

    errors: list[str] = []
    if node_type == "NUM":
        if not isinstance(node.get("value"), int):
            errors.append(f"{path}: NUM.value must be an integer")
    elif node_type == "BOOL":
        if not isinstance(node.get("value"), bool):
            errors.append(f"{path}: BOOL.value must be a boolean")
    elif node_type == "VAR":
        if not isinstance(node.get("name"), str):
            errors.append(f"{path}: VAR.name must be a string")
    elif node_type in {"ADD", "SUB", "MUL", "DIV", "LESS", "EQUAL"}:
        errors.extend(_validate_json_ast(node.get("left"), f"{path}.left"))
        errors.extend(_validate_json_ast(node.get("right"), f"{path}.right"))
    elif node_type == "IF":
        errors.extend(_validate_json_ast(node.get("cond"), f"{path}.cond"))
        errors.extend(_validate_json_ast(node.get("then"), f"{path}.then"))
        errors.extend(_validate_json_ast(node.get("else"), f"{path}.else"))
    elif node_type == "LET":
        if not isinstance(node.get("name"), str):
            errors.append(f"{path}: LET.name must be a string")
        errors.extend(_validate_json_ast(node.get("value"), f"{path}.value"))
        errors.extend(_validate_json_ast(node.get("body"), f"{path}.body"))
    elif node_type == "WRITE":
        errors.extend(_validate_json_ast(node.get("expr"), f"{path}.expr"))
    elif node_type == "LETF":
        if not isinstance(node.get("name"), str):
            errors.append(f"{path}: LETF.name must be a string")
        params = node.get("params")
        if not isinstance(params, list) or not all(isinstance(p, str) for p in params):
            errors.append(f"{path}: LETF.params must be a list of strings")
        errors.extend(_validate_json_ast(node.get("body"), f"{path}.body"))
        errors.extend(_validate_json_ast(node.get("in"), f"{path}.in"))
    elif node_type == "CALLV":
        if not isinstance(node.get("name"), str):
            errors.append(f"{path}: CALLV.name must be a string")
        args = node.get("args")
        if not isinstance(args, list):
            errors.append(f"{path}: CALLV.args must be a list")
        else:
            for i, arg in enumerate(args):
                errors.extend(_validate_json_ast(arg, f"{path}.args[{i}]"))
    else:
        errors.append(f"{path}: unsupported node type '{node_type}'")
    return errors


def _ocaml_string(value: str) -> str:
    return json.dumps(value)


def _json_ast_to_ocaml(node: dict[str, Any]) -> str:
    node_type = node["type"]
    if node_type == "NUM":
        value = int(node["value"])
        return f"NUM ({value})" if value < 0 else f"NUM {value}"
    if node_type == "BOOL":
        return "BOOL true" if node["value"] else "BOOL false"
    if node_type == "VAR":
        return f"VAR {_ocaml_string(node['name'])}"
    if node_type in {"ADD", "SUB", "MUL", "DIV", "LESS", "EQUAL"}:
        return f"{node_type} ({_json_ast_to_ocaml(node['left'])}, {_json_ast_to_ocaml(node['right'])})"
    if node_type == "IF":
        return f"IF ({_json_ast_to_ocaml(node['cond'])}, {_json_ast_to_ocaml(node['then'])}, {_json_ast_to_ocaml(node['else'])})"
    if node_type == "LET":
        return f"LET ({_ocaml_string(node['name'])}, {_json_ast_to_ocaml(node['value'])}, {_json_ast_to_ocaml(node['body'])})"
    if node_type == "WRITE":
        return f"WRITE ({_json_ast_to_ocaml(node['expr'])})"
    if node_type == "LETF":
        params = "; ".join(_ocaml_string(param) for param in node["params"])
        return (
            f"LETF ({_ocaml_string(node['name'])}, [{params}], "
            f"{_json_ast_to_ocaml(node['body'])}, {_json_ast_to_ocaml(node['in'])})"
        )
    if node_type == "CALLV":
        args = "; ".join(_json_ast_to_ocaml(arg) for arg in node.get("args", []))
        return f"CALLV ({_ocaml_string(node['name'])}, [{args}])"
    raise ValueError(f"Unsupported node type: {node_type}")


def _program_with_args(program: dict[str, Any], entry_name: str, args: list[int]) -> dict[str, Any]:
    if program.get("type") == "LETF":
        return {
            **program,
            "in": _call(entry_name, [_num(int(arg)) for arg in args]),
        }
    return program


def _execute_ocaml_cases(interpreter_source: str, case_programs: list[dict[str, Any]]) -> dict[str, Any]:
    ocaml_bin = shutil.which("ocaml")
    if not ocaml_bin:
        return {
            "execution_ok": False,
            "notes": "ocaml runtime not found",
            "cases": [],
        }

    case_lines = []
    for index, case in enumerate(case_programs, start=1):
        expr = _json_ast_to_ocaml(case["program"])
        case_lines.append(
            f"  (\"case_{index}\", {expr}, {int(case['expected'])});"
        )

    driver = f"""
{interpreter_source}

let validator_cases = [
{chr(10).join(case_lines)}
]

let () =
  List.iter
    (fun (label, program, expected) ->
      let result = runb program in
      Printf.printf "__CASE__=%s|%d|%d\\n" label result expected)
    validator_cases
"""

    with tempfile.NamedTemporaryFile("w", suffix=".ml", delete=False, encoding="utf-8") as tmp:
        tmp.write(driver)
        tmp_path = Path(tmp.name)

    try:
        proc = subprocess.run(
            [ocaml_bin, str(tmp_path)],
            capture_output=True,
            text=True,
            timeout=8,
        )
    except subprocess.TimeoutExpired:
        tmp_path.unlink(missing_ok=True)
        return {"execution_ok": False, "notes": "ocaml execution timed out", "cases": []}
    finally:
        tmp_path.unlink(missing_ok=True)

    if proc.returncode != 0:
        return {
            "execution_ok": False,
            "notes": (proc.stderr or proc.stdout or "ocaml execution failed").strip(),
            "cases": [],
        }

    case_results = []
    for line in proc.stdout.splitlines():
        if not line.startswith("__CASE__="):
            continue
        _, payload = line.split("=", 1)
        label, actual, expected = payload.split("|", 2)
        case_results.append(
            {
                "label": label,
                "actual": int(actual),
                "expected": int(expected),
                "match": int(actual) == int(expected),
            }
        )

    return {
        "execution_ok": True,
        "notes": "",
        "cases": case_results,
        "stdout": [line for line in proc.stdout.splitlines() if not line.startswith("__CASE__=")],
    }


def _strategy_tree(candidate: dict[str, Any], parent_name: str | None) -> dict[str, Any]:
    meta = candidate.get("metadata", {}) or {}
    selected_family = meta.get("strategy_family", "semantic_conflict")
    selected_leaf = meta.get("strategy_leaf", "inverted_if")

    def fam_status(fam_id: str) -> str:
        return "selected" if fam_id == selected_family else "explored"

    def leaf_status(leaf_id: str) -> str:
        return "selected" if leaf_id == selected_leaf else "candidate"

    return {
        "candidate_id": candidate["id"],
        "tree_name": f"Strategy search for {candidate['name']}",
        "selected_path": ["root", selected_family, selected_leaf],
        "nodes": {
            "root": {
                "label": "Python-near hardest-language search",
                "kind": "root",
                "status": "active",
                "note": f"Parent = {parent_name or candidate.get('parent_id') or 'None'}",
            },
            "baseline_python_near": {
                "label": "Baseline / Python-near",
                "kind": "family",
                "status": fam_status("baseline_python_near"),
            },
            "token_conflict": {
                "label": "Token conflict family",
                "kind": "family",
                "status": fam_status("token_conflict"),
            },
            "syntax_conflict": {
                "label": "Syntax conflict family",
                "kind": "family",
                "status": fam_status("syntax_conflict"),
            },
            "semantic_conflict": {
                "label": "Explicit semantic conflict family",
                "kind": "family",
                "status": fam_status("semantic_conflict"),
            },
            "implicit_semantic_conflict": {
                "label": "Implicit semantic conflict family",
                "kind": "family",
                "status": fam_status("implicit_semantic_conflict"),
            },
            "compound_conflict": {
                "label": "Compound conflict family",
                "kind": "family",
                "status": fam_status("compound_conflict"),
            },
            "baseline_reference": {
                "label": "Reference interpreter",
                "kind": "strategy",
                "status": leaf_status("baseline_reference"),
                "score": round(candidate.get("similarity_score", 0.0), 3),
            },
            "cross_keyword_swap": {
                "label": "Cross-keyword swap",
                "kind": "strategy",
                "status": leaf_status("cross_keyword_swap"),
                "score": round(candidate.get("conflict_score", 0.0), 3),
            },
            "block_syntax_inversion": {
                "label": "Block syntax inversion",
                "kind": "strategy",
                "status": leaf_status("block_syntax_inversion"),
                "score": round(candidate.get("conflict_score", 0.0), 3),
            },
            "inverted_if": {
                "label": "Invert IF semantics",
                "kind": "strategy",
                "status": leaf_status("inverted_if"),
                "score": round(candidate.get("failure_rate", 0.0), 3),
            },
            "example_only_rule_induction": {
                "label": "Example-only rule induction",
                "kind": "strategy",
                "status": leaf_status("example_only_rule_induction"),
                "score": round(candidate.get("failure_rate", 0.0), 3),
            },
            "keyword_plus_syntax_plus_semantics": {
                "label": "Keyword + syntax + semantics bundle",
                "kind": "strategy",
                "status": leaf_status("keyword_plus_syntax_plus_semantics"),
                "score": round(candidate.get("failure_rate", 0.0), 3),
            },
        },
        "edges": [
            ["root", "baseline_python_near"],
            ["root", "token_conflict"],
            ["root", "syntax_conflict"],
            ["root", "semantic_conflict"],
            ["root", "implicit_semantic_conflict"],
            ["root", "compound_conflict"],
            ["baseline_python_near", "baseline_reference"],
            ["token_conflict", "cross_keyword_swap"],
            ["syntax_conflict", "block_syntax_inversion"],
            ["semantic_conflict", "inverted_if"],
            ["implicit_semantic_conflict", "example_only_rule_induction"],
            ["compound_conflict", "keyword_plus_syntax_plus_semantics"],
        ],
    }


def _agent_graph(candidate: dict[str, Any]) -> dict[str, Any]:
    archived = bool(candidate.get("archived"))
    return {
        "candidate_id": candidate["id"],
        "nodes": [
            {"id": "strategy_root", "label": "Strategy Root", "kind": "strategy", "x": 70, "y": 110, "status": "active"},
            {"id": "agent_a", "label": "Agent A\nInterpreter Builder", "kind": "agent", "x": 260, "y": 110, "status": "active"},
            {"id": "interpreter", "label": "interpreter.ml", "kind": "artifact", "x": 470, "y": 50, "status": "ready"},
            {"id": "schema", "label": "ast_schema.json", "kind": "artifact", "x": 470, "y": 170, "status": "ready"},
            {"id": "tasks", "label": "tasks.json", "kind": "artifact", "x": 470, "y": 290, "status": "ready"},
            {"id": "agent_b", "label": "Agent B\nProgram Solver", "kind": "agent", "x": 700, "y": 110, "status": "active"},
            {"id": "program", "label": "program_attempts.json", "kind": "artifact", "x": 900, "y": 110, "status": "ready"},
            {"id": "validator", "label": "Validator\nJSON → AST → Execute", "kind": "agent", "x": 1110, "y": 110, "status": "active"},
            {"id": "result", "label": "validator_result.json", "kind": "artifact", "x": 1330, "y": 110, "status": "archived" if archived else "scored"},
        ],
        "edges": [
            {"id": "e1", "source": "strategy_root", "target": "agent_a", "label": "selected strategy", "exchange": "mutation family + chosen branch", "inspect": "strategy"},
            {"id": "e2", "source": "agent_a", "target": "interpreter", "label": "emit interpreter", "exchange": "OCaml interpreter definition", "inspect": "interpreter.ml"},
            {"id": "e3", "source": "agent_a", "target": "schema", "label": "emit schema", "exchange": "JSON AST contract", "inspect": "ast_schema.json"},
            {"id": "e4", "source": "agent_a", "target": "tasks", "label": "emit tasks", "exchange": "task bank + expected outputs", "inspect": "tasks.json"},
            {"id": "e5", "source": "interpreter", "target": "agent_b", "label": "language semantics", "exchange": "canonical executable language spec", "inspect": "prompts/agentB_solver.txt"},
            {"id": "e6", "source": "schema", "target": "agent_b", "label": "AST contract", "exchange": "required JSON structure", "inspect": "ast_schema.json"},
            {"id": "e7", "source": "tasks", "target": "agent_b", "label": "task prompt", "exchange": "task targets and expected behavior", "inspect": "tasks.json"},
            {"id": "e8", "source": "agent_b", "target": "program", "label": "submit JSON AST", "exchange": "program.json / attempt bundle", "inspect": "program_attempts.json"},
            {"id": "e9", "source": "program", "target": "validator", "label": "candidate program", "exchange": "machine-parseable JSON AST", "inspect": "program_attempts.json"},
            {"id": "e10", "source": "interpreter", "target": "validator", "label": "execution engine", "exchange": "runtime semantics for execution", "inspect": "interpreter.ml"},
            {"id": "e11", "source": "validator", "target": "result", "label": "execution verdict", "exchange": "parse/execution/output-match results", "inspect": "validator_result.json"},
        ],
    }


def _language_spec(candidate: dict[str, Any], parent_name: str | None) -> dict[str, Any]:
    meta = candidate.get("metadata", {}) or {}
    family = meta.get("strategy_family", candidate.get("level", "semantic_conflict"))
    agent_a_settings = meta.get(
        "agent_a_settings",
        {
            "model": meta.get("agent_a_model", "gpt-5.4"),
            "temperature": meta.get("agent_a_temperature", 0.7),
            "thinking": meta.get("agent_a_thinking", "high"),
        },
    )
    solver_settings = meta.get(
        "solver_settings",
        meta.get(
            "agent_b_settings",
            {
                "enabled_models": [meta.get("agent_b_model", "gpt-5.4")],
                "temperature": meta.get("agent_b_temperature", 0.2),
                "thinking": meta.get("agent_b_thinking", "medium"),
                "repeat_count": 1,
                "parallelism": 1,
                "provider": "openai",
            },
        ),
    )
    semantics = {
        "control_flow": "inverted_if" if family in INVERTED_IF_FAMILIES else "canonical_if",
        "strategy_family": family,
        "strategy_leaf": meta.get("strategy_leaf"),
        "syntax_mode": "python_near" if candidate.get("similarity_score", 0.0) >= 0.7 else "restructured",
        "submission_format": "json_ast_v1",
        "execution_mode": "interpreter_ml",
    }
    return {
        "candidate_id": candidate["id"],
        "name": candidate["name"],
        "strategy_family": family,
        "strategy_leaf": meta.get("strategy_leaf"),
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
            "agent_b": "Solver bench across enabled models",
            "validator": "Deterministic JSON->AST->Interpreter execution",
        },
        "agent_settings": {
            "agent_a": agent_a_settings,
            "solver_bench": solver_settings,
        },
        "status": candidate.get("status", "generated"),
        "archived": bool(candidate.get("archived")),
        "metadata": meta,
    }


def _spec_markdown(candidate: dict[str, Any], parent_name: str | None) -> str:
    spec = _language_spec(candidate, parent_name)
    return f"""# {candidate['name']}

- **Candidate ID:** {candidate['id']}
- **Strategy family:** {candidate.get('metadata', {}).get('strategy_family', candidate.get('level'))}
- **Strategy leaf:** {candidate.get('metadata', {}).get('strategy_leaf', 'n/a')}
- **Parent:** {parent_name or candidate.get('parent_id') or 'None'}
- **Status:** {candidate.get('status', 'generated')}
- **Archived:** {'yes' if candidate.get('archived') else 'no'}

## Mutation Summary
{candidate['mutation_summary']}

## Interpreter Hint
{candidate['interpreter_hint']}

## Pipeline
1. Strategy tree selects a mutation family and strategy branch.
2. Agent A mutates or creates the interpreter.
3. Agent B generates a JSON AST program for the task.
4. The deterministic validator parses JSON, reconstructs AST, executes the interpreter, and compares outputs.

## Structured Spec
```json
{json.dumps(spec, ensure_ascii=False, indent=2)}
```
"""


def _interpreter_code(candidate: dict[str, Any]) -> str:
    family = ((candidate.get("metadata", {}) or {}).get("strategy_family") or candidate.get("level") or "semantic_conflict")
    semantics = {
        "token_conflict": {
            "comment": "(* token-conflict language: conflicting surface keywords are normalized before function lookup *)",
            "keyword_rule": "let normalize_keyword k = match k with | \"fn\" -> \"def\" | \"unless\" -> \"if\" | _ -> k",
            "if_rule": "let eval_if cond = cond",
        },
        "syntax_conflict": {
            "comment": "(* syntax-conflict language: surface syntax is assumed to be normalized into the AST before evaluation *)",
            "keyword_rule": "let normalize_keyword k = k",
            "if_rule": "let eval_if cond = cond",
        },
        "semantic_conflict": {
            "comment": "(* semantic-conflict language: IF executes its then-branch when the condition evaluates to FALSE *)",
            "keyword_rule": "let normalize_keyword k = k",
            "if_rule": "let eval_if cond = not cond",
        },
        "implicit_semantic_conflict": {
            "comment": "(* implicit semantic language: the runtime inverts IF, but the rule is meant to be inferred from behavior/examples *)",
            "keyword_rule": "let normalize_keyword k = k",
            "if_rule": "let eval_if cond = not cond",
        },
        "compound_conflict": {
            "comment": "(* compound conflict language: keyword remap + inverted IF semantics are both active in the runtime *)",
            "keyword_rule": "let normalize_keyword k = match k with | \"fn\" -> \"def\" | \"give\" -> \"return\" | _ -> k",
            "if_rule": "let eval_if cond = not cond",
        },
    }.get(
        family,
        {
            "comment": "(* default interpreter semantics *)",
            "keyword_rule": "let normalize_keyword k = k",
            "if_rule": "let eval_if cond = cond",
        },
    )

    template = """(* interpreter.ml for __NAME__ *)
(* Directly executable OCaml interpreter artifact. *)
(* Run with: ocaml interpreter.ml *)

exception UndefinedSemantics

type id = string

type exp =
  | NUM of int
  | BOOL of bool
  | VAR of id
  | ADD of exp * exp
  | SUB of exp * exp
  | MUL of exp * exp
  | DIV of exp * exp
  | LESS of exp * exp
  | EQUAL of exp * exp
  | IF of exp * exp * exp
  | LET of id * exp * exp
  | WRITE of exp
  | LETF of id * id list * exp * exp
  | CALLV of id * exp list

type value =
  | Int of int
  | Bool of bool

type env = (id * value) list

type proc = {
  params : id list;
  body : exp;
  penv : env;
  pfenv : fenv;
}

and fenv = (id * proc) list

__SEMANTICS_COMMENT__
__KEYWORD_RULE__
__IF_RULE__

let string_of_value = function
  | Int n -> string_of_int n
  | Bool b -> string_of_bool b

let as_int = function
  | Int n -> n
  | Bool _ -> raise UndefinedSemantics

let as_bool = function
  | Bool b -> b
  | Int n -> n <> 0

let rec lookup x env =
  match env with
  | [] -> raise UndefinedSemantics
  | (y, v) :: rest -> if x = y then v else lookup x rest

let rec lookup_fun f fenv =
  match fenv with
  | [] -> raise UndefinedSemantics
  | (g, p) :: rest -> if f = g then p else lookup_fun f rest

let bind_params params values base_env =
  let rec aux ps vs acc =
    match ps, vs with
    | [], [] -> acc
    | p :: ps', v :: vs' -> aux ps' vs' ((p, v) :: acc)
    | _ -> raise UndefinedSemantics
  in
  aux params values base_env

let rec eval (fenv : fenv) (env : env) (e : exp) : value =
  match e with
  | NUM n -> Int n
  | BOOL b -> Bool b
  | VAR x -> lookup x env
  | ADD (l, r) -> Int (as_int (eval fenv env l) + as_int (eval fenv env r))
  | SUB (l, r) -> Int (as_int (eval fenv env l) - as_int (eval fenv env r))
  | MUL (l, r) -> Int (as_int (eval fenv env l) * as_int (eval fenv env r))
  | DIV (l, r) ->
      let denom = as_int (eval fenv env r) in
      if denom = 0 then raise UndefinedSemantics
      else Int (as_int (eval fenv env l) / denom)
  | LESS (l, r) -> Bool (as_int (eval fenv env l) < as_int (eval fenv env r))
  | EQUAL (l, r) -> Bool (eval fenv env l = eval fenv env r)
  | IF (cond, then_e, else_e) ->
      if eval_if (as_bool (eval fenv env cond))
      then eval fenv env then_e
      else eval fenv env else_e
  | LET (name, rhs, body) ->
      let value = eval fenv env rhs in
      eval fenv ((name, value) :: env) body
  | WRITE expr ->
      let value = eval fenv env expr in
      print_endline (string_of_value value);
      value
  | LETF (name, params, fn_body, in_exp) ->
      let normalized_name = normalize_keyword name in
      let rec proc = {
        params = params;
        body = fn_body;
        penv = env;
        pfenv = next_fenv;
      }
      and next_fenv = (normalized_name, proc) :: fenv in
      eval next_fenv env in_exp
  | CALLV (name, args) ->
      let normalized_name = normalize_keyword name in
      let proc = lookup_fun normalized_name fenv in
      let arg_values = List.map (eval fenv env) args in
      let call_env = bind_params proc.params arg_values proc.penv in
      eval proc.pfenv call_env proc.body

let run e = eval [] [] e

let runb e =
  match run e with
  | Int n -> n
  | Bool b -> if b then 1 else 0

let sample_program =
  WRITE (
    LETF (
      "abs_val",
      ["x"],
      IF (
        LESS (VAR "x", NUM 0),
        SUB (NUM 0, VAR "x"),
        VAR "x"
      ),
      CALLV ("abs_val", [NUM (-3)])
    )
  )

let () =
  if not !Sys.interactive && Sys.getenv_opt "HLL_RUN_SAMPLE" = Some "1" then (
    let result = run sample_program in
    Printf.printf "sample_result=%s\n" (string_of_value result)
  )
"""

    return (
        template.replace("__NAME__", candidate["name"])
        .replace("__SEMANTICS_COMMENT__", semantics["comment"])
        .replace("__KEYWORD_RULE__", semantics["keyword_rule"])
        .replace("__IF_RULE__", semantics["if_rule"])
    )


def _ast_schema(candidate: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_name": "json_ast_v1",
        "candidate_id": candidate["id"],
        "root": "exp",
        "required_top_level": ["program"],
        "node_examples": {
            "NUM": {"type": "NUM", "value": 3},
            "BOOL": {"type": "BOOL", "value": True},
            "VAR": {"type": "VAR", "name": "x"},
            "ADD": {"type": "ADD", "left": {"type": "NUM", "value": 1}, "right": {"type": "NUM", "value": 2}},
            "WRITE": {"type": "WRITE", "expr": {"type": "NUM", "value": 3}},
            "IF": {
                "type": "IF",
                "cond": {"type": "LESS", "left": {"type": "VAR", "name": "n"}, "right": {"type": "NUM", "value": 2}},
                "then": {"type": "VAR", "name": "n"},
                "else": {"type": "NUM", "value": 0},
            },
            "LET": {
                "type": "LET",
                "name": "x",
                "value": {"type": "NUM", "value": 3},
                "body": {"type": "ADD", "left": {"type": "VAR", "name": "x"}, "right": {"type": "NUM", "value": 1}},
            },
            "LETF": {
                "type": "LETF",
                "name": "fib",
                "params": ["n"],
                "body": {
                    "type": "IF",
                    "cond": {"type": "LESS", "left": {"type": "VAR", "name": "n"}, "right": {"type": "NUM", "value": 2}},
                    "then": {"type": "VAR", "name": "n"},
                    "else": {
                        "type": "ADD",
                        "left": {"type": "CALLV", "name": "fib", "args": [{"type": "SUB", "left": {"type": "VAR", "name": "n"}, "right": {"type": "NUM", "value": 1}}]},
                        "right": {"type": "CALLV", "name": "fib", "args": [{"type": "SUB", "left": {"type": "VAR", "name": "n"}, "right": {"type": "NUM", "value": 2}}]},
                    },
                },
                "in": {"type": "CALLV", "name": "fib", "args": [{"type": "NUM", "value": 6}]},
            },
        },
        "notes": [
            "Agent B must output JSON only.",
            "The validator will reject malformed or schema-incompatible programs.",
            "Surface syntax is optional; JSON AST is canonical for v1.",
            "LET nodes use fields {name, value, body}; WRITE nodes use {expr}.",
        ],
    }


def _program_attempts(candidate: dict[str, Any], evaluations: list[dict[str, Any]] | None, tasks: list[dict[str, Any]]) -> dict[str, Any]:
    rows = evaluations or []
    task_map = {task["task_name"]: task for task in tasks}
    attempts = []
    for row in rows:
        task = row["task_name"]
        task_info = task_map[task]
        expected_success = bool(row.get("success", True))
        meta = row.get("metadata", {}) or {}
        if meta.get("program"):
            program = meta["program"]
            entry_name = meta.get("entry_name", task_info["entry_name"])
            params = meta.get("params", task_info["params"])
            tests = meta.get("tests", task_info["tests"])
        else:
            program = _build_task_program(candidate, task_info, expected_success)
            entry_name = task_info["entry_name"]
            params = task_info["params"]
            tests = task_info["tests"]
        prog = {
            "format": "json_ast_v1",
            "task_name": task,
            "entry_name": entry_name,
            "params": params,
            "model_name": row["model_name"],
            "provider": meta.get("provider", "simulated"),
            "attempt_index": meta.get("attempt_index", 1),
            "program": program,
            "tests": tests,
            "expected_success": expected_success,
        }
        attempts.append(prog)
    return {
        "candidate_id": candidate["id"],
        "submission_contract": "Agent B must return machine-parseable JSON AST, not free-form code text.",
        "attempts": attempts,
    }


def _validator_result(
    candidate: dict[str, Any],
    program_attempts: dict[str, Any],
    interpreter_source: str,
    analysis: dict[str, Any] | None,
) -> dict[str, Any]:
    rows = []
    for attempt in program_attempts.get("attempts", []):
        parse_errors = _validate_json_ast(attempt.get("program"), path=f"{attempt['task_name']}.program")
        if parse_errors:
            rows.append(
                {
                    "model_name": attempt["model_name"],
                    "task_name": attempt["task_name"],
                    "parse_ok": False,
                    "execution_ok": False,
                    "outputs_match": False,
                    "success": False,
                    "score": 0.0,
                    "notes": "; ".join(parse_errors),
                    "cases": [],
                    "expected_success": attempt.get("expected_success", True),
                }
            )
            continue

        case_programs = [
            {
                "program": _program_with_args(attempt["program"], attempt["entry_name"], case["args"]),
                "expected": case["expected"],
            }
            for case in attempt.get("tests", [])
        ]
        execution = _execute_ocaml_cases(interpreter_source, case_programs)
        case_results = execution.get("cases", [])
        outputs_match = bool(case_results) and all(case.get("match") for case in case_results)
        success = execution.get("execution_ok", False) and outputs_match
        score = round(sum(1 for case in case_results if case.get("match")) / len(case_results), 3) if case_results else 0.0
        notes = execution.get("notes", "")
        if success != bool(attempt.get("expected_success", True)):
            notes = (notes + " | " if notes else "") + "execution result differs from simulated solver label"
        rows.append(
            {
                "model_name": attempt["model_name"],
                "task_name": attempt["task_name"],
                "parse_ok": True,
                "execution_ok": execution.get("execution_ok", False),
                "outputs_match": outputs_match,
                "success": success,
                "score": score,
                "notes": notes,
                "cases": case_results,
                "expected_success": attempt.get("expected_success", True),
            }
        )

    actual_failure_rate = (sum(1 for row in rows if not row.get("success")) / len(rows)) if rows else 0.0
    return {
        "candidate_id": candidate["id"],
        "validator_mode": "json -> schema check -> AST reconstruction -> interpreter execution -> output comparison",
        "summary": {
            "total_evaluations": len(rows),
            "total_success": sum(1 for r in rows if r.get("success")),
            "total_failure": sum(1 for r in rows if not r.get("success")),
            "failure_rate": round(actual_failure_rate, 3),
            "reference_failure_rate": analysis.get("failure_rate") if analysis else candidate.get("failure_rate", 0.0),
        },
        "rows": rows,
    }


def _agent_prompts(candidate: dict[str, Any], parent_name: str | None) -> dict[str, str]:
    meta = candidate.get("metadata", {}) or {}
    agent_a = meta.get(
        "agent_a_settings",
        {
            "model": meta.get("agent_a_model", "gpt-5.4"),
            "temperature": meta.get("agent_a_temperature", 0.7),
            "thinking": meta.get("agent_a_thinking", "high"),
        },
    )
    solver_settings = meta.get(
        "solver_settings",
        meta.get(
            "agent_b_settings",
            {
                "enabled_models": [meta.get("agent_b_model", "gpt-5.4")],
                "temperature": meta.get("agent_b_temperature", 0.2),
                "thinking": meta.get("agent_b_thinking", "medium"),
                "repeat_count": 1,
                "parallelism": 1,
                "provider": "openai",
            },
        ),
    )
    enabled_models = solver_settings.get("enabled_models", [meta.get("agent_b_model", "gpt-5.4")])
    return {
        "prompts/agentA_interpreter_builder.txt": f"""You are Agent A (Interpreter Builder / Mutator).

Selected OpenAI model: {agent_a.get('model', 'gpt-5.4')}
Thinking: {agent_a.get('thinking', 'high')}
Temperature: {agent_a.get('temperature', 0.7)}

Parent language: {parent_name or 'None'}
Target candidate: {candidate['name']}
Strategy family: {candidate.get('metadata', {}).get('strategy_family', candidate.get('level'))}
Strategy leaf: {candidate.get('metadata', {}).get('strategy_leaf', 'n/a')}

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

Enabled model pool: {', '.join(enabled_models)}
Thinking: {solver_settings.get('thinking', 'medium')}
Temperature: {solver_settings.get('temperature', 0.2)}
Repeat count: {solver_settings.get('repeat_count', 1)}
Max concurrent requests: {solver_settings.get('parallelism', 1)}

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

    tasks = _task_bank(candidate)
    interpreter_source = _interpreter_code(candidate)
    language_spec = _language_spec(candidate, parent_name)
    ast_schema = _ast_schema(candidate)
    program_attempts = _program_attempts(candidate, evaluations, tasks)
    validator_result = _validator_result(candidate, program_attempts, interpreter_source, analysis)
    strategy_tree = _strategy_tree(candidate, parent_name)
    agent_graph = _agent_graph(candidate)

    files: dict[str, str] = {
        "spec.md": _spec_markdown(candidate, parent_name),
        "interpreter.ml": interpreter_source,
        "language_spec.json": json.dumps(language_spec, ensure_ascii=False, indent=2),
        "ast_schema.json": json.dumps(ast_schema, ensure_ascii=False, indent=2),
        "tasks.json": json.dumps(tasks, ensure_ascii=False, indent=2),
        "strategy_tree.json": json.dumps(strategy_tree, ensure_ascii=False, indent=2),
        "agent_graph.json": json.dumps(agent_graph, ensure_ascii=False, indent=2),
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
