from __future__ import annotations

import json
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent.parent
CANDIDATE_ROOT = BASE_DIR / "data" / "candidates"


def _task_bank(candidate: dict[str, Any]) -> list[dict[str, Any]]:
    level = candidate.get("level", "L3")
    semantics = {
        "L1": "Keywords are remapped but semantics remain mostly Python-like.",
        "L2": "Surface syntax differs from Python while execution remains structurally close.",
        "L3": "The meaning of core control flow is explicitly inverted.",
        "L4": "The language rules are only implied by examples and interpreter code.",
        "L5": "Multiple conflicts are composed: keyword, syntax, and semantic shifts.",
        "Seed": "Canonical Python-like baseline.",
    }.get(level, "Python-near language with controlled semantic conflict.")
    return [
        {
            "name": "abs",
            "prompt": "Write abs_val(x).",
            "expected_behavior": "Return the absolute value of x.",
            "reason": "Neutral/simple task.",
        },
        {
            "name": "max",
            "prompt": "Write max_val(a, b).",
            "expected_behavior": "Return the larger of two values.",
            "reason": "Low entrenchment sanity check.",
        },
        {
            "name": "fib",
            "prompt": "Write fib(n).",
            "expected_behavior": f"Implement Fibonacci under candidate semantics. {semantics}",
            "reason": "Prior-entrenched canonical task.",
        },
        {
            "name": "gcd",
            "prompt": "Write gcd(a, b).",
            "expected_behavior": f"Implement Euclidean GCD under candidate semantics. {semantics}",
            "reason": "Prior-entrenched canonical task.",
        },
    ]


def _spec_markdown(candidate: dict[str, Any], parent_name: str | None) -> str:
    metadata = candidate.get("metadata", {}) or {}
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

## Search Signals
- Similarity to Python: {candidate['similarity_score']}
- Conflict score: {candidate['conflict_score']}
- Solvable score: {candidate['solvable_score']}
- Novelty score: {candidate['novelty_score']}
- Failure rate: {candidate.get('failure_rate', 0.0)}

## Metadata
```json
{json.dumps(metadata, ensure_ascii=False, indent=2)}
```
"""


def _interpreter_code(candidate: dict[str, Any]) -> str:
    level = candidate.get("level", "L3")
    body = {
        "L1": "# Token-conflict language: parser rewrites conflicting keywords before evaluation\nKEYWORD_MAP = {'fn': 'def', 'unless': 'if', 'yieldback': 'return'}",
        "L2": "# Syntax-conflict language: blocks and declarations are reshaped before execution\n# Example: :define name [args] ->  becomes  def name(args):",
        "L3": "# Semantic-conflict language: conditionals execute when condition is FALSE\ndef eval_if(cond: bool) -> bool:\n    return not cond",
        "L4": "# Implicit semantic language: same runtime as L3, but the rule is never verbalized in prompts\ndef eval_if(cond: bool) -> bool:\n    return not cond",
        "L5": "# Compound conflict language: keyword remap + syntax reshape + inverted conditionals\nKEYWORD_MAP = {'fn': 'def', 'give': 'return'}\ndef eval_if(cond: bool) -> bool:\n    return not cond",
        "Seed": "# Canonical Python-like reference interpreter\ndef eval_if(cond: bool) -> bool:\n    return cond",
    }.get(level, "# Python-near interpreter stub")
    return f"""# interpreter.py for {candidate['name']}
# This code defines the programming language used for evaluation.

class CandidateLanguage:
    name = {candidate['name']!r}
    level = {level!r}

{body}


def run_program(source: str, tests: list[dict]) -> dict:
    # TODO: replace with real parser + executor.
    # Current MVP keeps the contract fixed for later integration.
    return {{
        'ok': True,
        'candidate': {candidate['id']!r},
        'note': 'MVP interpreter stub; connect real semantics here.'
    }}
"""


def _agent_prompts(candidate: dict[str, Any], parent_name: str | None) -> dict[str, str]:
    return {
        "prompts/agent1_newpl.txt": f"""You are Agent 1 (NewPL Searcher).

Parent language: {parent_name or 'None'}
Target candidate: {candidate['name']} ({candidate['level']})

Goal:
Generate a Python-near language that increases prior conflict without becoming meaningless.

Constraints:
- preserve human solvability
- keep interpreter deterministic
- avoid pure renaming-only triviality
- maximize failure on prior-entrenched tasks

Mutation summary:
{candidate['mutation_summary']}

Interpreter hint:
{candidate['interpreter_hint']}
""",
        "prompts/agent2_solver.txt": f"""You are Agent 2 (Solver Bench).

This code defines our programming language.
[interpreter.py]

Solve the following tasks in this language:
- abs
- max
- fib
- gcd

Default prompt mode: interpreter_as_spec
Candidate: {candidate['name']}
""",
        "prompts/agent3_curator.txt": f"""You are Agent 3 (Analyzer / Curator).

Assess whether candidate {candidate['name']} should enter the hardest-language archive.

Keep candidates that are:
- hard for multiple models
- still human-solvable
- close enough to Python to support a prior-conflict story
- novel relative to the existing archive

Signals:
- similarity_score={candidate['similarity_score']}
- conflict_score={candidate['conflict_score']}
- solvable_score={candidate['solvable_score']}
- novelty_score={candidate['novelty_score']}
""",
    }


def materialize_candidate_bundle(
    candidate: dict[str, Any],
    parent_name: str | None = None,
    evaluations: list[dict[str, Any]] | None = None,
    analysis: dict[str, Any] | None = None,
) -> dict[str, Any]:
    candidate_dir = CANDIDATE_ROOT / candidate["id"]
    prompts_dir = candidate_dir / "prompts"
    prompts_dir.mkdir(parents=True, exist_ok=True)

    files: dict[str, str] = {
        "spec.md": _spec_markdown(candidate, parent_name),
        "interpreter.py": _interpreter_code(candidate),
        "tasks.json": json.dumps(_task_bank(candidate), ensure_ascii=False, indent=2),
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
