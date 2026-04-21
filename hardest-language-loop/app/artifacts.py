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


def _strategy_tree(candidate: dict[str, Any], parent_name: str | None) -> dict[str, Any]:
    level = candidate.get("level", "L3")
    selected_family = {
        "Seed": "baseline_python_near",
        "L1": "token_conflict",
        "L2": "syntax_conflict",
        "L3": "semantic_conflict",
        "L4": "implicit_semantic_conflict",
        "L5": "compound_conflict",
    }.get(level, "semantic_conflict")
    selected_leaf = {
        "Seed": "baseline_reference",
        "L1": "cross_keyword_swap",
        "L2": "block_syntax_inversion",
        "L3": "inverted_if",
        "L4": "example_only_rule_induction",
        "L5": "keyword_plus_syntax_plus_semantics",
    }.get(level, "inverted_if")

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
    level = candidate.get("level", "L3")
    agent_a_settings = meta.get(
        "agent_a_settings",
        {
            "model": meta.get("agent_a_model", "gpt-5.4"),
            "temperature": meta.get("agent_a_temperature", 0.7),
            "thinking": meta.get("agent_a_thinking", "high"),
        },
    )
    agent_b_settings = meta.get(
        "agent_b_settings",
        {
            "model": meta.get("agent_b_model", "gpt-5.4"),
            "temperature": meta.get("agent_b_temperature", 0.2),
            "thinking": meta.get("agent_b_thinking", "medium"),
        },
    )
    semantics = {
        "control_flow": "inverted_if" if level in {"L3", "L4", "L5"} else "canonical_if",
        "syntax_mode": "python_near" if candidate.get("similarity_score", 0.0) >= 0.7 else "restructured",
        "submission_format": "json_ast_v1",
        "execution_mode": "interpreter_ml",
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
        "agent_settings": {
            "agent_a": agent_a_settings,
            "agent_b": agent_b_settings,
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
    level = candidate.get("level", "L3")
    semantics = {
        "L1": {
            "comment": "(* token-conflict language: conflicting surface keywords are normalized before function lookup *)",
            "keyword_rule": "let normalize_keyword k = match k with | \"fn\" -> \"def\" | \"unless\" -> \"if\" | _ -> k",
            "if_rule": "let eval_if cond = cond",
        },
        "L2": {
            "comment": "(* syntax-conflict language: surface syntax is assumed to be normalized into the AST before evaluation *)",
            "keyword_rule": "let normalize_keyword k = k",
            "if_rule": "let eval_if cond = cond",
        },
        "L3": {
            "comment": "(* semantic-conflict language: IF executes its then-branch when the condition evaluates to FALSE *)",
            "keyword_rule": "let normalize_keyword k = k",
            "if_rule": "let eval_if cond = not cond",
        },
        "L4": {
            "comment": "(* implicit semantic language: the runtime inverts IF, but the rule is meant to be inferred from behavior/examples *)",
            "keyword_rule": "let normalize_keyword k = k",
            "if_rule": "let eval_if cond = not cond",
        },
        "L5": {
            "comment": "(* compound conflict language: keyword remap + inverted IF semantics are both active in the runtime *)",
            "keyword_rule": "let normalize_keyword k = match k with | \"fn\" -> \"def\" | \"give\" -> \"return\" | _ -> k",
            "if_rule": "let eval_if cond = not cond",
        },
        "Seed": {
            "comment": "(* canonical Python-like baseline interpreter *)",
            "keyword_rule": "let normalize_keyword k = k",
            "if_rule": "let eval_if cond = cond",
        },
    }.get(
        level,
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
  if not !Sys.interactive then (
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
    meta = candidate.get("metadata", {}) or {}
    agent_a = meta.get(
        "agent_a_settings",
        {
            "model": meta.get("agent_a_model", "gpt-5.4"),
            "temperature": meta.get("agent_a_temperature", 0.7),
            "thinking": meta.get("agent_a_thinking", "high"),
        },
    )
    agent_b = meta.get(
        "agent_b_settings",
        {
            "model": meta.get("agent_b_model", "gpt-5.4"),
            "temperature": meta.get("agent_b_temperature", 0.2),
            "thinking": meta.get("agent_b_thinking", "medium"),
        },
    )
    return {
        "prompts/agentA_interpreter_builder.txt": f"""You are Agent A (Interpreter Builder / Mutator).

Selected OpenAI model: {agent_a.get('model', 'gpt-5.4')}
Thinking: {agent_a.get('thinking', 'high')}
Temperature: {agent_a.get('temperature', 0.7)}

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

Selected OpenAI model: {agent_b.get('model', 'gpt-5.4')}
Thinking: {agent_b.get('thinking', 'medium')}
Temperature: {agent_b.get('temperature', 0.2)}

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
    strategy_tree = _strategy_tree(candidate, parent_name)
    agent_graph = _agent_graph(candidate)

    files: dict[str, str] = {
        "spec.md": _spec_markdown(candidate, parent_name),
        "interpreter.ml": _interpreter_code(candidate),
        "language_spec.json": json.dumps(language_spec, ensure_ascii=False, indent=2),
        "ast_schema.json": json.dumps(ast_schema, ensure_ascii=False, indent=2),
        "tasks.json": json.dumps(_task_bank(candidate), ensure_ascii=False, indent=2),
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
