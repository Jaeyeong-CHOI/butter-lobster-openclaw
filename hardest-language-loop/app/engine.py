from __future__ import annotations

import asyncio
import json
import random
import re
import urllib.error
import urllib.request
import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from . import store
from .artifacts import (
    _ast_schema,
    _build_task_program,
    _execute_ocaml_cases,
    _interpreter_code,
    _program_with_args,
    _task_bank,
    _validate_json_ast,
    materialize_candidate_bundle,
)

OPENAI_MODEL_CATALOG = {
    "gpt-5.4": {
        "name": "gpt-5.4",
        "skill": 0.82,
        "prior_strength": 0.92,
        "description": "최상위 범용 reasoning 모델",
    },
    "gpt-5.4-mini": {
        "name": "gpt-5.4-mini",
        "skill": 0.69,
        "prior_strength": 0.78,
        "description": "gpt-5.4 경량형",
    },
    "gpt-5.4-nano": {
        "name": "gpt-5.4-nano",
        "skill": 0.57,
        "prior_strength": 0.83,
        "description": "초경량·저비용 계열",
    },
    "gpt-4.1": {
        "name": "gpt-4.1",
        "skill": 0.76,
        "prior_strength": 0.89,
        "description": "안정적인 범용 모델",
    },
    "gpt-4.1-mini": {
        "name": "gpt-4.1-mini",
        "skill": 0.63,
        "prior_strength": 0.82,
        "description": "gpt-4.1 경량형",
    },
    "gpt-4o": {
        "name": "gpt-4o",
        "skill": 0.74,
        "prior_strength": 0.87,
        "description": "멀티모달 기반 범용 모델",
    },
    "gpt-4o-mini": {
        "name": "gpt-4o-mini",
        "skill": 0.58,
        "prior_strength": 0.79,
        "description": "gpt-4o 경량형",
    },
    "o4-mini": {
        "name": "o4-mini",
        "skill": 0.88,
        "prior_strength": 0.71,
        "description": "reasoning 성향이 강한 경량 모델",
    },
}

THINKING_OPTIONS = ("off", "low", "medium", "high")
THINKING_BONUS = {
    "off": -0.04,
    "low": 0.0,
    "medium": 0.03,
    "high": 0.06,
}

TASKS = [
    {"name": "abs", "entrenchment": 0.15},
    {"name": "max", "entrenchment": 0.20},
    {"name": "fib", "entrenchment": 0.92},
    {"name": "gcd", "entrenchment": 0.88},
]

MUTATIONS = [
    {
        "family": "token_conflict",
        "mutation_summary": "Keyword aliases and token remaps are introduced while the overall language shape stays Python-near.",
        "interpreter_hint": "Surface keywords are deliberately remapped to conflict with Python priors.",
    },
    {
        "family": "syntax_conflict",
        "mutation_summary": "Control structures and declaration syntax are reshaped while the runtime remains mostly familiar.",
        "interpreter_hint": "Surface syntax is reorganized before execution.",
    },
    {
        "family": "semantic_conflict",
        "mutation_summary": "Core control-flow behavior is inverted or reweighted against Python expectations.",
        "interpreter_hint": "Execution rules conflict with the Python prior in key branching cases.",
    },
    {
        "family": "implicit_semantic_conflict",
        "mutation_summary": "The crucial runtime rule is implicit in examples/interpreter behavior rather than stated up front.",
        "interpreter_hint": "The model has to infer the runtime rule from behavior, not a clean natural-language summary.",
    },
    {
        "family": "compound_conflict",
        "mutation_summary": "Keyword, syntax, and semantic conflicts are bundled together in one candidate language.",
        "interpreter_hint": "Multiple prior-breaking mechanisms are combined in the same interpreter.",
    },
]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class LoopConfig:
    tick_seconds: float = 3.0


class AgentLoopService:
    def __init__(self) -> None:
        self._task: asyncio.Task[Any] | None = None
        self._step_task: asyncio.Task[Any] | None = None
        self._running = False
        self._iteration_lock = asyncio.Lock()
        self.config = LoopConfig()

    def bootstrap(self) -> None:
        total = store.get_overview()["stats"]["total_candidates"]
        if total == 0:
            store.insert_event(
                "bootstrap",
                {
                    "message": "Empty-state bootstrap complete",
                    "note": "No mock candidates were inserted. Generate or import real candidates.",
                },
                now_iso(),
            )

    async def start(self) -> dict[str, Any]:
        if self._running:
            return {"ok": True, "status": "already_running"}
        self._running = True
        store.set_loop_state(status="running", note="Loop running")
        self._task = asyncio.create_task(self._run())
        store.insert_event("loop_started", {"message": "Agent loop started"}, now_iso())
        return {"ok": True, "status": "started"}

    async def pause(self) -> dict[str, Any]:
        self._running = False
        store.set_loop_state(status="paused", note="Loop paused")
        store.insert_event("loop_paused", {"message": "Agent loop paused"}, now_iso())
        return {"ok": True, "status": "paused"}

    async def step_once(self) -> dict[str, Any]:
        if self._running:
            return {"ok": False, "status": "busy", "detail": "Loop is already running"}
        if self._step_task and not self._step_task.done():
            return {"ok": False, "status": "busy", "detail": "A manual step is already in progress"}
        store.set_loop_state(status="running", note="Manual step queued")

        async def _manual_step_wrapper() -> None:
            try:
                await self._run_iteration(manual=True)
            finally:
                if not self._running:
                    store.set_loop_state(status="idle", note="Manual step completed")

        self._step_task = asyncio.create_task(_manual_step_wrapper())
        return {"ok": True, "status": "queued"}

    async def reset(self) -> dict[str, Any]:
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
        if self._step_task and not self._step_task.done():
            self._step_task.cancel()
        backup = store.reset_all()
        self.bootstrap()
        payload = {"message": "Loop state reset", "backup": backup}
        store.insert_event("loop_reset", payload, now_iso())
        return {"ok": True, "status": "reset", "backup": backup}

    async def _run(self) -> None:
        try:
            while self._running:
                await self._run_iteration(manual=False)
                await asyncio.sleep(self.config.tick_seconds)
        except asyncio.CancelledError:
            pass
        finally:
            if not self._running:
                store.set_loop_state(status="paused", note="Loop paused")

    def _choose_parent(self) -> dict[str, Any] | None:
        candidates = store.list_candidates(limit=200)
        archived = [c for c in candidates if c.get("archived")]
        pool = archived or candidates
        if not pool:
            return None
        pool = sorted(pool, key=lambda c: (c.get("failure_rate", 0), c.get("conflict_score", 0)), reverse=True)
        return random.choice(pool[: min(6, len(pool))])

    def _next_strategy(self, family: str, iteration: int, parent: dict[str, Any] | None) -> tuple[str, str]:
        parent_meta = (parent or {}).get("metadata", {}) or {}
        existing_family = parent_meta.get("strategy_family")
        variants = {
            "token_conflict": ["alias_swap", "keyword_shadow", "surface_synonym"],
            "syntax_conflict": ["block_syntax_inversion", "delimiter_shift", "header_rewrite"],
            "semantic_conflict": ["inverted_if", "inverted_base_case", "comparison_flip"],
            "implicit_semantic_conflict": ["example_only_rule_induction", "silent_branch_rule", "implicit_operator_shift"],
            "compound_conflict": ["keyword_plus_syntax_plus_semantics", "compound_control_bundle", "stacked_prior_conflict"],
        }
        chosen_family = family or existing_family or "semantic_conflict"
        leaves = variants.get(chosen_family, ["inverted_if"])
        leaf = leaves[iteration % len(leaves)]
        return chosen_family, leaf

    def _generate_candidate(self, iteration: int, parent: dict[str, Any] | None) -> dict[str, Any]:
        settings = store.get_settings()
        agent_a_model = settings.get("agent_a_model", "gpt-5.4")
        agent_a_temperature = float(settings.get("agent_a_temperature", 0.7))
        agent_a_thinking = str(settings.get("agent_a_thinking", "high"))
        solver_models = list(settings.get("solver_models", list(OPENAI_MODEL_CATALOG.keys())))
        solver_temperature = float(settings.get("solver_temperature", 0.2))
        solver_thinking = str(settings.get("solver_thinking", "medium"))
        solver_repeat_count = int(settings.get("solver_repeat_count", 5))
        solver_parallelism = int(settings.get("solver_parallelism", 10))

        rnd = random.Random(iteration * 7919)
        mutation = MUTATIONS[iteration % len(MUTATIONS)]
        strategy_family = mutation["family"]
        mutation_summary = mutation["mutation_summary"]
        interpreter_hint = mutation["interpreter_hint"]
        strategy_family, strategy_leaf = self._next_strategy(strategy_family, iteration, parent)
        parent_similarity = float(parent.get("similarity_score", 0.95)) if parent else 0.95
        agent_a_thinking_bonus = THINKING_BONUS.get(agent_a_thinking, 0.03)
        similarity = max(0.45, min(0.98, parent_similarity + rnd.uniform(-0.08, 0.03)))
        conflict = max(
            0.15,
            min(
                0.98,
                (parent.get("conflict_score", 0.2) if parent else 0.2)
                + rnd.uniform(0.03, 0.15)
                + agent_a_thinking_bonus * 0.4
                + max(0.0, agent_a_temperature - 0.4) * 0.05,
            ),
        )
        solvable = max(0.35, min(0.97, 0.92 - abs(conflict - 0.72) * 0.7 + rnd.uniform(-0.08, 0.05)))
        novelty = max(0.15, min(0.99, rnd.uniform(0.35, 0.9) + agent_a_thinking_bonus * 0.5 + agent_a_temperature * 0.05))
        return {
            "id": f"cand-{uuid.uuid4().hex[:10]}",
            "parent_id": parent.get("id") if parent else None,
            "level": strategy_family,
            "name": f"PL-{iteration:03d}",
            "mutation_summary": mutation_summary,
            "interpreter_hint": interpreter_hint,
            "similarity_score": round(similarity, 3),
            "conflict_score": round(conflict, 3),
            "solvable_score": round(solvable, 3),
            "novelty_score": round(novelty, 3),
            "failure_rate": 0.0,
            "archived": False,
            "status": "generated",
            "metadata": {
                "prompt_mode_default": "interpreter_as_spec",
                "agent1_parent": parent.get("name") if parent else "None",
                "agent_a_settings": {
                    "model": agent_a_model,
                    "temperature": agent_a_temperature,
                    "thinking": agent_a_thinking,
                },
                "solver_settings": {
                    "provider": "openai",
                    "enabled_models": solver_models,
                    "temperature": solver_temperature,
                    "thinking": solver_thinking,
                    "repeat_count": solver_repeat_count,
                    "parallelism": solver_parallelism,
                },
                "python_near": similarity > 0.72,
                "task_bank": [t["name"] for t in TASKS],
                "strategy_family": strategy_family,
                "strategy_leaf": strategy_leaf,
            },
            "created_at": now_iso(),
        }

    def _supports_reasoning(self, model_name: str) -> bool:
        return model_name.startswith("o") or model_name.startswith("gpt-5")

    def _extract_json_block(self, text: str) -> str:
        stripped = text.strip()
        if stripped.startswith("```"):
            stripped = re.sub(r"^```(?:json)?\s*", "", stripped)
            stripped = re.sub(r"\s*```$", "", stripped)
        try:
            json.loads(stripped)
            return stripped
        except Exception:
            pass
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start != -1 and end != -1 and end > start:
            return stripped[start : end + 1]
        raise ValueError("No JSON object found in model output")

    def _extract_response_text(self, payload: dict[str, Any]) -> str:
        text = payload.get("output_text")
        if isinstance(text, str) and text.strip():
            return text.strip()
        for item in payload.get("output", []):
            if item.get("type") != "message":
                continue
            for content in item.get("content", []):
                if content.get("type") == "output_text" and isinstance(content.get("text"), str):
                    return content["text"].strip()
        raise ValueError("No output_text found in OpenAI response")

    def _solver_prompt(
        self,
        *,
        candidate: dict[str, Any],
        interpreter_source: str,
        ast_schema: dict[str, Any],
        task: dict[str, Any],
    ) -> str:
        return f"""You are Agent B for the hardest-language benchmark.
Return ONLY a JSON object for a top-level exp AST.
No markdown fences. No explanation.

Candidate: {candidate['name']}
Strategy family: {candidate['metadata'].get('strategy_family')}
Strategy leaf: {candidate['metadata'].get('strategy_leaf')}
Mutation summary: {candidate['mutation_summary']}
Task: {task['task_name']}
Entry function name: {task['entry_name']}
Parameters: {task['params']}
Prompt: {task['prompt']}
Expected behavior: {task['expected_behavior']}
Tests: {json.dumps(task['tests'], ensure_ascii=False)}

JSON AST rules:
- Root should usually be a LETF node defining {task['entry_name']} and invoking it in the `in` field.
- LET uses fields: name, value, body
- WRITE uses field: expr
- CALLV uses fields: name, args
- Return machine-parseable JSON only

AST schema reference:
{json.dumps(ast_schema, ensure_ascii=False, indent=2)}

Interpreter:
{interpreter_source}
"""

    def _solve_with_openai(
        self,
        *,
        api_key: str,
        model_name: str,
        thinking: str,
        temperature: float,
        candidate: dict[str, Any],
        interpreter_source: str,
        ast_schema: dict[str, Any],
        task: dict[str, Any],
        prompt_text: str,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": model_name,
            "input": [
                {
                    "role": "system",
                    "content": [{"type": "input_text", "text": "You are a precise compiler-like solver. Produce JSON only."}],
                },
                {
                    "role": "user",
                    "content": [{"type": "input_text", "text": prompt_text}],
                },
            ],
            "temperature": temperature,
        }
        if thinking != "off" and self._supports_reasoning(model_name):
            payload["reasoning"] = {"effort": thinking}

        req = urllib.request.Request(
            "https://api.openai.com/v1/responses",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=45) as resp:
                raw = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"OpenAI HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"OpenAI request failed: {exc}") from exc

        output_text = self._extract_response_text(raw)
        json_text = self._extract_json_block(output_text)
        parsed = json.loads(json_text)
        if isinstance(parsed, dict) and "program" in parsed and isinstance(parsed["program"], dict):
            program = parsed["program"]
        else:
            program = parsed
        return {
            "program": program,
            "raw_response": raw,
            "response_text": output_text,
        }

    def _simulate_attempt(
        self,
        *,
        candidate: dict[str, Any],
        model_name: str,
        task: dict[str, Any],
        attempt_index: int,
        temperature: float,
        thinking: str,
    ) -> dict[str, Any]:
        model = OPENAI_MODEL_CATALOG.get(model_name, OPENAI_MODEL_CATALOG["gpt-5.4"])
        entrenchment = next((item["entrenchment"] for item in TASKS if item["name"] == task["task_name"]), 0.4)
        seed = f"{candidate['id']}:{model_name}:{task['task_name']}:{attempt_index}"
        rnd = random.Random(seed)
        prior_penalty = entrenchment * candidate["conflict_score"] * model["prior_strength"]
        capability = model["skill"] * candidate["solvable_score"]
        prompt_bonus = 0.08 if candidate["metadata"].get("strategy_family") in {"token_conflict", "syntax_conflict", "semantic_conflict"} else -0.05
        thinking_bonus = THINKING_BONUS.get(thinking, 0.03)
        stability_penalty = abs(temperature - 0.2) * 0.08
        raw_score = capability - prior_penalty + prompt_bonus + thinking_bonus - stability_penalty + rnd.uniform(-0.08, 0.08)
        success = raw_score > 0.18
        program = _build_task_program(candidate, task, success)
        return {
            "program": program,
            "simulated_success": success,
            "score": max(0.0, min(1.0, 0.5 + raw_score)),
            "response_text": json.dumps(program, ensure_ascii=False),
        }

    async def _evaluate_attempt(
        self,
        *,
        api_key: str | None,
        model_name: str,
        task: dict[str, Any],
        candidate: dict[str, Any],
        interpreter_source: str,
        ast_schema: dict[str, Any],
        thinking: str,
        temperature: float,
        attempt_index: int,
        repeat_count: int,
    ) -> dict[str, Any]:
        provider = "openai" if api_key else "simulated"
        notes: list[str] = []
        parse_errors: list[str] = []
        raw_response: Any = None
        response_text = ""
        execution_cases: list[dict[str, Any]] = []
        execution_stdout: list[str] = []
        program: dict[str, Any] | None = None
        prompt_text = self._solver_prompt(
            candidate=candidate,
            interpreter_source=interpreter_source,
            ast_schema=ast_schema,
            task=task,
        )

        try:
            if api_key:
                solve = await asyncio.to_thread(
                    self._solve_with_openai,
                    api_key=api_key,
                    model_name=model_name,
                    thinking=thinking,
                    temperature=temperature,
                    candidate=candidate,
                    interpreter_source=interpreter_source,
                    ast_schema=ast_schema,
                    task=task,
                    prompt_text=prompt_text,
                )
                program = solve["program"]
                raw = solve.get("raw_response") or {}
                raw_response = {
                    "id": raw.get("id"),
                    "status": raw.get("status"),
                    "model": raw.get("model"),
                    "usage": raw.get("usage"),
                }
                response_text = solve.get("response_text", "")
            else:
                solve = self._simulate_attempt(
                    candidate=candidate,
                    model_name=model_name,
                    task=task,
                    attempt_index=attempt_index,
                    temperature=temperature,
                    thinking=thinking,
                )
                program = solve["program"]
                response_text = solve.get("response_text", "")
                notes.append("simulated fallback used because OpenAI API key is missing")
        except Exception as exc:
            notes.append(str(exc))

        if program is None:
            success = False
            score = 0.0
            execution_ok = False
            outputs_match = False
        else:
            parse_errors = _validate_json_ast(program, path=f"{task['task_name']}.program")
            if parse_errors:
                notes.extend(parse_errors)
                success = False
                score = 0.0
                execution_ok = False
                outputs_match = False
            else:
                case_programs = [
                    {
                        "program": _program_with_args(program, task["entry_name"], case["args"]),
                        "expected": case["expected"],
                    }
                    for case in task.get("tests", [])
                ]
                execution = await asyncio.to_thread(_execute_ocaml_cases, interpreter_source, case_programs)
                execution_ok = bool(execution.get("execution_ok"))
                execution_cases = execution.get("cases", [])
                execution_stdout = execution.get("stdout", [])
                if execution.get("notes"):
                    notes.append(str(execution["notes"]))
                outputs_match = bool(execution_cases) and all(case.get("match") for case in execution_cases)
                success = execution_ok and outputs_match
                score = round(sum(1 for case in execution_cases if case.get("match")) / len(execution_cases), 3) if execution_cases else 0.0

        return {
            "id": f"eval-{uuid.uuid4().hex[:12]}",
            "candidate_id": candidate["id"],
            "model_name": model_name,
            "task_name": task["task_name"],
            "prompt_mode": "interpreter_as_spec",
            "success": success,
            "score": score,
            "notes": " | ".join(note for note in notes if note),
            "created_at": now_iso(),
            "metadata": {
                "provider": provider,
                "attempt_index": attempt_index,
                "repeat_count": repeat_count,
                "entry_name": task["entry_name"],
                "params": task.get("params", []),
                "tests": task.get("tests", []),
                "program": program,
                "parse_errors": parse_errors,
                "execution_ok": execution_ok if program is not None else False,
                "outputs_match": outputs_match if program is not None else False,
                "cases": execution_cases,
                "stdout": execution_stdout,
                "response_text": response_text,
                "raw_response": raw_response,
                "prompt": prompt_text,
                "thinking": thinking,
                "temperature": temperature,
            },
        }

    async def _evaluate_candidate(self, candidate: dict[str, Any], iteration: int) -> list[dict[str, Any]]:
        settings = store.get_settings()
        solver_models = list(settings.get("solver_models", list(OPENAI_MODEL_CATALOG.keys())))
        repeat_count = int(settings.get("solver_repeat_count", 5))
        parallelism = int(settings.get("solver_parallelism", 10))
        thinking = str(settings.get("solver_thinking", "medium"))
        temperature = float(settings.get("solver_temperature", 0.2))
        api_key = store.get_openai_api_key()

        tasks = _task_bank(candidate)
        interpreter_source = _interpreter_code(candidate)
        ast_schema = _ast_schema(candidate)
        total_jobs = len(solver_models) * len(tasks) * repeat_count
        completed = 0
        progress_interval = max(1, total_jobs // 16)
        semaphore = asyncio.Semaphore(parallelism)
        results: list[dict[str, Any]] = []

        store.insert_event(
            "solver_bench_started",
            {
                "candidate_id": candidate["id"],
                "models": solver_models,
                "repeat_count": repeat_count,
                "parallelism": parallelism,
                "total_jobs": total_jobs,
                "provider": "openai" if api_key else "simulated",
            },
            now_iso(),
        )

        async def run_job(model_name: str, task: dict[str, Any], attempt_index: int) -> None:
            nonlocal completed
            async with semaphore:
                evaluation = await self._evaluate_attempt(
                    api_key=api_key,
                    model_name=model_name,
                    task=task,
                    candidate=candidate,
                    interpreter_source=interpreter_source,
                    ast_schema=ast_schema,
                    thinking=thinking,
                    temperature=temperature,
                    attempt_index=attempt_index,
                    repeat_count=repeat_count,
                )
            store.insert_evaluation(evaluation)
            results.append(evaluation)
            completed += 1
            if completed % progress_interval == 0 or completed == total_jobs:
                store.set_loop_state(
                    status="running" if self._running else "idle",
                    iteration=iteration,
                    note=f"{candidate['name']} benchmarking {completed}/{total_jobs}",
                )
                store.insert_event(
                    "solver_progress",
                    {
                        "candidate_id": candidate["id"],
                        "completed": completed,
                        "total": total_jobs,
                        "model_name": model_name,
                        "task_name": task["task_name"],
                        "attempt_index": attempt_index,
                    },
                    now_iso(),
                )

        jobs = [
            asyncio.create_task(run_job(model_name, task, attempt_index))
            for model_name in solver_models
            for task in tasks
            for attempt_index in range(1, repeat_count + 1)
        ]
        await asyncio.gather(*jobs)
        return sorted(results, key=lambda row: (row["model_name"], row["task_name"], row["metadata"].get("attempt_index", 0)))

    def _analyze(self, candidate: dict[str, Any], evaluations: list[dict[str, Any]]) -> dict[str, Any]:
        total = len(evaluations)
        failures = sum(1 for evaluation in evaluations if not evaluation["success"])
        failure_rate = failures / total if total else 0.0

        by_model: dict[str, list[dict[str, Any]]] = defaultdict(list)
        by_task: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for evaluation in evaluations:
            by_model[evaluation["model_name"]].append(evaluation)
            by_task[evaluation["task_name"]].append(evaluation)

        hardest_models = []
        model_summary: dict[str, Any] = {}
        for model_name, rows in by_model.items():
            success_count = sum(1 for row in rows if row["success"])
            pass_rate = success_count / len(rows) if rows else 0.0
            if pass_rate <= 0.25:
                hardest_models.append(model_name)
            model_summary[model_name] = {
                "success_count": success_count,
                "total": len(rows),
                "pass_rate": round(pass_rate, 3),
            }

        task_summary: dict[str, Any] = {}
        for task_name, rows in by_task.items():
            success_count = sum(1 for row in rows if row["success"])
            task_summary[task_name] = {
                "success_count": success_count,
                "total": len(rows),
                "pass_rate": round(success_count / len(rows), 3) if rows else 0.0,
            }

        archived = (
            failure_rate >= 0.55
            and candidate["solvable_score"] >= 0.5
            and candidate["similarity_score"] >= 0.6
            and candidate["novelty_score"] >= 0.35
        )
        return {
            "failure_rate": round(failure_rate, 3),
            "archived": archived,
            "status": "archived" if archived else "discarded",
            "metadata": {
                **candidate.get("metadata", {}),
                "hardest_models": hardest_models,
                "total_failures": failures,
                "total_evals": total,
                "prior_boundary": candidate["similarity_score"] >= 0.75 and candidate["conflict_score"] >= 0.65,
                "model_summary": model_summary,
                "task_summary": task_summary,
            },
        }

    async def _run_iteration(self, manual: bool) -> None:
        async with self._iteration_lock:
            state = store.get_loop_state()
            iteration = int(state.get("iteration", 0)) + 1
            parent = self._choose_parent()
            candidate = self._generate_candidate(iteration, parent)
            materialize_candidate_bundle(candidate, parent_name=parent.get("name") if parent else None, evaluations=[], analysis={"stage": "generated"})
            store.insert_candidate(candidate)
            store.update_candidate_outcome(
                candidate["id"],
                failure_rate=0.0,
                archived=False,
                status="evaluating",
                metadata={**candidate["metadata"], "progress": {"completed": 0, "total": 0}},
            )
            store.set_loop_state(
                status="running" if self._running or manual else "idle",
                iteration=iteration,
                note=f"Iteration {iteration} generated {candidate['name']}",
            )
            store.insert_event(
                "candidate_generated",
                {
                    "iteration": iteration,
                    "candidate_id": candidate["id"],
                    "name": candidate["name"],
                    "strategy_family": candidate["metadata"].get("strategy_family"),
                    "strategy_leaf": candidate["metadata"].get("strategy_leaf"),
                    "parent": parent.get("name") if parent else None,
                    "manual": manual,
                },
                now_iso(),
            )

            evaluations = await self._evaluate_candidate(candidate, iteration)
            analysis = self._analyze(candidate, evaluations)
            materialize_candidate_bundle(
                candidate,
                parent_name=parent.get("name") if parent else None,
                evaluations=evaluations,
                analysis=analysis,
            )
            store.update_candidate_outcome(
                candidate["id"],
                failure_rate=analysis["failure_rate"],
                archived=analysis["archived"],
                status=analysis["status"],
                metadata=analysis["metadata"],
            )
            store.insert_event(
                "benchmark_completed",
                {
                    "iteration": iteration,
                    "candidate_id": candidate["id"],
                    "failure_rate": analysis["failure_rate"],
                    "archived": analysis["archived"],
                    "hardest_models": analysis["metadata"].get("hardest_models", []),
                    "total_evals": analysis["metadata"].get("total_evals", 0),
                },
                now_iso(),
            )
            if analysis["archived"]:
                store.insert_event(
                    "archive_updated",
                    {
                        "iteration": iteration,
                        "candidate_id": candidate["id"],
                        "message": f"{candidate['name']} entered the hardest-language archive",
                    },
                    now_iso(),
                )
