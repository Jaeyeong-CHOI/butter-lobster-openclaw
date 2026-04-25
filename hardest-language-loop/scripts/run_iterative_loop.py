#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def candidate_count(run_dir: Path) -> int:
    candidate_path = run_dir / "artifacts" / "candidate_languages.json"
    if not candidate_path.exists():
        return 0
    data = load_json(candidate_path)
    if isinstance(data, dict):
        data = data.get("candidate_languages", [])
    return len(data) if isinstance(data, list) else 0


def summary_snapshot(run_dir: Path) -> dict[str, Any]:
    summary_path = run_dir / "artifacts" / "summary.json"
    if not summary_path.exists():
        return {}
    summary = load_json(summary_path)
    return {
        "run_id": summary.get("run_id"),
        "run_dir": summary.get("run_dir"),
        "candidate_count": summary.get("candidate_count"),
        "initial_candidate_count": summary.get("initial_candidate_count"),
        "expanded_candidate_count": summary.get("expanded_candidate_count"),
        "problem_count": summary.get("problem_count"),
        "requested_evaluations": summary.get("requested_evaluations"),
        "skipped_existing_evaluations": summary.get("skipped_existing_evaluations"),
        "completed_model_requests": summary.get("completed_model_requests"),
        "infrastructure_errors": summary.get("infrastructure_errors"),
        "candidate_set_hash": summary.get("candidate_set_hash"),
        "result_summary": summary.get("result_summary"),
        "expansion_plan": {
            "requested": (summary.get("expansion_plan") or {}).get("requested"),
            "selected": (summary.get("expansion_plan") or {}).get("selected"),
            "reason": (summary.get("expansion_plan") or {}).get("reason"),
        },
    }


def write_state(run_dir: Path, state: dict[str, Any]) -> None:
    artifacts = run_dir / "artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)
    state["updated_at_unix"] = time.time()
    (artifacts / "iterative_loop_state.json").write_text(
        json.dumps(state, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def run_step(cmd: list[str], *, log_path: Path, env: dict[str, str] | None = None) -> int:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("w", encoding="utf-8") as log:
        log.write("$ " + " ".join(cmd) + "\n\n")
        log.flush()
        proc = subprocess.run(cmd, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, text=True, env=env)
        log.write(f"\n[exit_code] {proc.returncode}\n")
    return proc.returncode


def build_explore_cmd(
    *,
    result_root: str,
    run_id: str,
    problem_limit: int,
    parallel_workers: int,
    expand_after_eval: int,
    candidate_count_arg: int | None = None,
    candidate_source: str | None = None,
    resume: bool = False,
    seed: int | None = None,
    max_evaluations: int = 0,
    no_api: bool = False,
) -> list[str]:
    cmd = [
        sys.executable,
        "scripts/explore_languages.py",
        "--result-root",
        result_root,
        "--run-id",
        run_id,
        "--problem-limit",
        str(problem_limit),
        "--parallel-workers",
        str(parallel_workers),
        "--expand-after-eval",
        str(expand_after_eval),
    ]
    if resume:
        cmd.append("--resume")
    if candidate_count_arg is not None:
        cmd.extend(["--candidates", str(candidate_count_arg)])
    if candidate_source:
        cmd.extend(["--candidate-source", candidate_source])
    if seed is not None:
        cmd.extend(["--seed", str(seed)])
    if max_evaluations > 0:
        cmd.extend(["--max-evaluations", str(max_evaluations)])
    if no_api:
        cmd.append("--no-api")
    return cmd


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the language loop in batches: generate N, evaluate, summarize, expand, repeat."
    )
    parser.add_argument("--run-id", default="v1")
    parser.add_argument("--result-root", default="loop_result")
    parser.add_argument("--target-candidates", type=int, default=300)
    parser.add_argument("--batch-size", type=int, default=10)
    parser.add_argument("--problem-limit", type=int, default=6)
    parser.add_argument("--parallel-workers", type=int, default=8)
    parser.add_argument("--candidate-source", choices=["agent", "seed", "file"], default="agent")
    parser.add_argument("--seed", type=int)
    parser.add_argument("--resume", action="store_true", help="Continue an existing run folder instead of creating it from scratch.")
    parser.add_argument("--no-final-evaluate", action="store_true", help="Stop once target candidates exist; do not evaluate the final appended batch.")
    parser.add_argument("--max-evaluations-per-iteration", type=int, default=0, help="Testing/debug cap passed to explore_languages.py.")
    parser.add_argument("--no-api", action="store_true", help="Testing/debug mode: do not call model APIs.")
    args = parser.parse_args()

    if args.batch_size <= 0:
        parser.error("--batch-size must be positive")
    if args.target_candidates <= 0:
        parser.error("--target-candidates must be positive")

    result_root = Path(args.result_root)
    if not result_root.is_absolute():
        result_root = ROOT / result_root
    run_dir = result_root / args.run_id
    log_root = result_root / f"_{args.run_id}_iteration_logs"
    state: dict[str, Any] = {
        "schema_version": 1,
        "run_id": args.run_id,
        "result_root": str(result_root),
        "target_candidates": args.target_candidates,
        "batch_size": args.batch_size,
        "problem_limit": args.problem_limit,
        "parallel_workers": args.parallel_workers,
        "candidate_source": args.candidate_source,
        "max_evaluations_per_iteration": args.max_evaluations_per_iteration,
        "no_api": args.no_api,
        "final_evaluate": not args.no_final_evaluate,
        "iterations": [],
        "status": "running",
        "started_at_unix": time.time(),
    }

    if run_dir.exists() and not args.resume:
        raise SystemExit(f"Run folder already exists: {run_dir}. Use --resume to continue it.")

    iteration = 0
    try:
        if not run_dir.exists():
            initial_count = min(args.batch_size, args.target_candidates)
            initial_expand = 0 if initial_count >= args.target_candidates else min(args.batch_size, args.target_candidates - initial_count)
            cmd = build_explore_cmd(
                result_root=str(result_root),
                run_id=args.run_id,
                candidate_source=args.candidate_source,
                candidate_count_arg=initial_count,
                problem_limit=args.problem_limit,
                parallel_workers=args.parallel_workers,
                expand_after_eval=initial_expand,
                seed=args.seed,
                max_evaluations=args.max_evaluations_per_iteration,
                no_api=args.no_api,
            )
            log_path = log_root / f"iteration_{iteration:03d}_initial.log"
            code = run_step(cmd, log_path=log_path, env=os.environ.copy())
            snapshot = summary_snapshot(run_dir)
            state["iterations"].append(
                {"iteration": iteration, "phase": "initial", "exit_code": code, "log_path": str(log_path), "summary": snapshot}
            )
            write_state(run_dir, state)
            if code != 0:
                raise RuntimeError(f"initial iteration failed with exit code {code}; see {log_path}")
            iteration += 1

        while candidate_count(run_dir) < args.target_candidates:
            current_count = candidate_count(run_dir)
            expand = min(args.batch_size, args.target_candidates - current_count)
            cmd = build_explore_cmd(
                result_root=str(result_root),
                run_id=args.run_id,
                resume=True,
                candidate_count_arg=current_count,
                problem_limit=args.problem_limit,
                parallel_workers=args.parallel_workers,
                expand_after_eval=expand,
                seed=args.seed,
                max_evaluations=args.max_evaluations_per_iteration,
                no_api=args.no_api,
            )
            log_path = log_root / f"iteration_{iteration:03d}_expand_to_{current_count + expand:04d}.log"
            code = run_step(cmd, log_path=log_path, env=os.environ.copy())
            snapshot = summary_snapshot(run_dir)
            state["iterations"].append(
                {
                    "iteration": iteration,
                    "phase": "evaluate_and_expand",
                    "candidate_count_before": current_count,
                    "expand_after_eval": expand,
                    "exit_code": code,
                    "log_path": str(log_path),
                    "summary": snapshot,
                }
            )
            write_state(run_dir, state)
            if code != 0:
                raise RuntimeError(f"iteration {iteration} failed with exit code {code}; see {log_path}")
            iteration += 1

        if not args.no_final_evaluate:
            current_count = candidate_count(run_dir)
            cmd = build_explore_cmd(
                result_root=str(result_root),
                run_id=args.run_id,
                resume=True,
                candidate_count_arg=current_count,
                problem_limit=args.problem_limit,
                parallel_workers=args.parallel_workers,
                expand_after_eval=0,
                seed=args.seed,
                max_evaluations=args.max_evaluations_per_iteration,
                no_api=args.no_api,
            )
            log_path = log_root / f"iteration_{iteration:03d}_final_evaluate.log"
            code = run_step(cmd, log_path=log_path, env=os.environ.copy())
            snapshot = summary_snapshot(run_dir)
            state["iterations"].append(
                {
                    "iteration": iteration,
                    "phase": "final_evaluate",
                    "candidate_count_before": current_count,
                    "expand_after_eval": 0,
                    "exit_code": code,
                    "log_path": str(log_path),
                    "summary": snapshot,
                }
            )
            write_state(run_dir, state)
            if code != 0:
                raise RuntimeError(f"final evaluation failed with exit code {code}; see {log_path}")

        state["status"] = "completed"
        state["completed_at_unix"] = time.time()
        state["final_candidate_count"] = candidate_count(run_dir)
        state["final_summary"] = summary_snapshot(run_dir)
        write_state(run_dir, state)
        print(json.dumps(state, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:  # noqa: BLE001 - persist failure state for resume/debugging
        state["status"] = "failed"
        state["error"] = f"{type(exc).__name__}: {exc}"
        state["failed_at_unix"] = time.time()
        if run_dir.exists():
            state["final_candidate_count"] = candidate_count(run_dir)
            state["final_summary"] = summary_snapshot(run_dir)
            write_state(run_dir, state)
        print(json.dumps(state, ensure_ascii=False, indent=2))
        return 1
    finally:
        if run_dir.exists():
            artifacts_log_root = run_dir / "artifacts" / "iteration_logs"
            if log_root.exists():
                artifacts_log_root.parent.mkdir(parents=True, exist_ok=True)
                if artifacts_log_root.exists():
                    shutil.rmtree(artifacts_log_root)
                shutil.copytree(log_root, artifacts_log_root)


if __name__ == "__main__":
    raise SystemExit(main())
