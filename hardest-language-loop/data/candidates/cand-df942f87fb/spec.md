# PL-027 L3

- **Candidate ID:** cand-df942f87fb
- **Level:** L3
- **Parent:** L3 InvertedIf Seed
- **Status:** generated
- **Archived:** no

## Mutation Summary
Inverted-if semantics

## Interpreter Hint
Conditionals execute on FALSE; comparison and boolean behavior partially conflict with Python.

## Pipeline
1. Agent A mutates or creates the interpreter.
2. Agent B generates a JSON AST program for the task.
3. The deterministic validator parses JSON, reconstructs AST, executes the interpreter, and compares outputs.

## Structured Spec
```json
{
  "candidate_id": "cand-df942f87fb",
  "name": "PL-027 L3",
  "level": "L3",
  "parent": "L3 InvertedIf Seed",
  "mutation_summary": "Inverted-if semantics",
  "interpreter_hint": "Conditionals execute on FALSE; comparison and boolean behavior partially conflict with Python.",
  "scores": {
    "similarity": 0.948,
    "conflict": 0.929,
    "solvable": 0.758,
    "novelty": 0.687,
    "failure_rate": 0.0
  },
  "semantics": {
    "control_flow": "inverted_if",
    "syntax_mode": "python_near",
    "submission_format": "json_ast_v1",
    "execution_mode": "interpreter_ml",
    "agent2_model": "gpt-5.4"
  },
  "pipeline": {
    "agent_a": "Interpreter Builder / Mutator",
    "agent_b": "Program Generator / Solver",
    "validator": "Deterministic JSON->AST->Interpreter execution"
  },
  "status": "generated",
  "archived": false,
  "metadata": {
    "prompt_mode_default": "interpreter_as_spec",
    "agent1_parent": "L3 InvertedIf Seed",
    "agent2_model": "gpt-5.4",
    "python_near": true,
    "task_bank": [
      "abs",
      "max",
      "fib",
      "gcd"
    ]
  }
}
```
