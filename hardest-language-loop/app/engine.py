from __future__ import annotations

import asyncio
import random
import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from . import store
from .artifacts import materialize_candidate_bundle

MODELS = [
    {"name": "gpt-5.4", "skill": 0.82, "prior_strength": 0.92},
    {"name": "gpt-5.4-mini", "skill": 0.69, "prior_strength": 0.78},
    {"name": "o4-mini", "skill": 0.88, "prior_strength": 0.71},
    {"name": "qwen3-32b", "skill": 0.63, "prior_strength": 0.80},
]

TASKS = [
    {"name": "abs", "entrenchment": 0.15},
    {"name": "max", "entrenchment": 0.20},
    {"name": "fib", "entrenchment": 0.92},
    {"name": "gcd", "entrenchment": 0.88},
]

MUTATIONS = [
    ("L1", "Cross-keyword remap", "Python surface mostly preserved; core keywords are remapped to conflicting tokens."),
    ("L2", "Block syntax inversion", "Function and block delimiters remain Python-near, but control-flow syntax is restructured."),
    ("L3", "Inverted-if semantics", "Conditionals execute on FALSE; comparison and boolean behavior partially conflict with Python."),
    ("L4", "Example-only semantic induction", "Rules are not stated; only interpreter code and examples imply the semantics."),
    ("L5", "Compound conflict bundle", "Keyword remapping, syntax shifts, and inverted semantics are combined in one language."),
]

SEEDS = [
    {
        "name": "Python Seed",
        "level": "Seed",
        "mutation_summary": "Baseline Python-like language with canonical semantics.",
        "interpreter_hint": "Reference seed language.",
        "similarity_score": 0.98,
        "conflict_score": 0.05,
        "solvable_score": 0.99,
        "novelty_score": 0.10,
        "failure_rate": 0.0,
        "archived": False,
        "status": "seed",
        "metadata": {"source": "seed"},
    },
    {
        "name": "L3 InvertedIf Seed",
        "level": "L3",
        "mutation_summary": "Conditionals execute when the condition is false.",
        "interpreter_hint": "Prototype based on existing confusion-language results.",
        "similarity_score": 0.93,
        "conflict_score": 0.84,
        "solvable_score": 0.80,
        "novelty_score": 0.44,
        "failure_rate": 0.68,
        "archived": True,
        "status": "archived",
        "metadata": {"source": "seed", "notes": "Initial hardest known family"},
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
        self._running = False
        self.config = LoopConfig()

    def bootstrap(self) -> None:
        total = store.get_overview()["stats"]["total_candidates"]
        if total == 0:
            for seed in SEEDS:
                candidate = {
                    **seed,
                    "id": f"seed-{uuid.uuid4().hex[:8]}",
                    "parent_id": None,
                    "created_at": now_iso(),
                }
                materialize_candidate_bundle(candidate, parent_name=None, evaluations=[], analysis={"bootstrap": True})
                store.insert_candidate(candidate)
            store.insert_event("bootstrap", {"message": "Seed languages inserted"}, now_iso())

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
        await self._run_iteration(manual=True)
        return {"ok": True, "status": "stepped"}

    async def reset(self) -> dict[str, Any]:
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
        store.reset_all()
        self.bootstrap()
        store.insert_event("loop_reset", {"message": "Loop state reset"}, now_iso())
        return {"ok": True, "status": "reset"}

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
        candidates = store.list_candidates(limit=100)
        archived = [c for c in candidates if c.get("archived")]
        pool = archived or candidates
        if not pool:
            return None
        pool = sorted(pool, key=lambda c: (c.get("failure_rate", 0), c.get("conflict_score", 0)), reverse=True)
        return random.choice(pool[: min(5, len(pool))])

    def _generate_candidate(self, iteration: int, parent: dict[str, Any] | None) -> dict[str, Any]:
        rnd = random.Random(iteration * 7919)
        level, mutation_summary, interpreter_hint = MUTATIONS[iteration % len(MUTATIONS)]
        parent_similarity = float(parent.get("similarity_score", 0.95)) if parent else 0.95
        similarity = max(0.45, min(0.98, parent_similarity + rnd.uniform(-0.08, 0.03)))
        conflict = max(0.15, min(0.98, (parent.get("conflict_score", 0.2) if parent else 0.2) + rnd.uniform(0.03, 0.15)))
        solvable = max(0.35, min(0.97, 0.92 - abs(conflict - 0.72) * 0.7 + rnd.uniform(-0.08, 0.05)))
        novelty = max(0.15, min(0.99, rnd.uniform(0.35, 0.9)))
        return {
            "id": f"cand-{uuid.uuid4().hex[:10]}",
            "parent_id": parent.get("id") if parent else None,
            "level": level,
            "name": f"PL-{iteration:03d} {level}",
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
                "python_near": similarity > 0.72,
                "task_bank": [t["name"] for t in TASKS],
            },
            "created_at": now_iso(),
        }

    def _simulate_solver(self, candidate: dict[str, Any]) -> list[dict[str, Any]]:
        rnd = random.Random(candidate["id"])
        rows = []
        for model in MODELS:
            for task in TASKS:
                prior_penalty = task["entrenchment"] * candidate["conflict_score"] * model["prior_strength"]
                capability = model["skill"] * candidate["solvable_score"]
                prompt_bonus = 0.08 if candidate["level"] in {"L1", "L2", "L3"} else -0.05
                raw = capability - prior_penalty + prompt_bonus + rnd.uniform(-0.08, 0.08)
                success = raw > 0.18
                score = max(0.0, min(1.0, 0.5 + raw))
                notes = "Fails on prior-entrenched task" if not success and task["entrenchment"] > 0.8 else ""
                rows.append(
                    {
                        "id": f"eval-{uuid.uuid4().hex[:12]}",
                        "candidate_id": candidate["id"],
                        "model_name": model["name"],
                        "task_name": task["name"],
                        "prompt_mode": "interpreter_as_spec",
                        "success": success,
                        "score": round(score, 3),
                        "notes": notes,
                        "created_at": now_iso(),
                    }
                )
        return rows

    def _analyze(self, candidate: dict[str, Any], evaluations: list[dict[str, Any]]) -> dict[str, Any]:
        total = len(evaluations)
        failures = sum(1 for e in evaluations if not e["success"])
        failure_rate = failures / total if total else 0.0
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for e in evaluations:
            grouped[e["model_name"]].append(e)
        hardest_models = []
        for model_name, rows in grouped.items():
            success_rate = sum(1 for r in rows if r["success"]) / len(rows)
            if success_rate <= 0.25:
                hardest_models.append(model_name)
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
            },
        }

    async def _run_iteration(self, manual: bool) -> None:
        state = store.get_loop_state()
        iteration = int(state.get("iteration", 0)) + 1
        parent = self._choose_parent()
        candidate = self._generate_candidate(iteration, parent)
        materialize_candidate_bundle(candidate, parent_name=parent.get("name") if parent else None, evaluations=[], analysis={"stage": "generated"})
        store.insert_candidate(candidate)
        store.set_loop_state(
            status="running" if self._running else "idle",
            iteration=iteration,
            note=f"Iteration {iteration} generated {candidate['name']}",
        )
        store.insert_event(
            "candidate_generated",
            {
                "iteration": iteration,
                "candidate_id": candidate["id"],
                "name": candidate["name"],
                "level": candidate["level"],
                "parent": parent.get("name") if parent else None,
                "manual": manual,
            },
            now_iso(),
        )
        await asyncio.sleep(0.2)
        evaluations = self._simulate_solver(candidate)
        for row in evaluations:
            store.insert_evaluation(row)
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
