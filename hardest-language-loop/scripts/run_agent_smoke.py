#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from llm_failure_pl.agents import CuratorAgent, LanguageDesignerAgent, SolverAgent
from llm_failure_pl.data_store import FileStore
from llm_failure_pl.problems import default_problem_set, validate_problem_set
from llm_failure_pl.settings import default_settings


def main() -> int:
    settings = default_settings()
    settings.data_root = "data/smoke_runs"
    store = FileStore(settings.data_root)
    paths = store.start_run(settings=settings)

    designer = LanguageDesignerAgent(settings.language_designer)
    solver = SolverAgent(settings.solver)
    curator = CuratorAgent(settings.curator)

    tree = designer.new_strategy_tree()
    node = tree.add_child(
        tree.root_id,
        title="Truthiness twist",
        hypothesis="A Python-looking branch can fail if truthiness is subtly changed.",
        tags=["truthiness", "minimal-rule"],
        note="Smoke-test seed node; future nodes should be created by Agent A outputs.",
    )

    problems = default_problem_set()
    validation = validate_problem_set(problems)
    results = [result for item in validation for result in item["results"]]
    for item in validation:
        tree.record_result(
            node.id,
            {
                "case_id": item["problem_id"],
                "success": item["success"],
                "note": f"Reference validation over {item['num_tests']} tests",
            },
        )

    store.save_tree(paths, tree)
    store.save_json_artifact(
        paths,
        "problem_set.json",
        [problem.to_dict(include_reference=True, include_hidden=True) for problem in problems],
    )
    store.save_json_artifact(paths, "reference_validation.json", validation)
    store.save_json_artifact(paths, "language_spec.json", problems[0].language_spec.to_dict())
    store.save_json_artifact(paths, "interpreter_results.json", results)
    store.save_json_artifact(paths, "prompts/language_designer.json", designer.render(tree, validation))
    solver_prompts = [
        solver.render(problem.language_spec.to_dict(), problem.to_solver_task(), solver_model=model.to_dict())
        for problem in problems
        for model in settings.solver_models
    ]
    store.save_json_artifact(paths, "prompts/solver_models.json", solver_prompts)
    # Keep a single prompt file for quick inspection; the full pool is in solver_models.json.
    store.save_json_artifact(paths, "prompts/solver.json", solver_prompts[0])
    store.save_json_artifact(paths, "prompts/curator.json", curator.render(tree, results))
    store.append_event(paths, "smoke_test_completed", {"results": results, "strategy_node_id": node.id})

    print(
        json.dumps(
            {
                "run_id": paths.run_id,
                "run_dir": str(paths.root),
                "problem_count": len(problems),
                "test_count": len(results),
                "reference_success": all(item["success"] for item in validation),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if all(item["success"] for item in validation) else 1


if __name__ == "__main__":
    raise SystemExit(main())
