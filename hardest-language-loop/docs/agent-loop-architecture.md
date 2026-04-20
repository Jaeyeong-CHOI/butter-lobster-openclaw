# Agent Loop Architecture (v1)

> Updated: 2026-04-20
> Principle: Ignore prompt-readability confounds for now.
> Focus: Interpreter mutation → code generation → interpreter execution validation.

---

## 1. Core decision

For the first real version of the project, we do **not** treat “the model may fail because it cannot read the prompt/interpreter code” as the primary research question.

Instead, we define the loop around a cleaner pipeline:

1. A specialized agent **creates or mutates an OCaml interpreter**.
2. A specialized agent **generates code/programs for that interpreter**.
3. The generated program is converted into a **JSON-structured representation**.
4. The interpreter runs the program.
5. The system validates success/failure **by execution**, not by textual judgment.

This makes the system much more executable, measurable, and stable.

---

## 2. Revised architecture

```text
[Agent A: Interpreter Builder / Mutator]
   ↓
Generates:
- interpreter.ml
- language metadata
- task set
- JSON schema / AST spec

[Agent B: Program Generator / Solver]
   ↓
Reads:
- interpreter.ml
- task description
- AST/JSON schema

Outputs:
- program.json
- optional program pretty-print form

[Deterministic Validator]
   ↓
1. parse JSON
2. convert JSON -> internal AST
3. execute via interpreter
4. compare with expected outputs
5. log success/failure
```

So in practice this is:
- **two specialized generative agents**
- **one deterministic execution/validation layer**

The validator is not an “intelligent” agent; it is infrastructure.

---

## 3. Why this is better than prompt-only language description

### 3.1 Stronger source of truth
The language is not merely described in natural language.
It is **defined by the OCaml interpreter itself**.

That means:
- semantics are executable
- the evaluator and the spec are aligned
- no ambiguity from paraphrased prompt descriptions

### 3.2 Execution-based validation
We do not need a judge LLM to decide whether the program was correct.

Instead:
- if `program.json` is parsed successfully,
- and the interpreter executes it,
- and the outputs match the task requirements,

then the candidate succeeds.

This is cleaner and much easier to defend in a paper.

### 3.3 Removes one confound for v1
By design, we temporarily ignore:
> “Did the model fail because it could not understand the interpreter prompt?”

That can be studied later.
For v1, we only care about:
> “Given a precisely defined executable language, can the system generate a correct program in it?”

---

## 4. Agent roles

## 4.1 Agent A — Interpreter Builder / Mutator

### Goal
Create or mutate an OCaml interpreter that defines a candidate programming language.

### Input
- seed interpreter (`interpreter.ml`)
- mutation policy
- prior language family (Python-near, B-language, confusion-language family, etc.)
- task requirements

### Output
- `interpreter.ml`
- `language_spec.json`
- `ast_schema.json`
- `tasks.json`
- `mutation_log.json`

### Responsibilities
- mutate semantics, syntax, or both
- ensure interpreter still compiles/runs
- ensure language is deterministic enough to evaluate
- define the JSON program format that Agent B must use

### Example mutations
- invert `IF`
- swap comparison semantics
- change evaluation order of `SEQ`
- alter `CALLV` / `CALLR`
- change assignment behavior
- mutate record-field access/update semantics

### Hard constraint
Agent A must not output “interesting but broken” languages.
Every interpreter candidate must pass infrastructure self-checks.

---

## 4.2 Agent B — Program Generator / Solver

### Goal
Given an OCaml interpreter + task + JSON AST schema, generate a program that solves the task in that language.

### Input
- `interpreter.ml`
- `language_spec.json`
- `ast_schema.json`
- `tasks.json`
- selected model (user-configurable Agent2 model)

### Output
- `program.json`
- optional `program_pretty.txt`
- optional reasoning trace (not used for validation)

### Important constraint
The primary output must be **machine-parseable JSON**, not free-form code text.

That means Agent B should produce something like:

```json
{
  "type": "LETF",
  "name": "fib",
  "params": ["n"],
  "body": {
    "type": "IF",
    "cond": { "type": "LESS", "left": {"type": "VAR", "name": "n"}, "right": {"type": "NUM", "value": 2} },
    "then": { "type": "VAR", "name": "n" },
    "else": {
      "type": "ADD",
      "left": { "type": "CALLV", "name": "fib", "args": [...] },
      "right": { "type": "CALLV", "name": "fib", "args": [...] }
    }
  }
}
```

This avoids brittle text parsing.

---

## 5. JSON-first program representation

This is a key design decision.

## 5.1 Why JSON
If Agent B outputs free-form source code,
we need another parser for every generated language.
That becomes a huge engineering burden.

Instead, we define:
- a language-level interpreter in OCaml
- a canonical JSON AST representation

Then the execution pipeline is:

```text
program.json
  -> JSON parser
  -> OCaml AST value
  -> eval
  -> output trace / result
```

So even if the language surface syntax is exotic,
Agent B still writes to a stable structured format.

## 5.2 Separation of concerns
This gives a clean split:
- **surface syntax** = optional / human-facing
- **semantic structure** = JSON AST
- **actual execution** = interpreter

For v1, JSON AST should be the canonical submission format.
Pretty-printed surface syntax can be added later as a secondary display.

---

## 6. Deterministic validator

The validator should do the following:

1. validate `program.json` against `ast_schema.json`
2. transform JSON into OCaml AST
3. execute using `runb` or equivalent interpreter entrypoint
4. compare execution outputs against `tasks.json`
5. emit a structured report

### Validator output example

```json
{
  "candidate_id": "cand-001",
  "task": "fib",
  "parse_ok": true,
  "execution_ok": true,
  "outputs_match": false,
  "stdout": [0,1,1,2,3,5,8],
  "expected": [0,1,1,2,3,5,8],
  "success": true,
  "error": null
}
```

This should be the only source of truth for success/failure.

---

## 7. Data artifacts per iteration

Each iteration should store:

```text
runs/<iteration>/<candidate_id>/
  interpreter.ml
  language_spec.json
  ast_schema.json
  tasks.json
  mutation_log.json
  agentA_prompt.txt
  agentB_prompt.txt
  program.json
  validator_result.json
  summary.json
```

This is exactly what the web dashboard should expose.

### In the dashboard, each candidate should show:
- interpreter code
- mutation summary
- AST schema
- task definitions
- Agent A prompt
- Agent B prompt
- generated JSON program
- execution result
- pass/fail summary

So the dashboard becomes a **real experimental observability tool**, not just a toy status page.

---

## 8. Recommended first implementation target

## Step 1 — Fixed interpreter, JSON AST only
Start with one known interpreter (e.g. B-language HW3 style).

Build:
- JSON AST schema
- JSON → OCaml AST converter
- validator runner
- one fixed task (`abs`, `max`, `fib`)

Do **not** do mutation yet.

Goal:
> prove that Agent B can generate JSON programs that the interpreter can execute.

## Step 2 — Controlled interpreter mutation
Add Agent A mutations on one axis only:
- inverted `IF`
- comparison swap
- altered `SEQ`

Goal:
> prove the loop can generate candidate interpreters and benchmark them automatically.

## Step 3 — Archive / hardness tracking
Track:
- which interpreters compile
- which are human-readable
- which produce high failure rates
- which are archived as “hardest so far”

---

## 9. What we are explicitly NOT doing yet

For v1, we postpone:
- prompt readability analysis
- natural-language-only language descriptions
- judging free-form source code text
- multiple meta-language confounds (e.g. OCaml vs Python interpreter prompt comparison)
- full training loop

These can be second-phase research questions.

---

## 10. Best immediate next step

The most concrete next move is:

### Build this first
1. `interpreter.ml` seed file
2. `ast_schema.json`
3. `json_to_ast.ml`
4. `validator.py` or `validator.sh`
5. Agent B contract: output `program.json`

### Then connect to web UI
Expose in the dashboard:
- current interpreter
- current selected Agent2 model
- last generated `program.json`
- validator result
- pass/fail

---

## 11. Final design principle

For v1, the loop should answer this narrower but stronger question:

> **Given a precisely defined executable language (via interpreter), can an agent generate a valid JSON program that solves the task, and can we verify that deterministically by execution?**

That is already strong enough to support the hardest-language search story.
