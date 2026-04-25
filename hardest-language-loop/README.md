# LLM Failure PL

Clean-slate Python-first scaffold for exploring programming-language semantics that make LLMs fail.

## Current focus

- Agents are plain Python files.
- The interpreter is Python-based and executes JSON AST programs.
- Experiment state is stored as versioned files under `loop_result/v0`, `loop_result/v1`, ... by default.
- The language designer agent owns a strategy tree and can create/mutate nodes based on results.
- The language designer uses `thinking=extra_high`.
- Solver benchmarking always includes `gpt-5.5`, `gpt-4o-mini`, local `gemma-4-31b-it` (`100.78.221.93:8000`), and local `qwen3.6-27b` (`100.78.221.93:8001`) with `temperature=0.0`, repeated 10 times per candidate/problem/model.
- Local vLLM solver calls use OpenAI-compatible chat completions and run in parallel by default (`max_parallel_solver_requests=8`); qwen disables thinking via `chat_template_kwargs.enable_thinking=false`.
- The current default problem is an empty-string truthiness checksum trap.
- The current benchmark set has 6 implementation problems / 55 reference tests.

## Layout

```text
llm_failure_pl/
  agents/
    language_designer.py
    solver.py
    curator.py
  interpreter.py
  problems.py
  strategy_tree.py
  data_store.py
  secrets.py
  prompts.py
  settings.py

docs/
  agent-prompts-and-settings.md
  related-work-agent-search.md
  reproducibility.md

scripts/
  check_secrets.py
  compare_runs.py
  explore_languages.py
  export_problem_set.py
  run_agent_smoke.py
```

## API keys

```bash
cp .env.example .env
# edit .env locally
python3 scripts/check_secrets.py
```

`.env` is gitignored. Do not commit real API keys.

## Smoke test

```bash
python3 scripts/run_agent_smoke.py
```

## Problem set preview

```bash
python3 scripts/export_problem_set.py
```

## Language search pilot

```bash
python3 scripts/explore_languages.py --candidate-source agent --candidates 3 --problem-limit 6 --parallel-workers 8
```

This asks the language designer for candidate semantic rules, evaluates each candidate with the configured solver models, validates JSON-AST programs with the Python interpreter, and stores a scored strategy tree under the next `loop_result/vN/` folder.

After an evaluation batch, the loop also writes aggregate result summaries back into the strategy tree and appends result-guided diverse candidates for the next round (`--expand-after-eval 25` by default, set `0` to disable). The result artifacts are:

- `artifacts/candidate_result_summary.json`
- `artifacts/expansion_plan.json`
- updated `strategy_tree.json` node artifacts/metrics

Fresh runs auto-create the next version folder (`v0`, `v1`, ...). To continue an existing folder, use:

```bash
python3 scripts/explore_languages.py --resume --run-id v0 --candidate-source file --candidate-file loop_result/v0/artifacts/candidate_languages.json
```

If `--resume` is used without `--run-id`, the latest `vN` folder is resumed. If no `--candidate-source` is provided while resuming and `candidate_languages.json` already exists, the script reuses that candidate file by default and skips completed successful evaluations.

## Iterative 10-at-a-time loop

For the main search loop, run 10 candidates at a time: generate/evaluate/review/expand, repeated until a target archive size is reached.

```bash
python3 scripts/run_iterative_loop.py \
  --run-id v1 \
  --target-candidates 300 \
  --batch-size 10 \
  --problem-limit 6 \
  --parallel-workers 8
```

This writes progress to `loop_result/v1/artifacts/iterative_loop_state.json` and per-iteration logs to `loop_result/v1/artifacts/iteration_logs/`.

For reproducible runs, use the deterministic seed catalog or replay a saved candidate set:

```bash
python3 scripts/explore_languages.py --candidate-source seed --candidates 300 --problem-limit 6 --seed 20260424
python3 scripts/explore_languages.py --candidate-source file --candidate-file loop_result/<version>/artifacts/candidate_languages.json --candidates 6 --problem-limit 6 --seed 20260424
python3 scripts/compare_runs.py loop_result/<baseline_version> loop_result/<replay_version>
```

## Related work

See `docs/related-work-agent-search.md` for notes on FunSearch-style evolutionary search, language-agent tree search, automated red teaming/benchmark generation, and PL-semantics robustness work that should inform the next search-loop design.

See `docs/reproducibility.md` for the run/replay/compare protocol and the exact artifacts each run writes.
