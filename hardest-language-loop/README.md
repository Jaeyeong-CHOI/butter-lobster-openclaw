# LLM Failure PL

Clean-slate Python-first scaffold for exploring programming-language semantics that make LLMs fail.

## Current focus

- Agents are plain Python files.
- The interpreter is Python-based and executes JSON AST programs.
- Experiment state is stored as files, not a web UI.
- The language designer agent owns a strategy tree and can create/mutate nodes based on results.
- The language designer uses `thinking=extra_high`.
- Solver benchmarking always includes `gpt-5.4`, `gpt-4o`, local `gemma-4-31b-it` (`100.78.221.93:8000`), and local `qwen3.6-27b` (`100.78.221.93:8001`) with `temperature=0.0`, repeated 10 times per candidate/problem/model.
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

This asks the language designer for candidate semantic rules, evaluates each candidate with the configured solver models, validates JSON-AST programs with the Python interpreter, and stores a scored strategy tree under `data/runs/<run_id>/`.

For reproducible runs, use the deterministic seed catalog or replay a saved candidate set:

```bash
python3 scripts/explore_languages.py --candidate-source seed --candidates 6 --problem-limit 6 --seed 20260424
python3 scripts/explore_languages.py --candidate-source file --candidate-file data/runs/<run_id>/artifacts/candidate_languages.json --candidates 6 --problem-limit 6 --seed 20260424
python3 scripts/compare_runs.py data/runs/<baseline_run_id> data/runs/<replay_run_id>
```

## Related work

See `docs/related-work-agent-search.md` for notes on FunSearch-style evolutionary search, language-agent tree search, automated red teaming/benchmark generation, and PL-semantics robustness work that should inform the next search-loop design.

See `docs/reproducibility.md` for the run/replay/compare protocol and the exact artifacts each run writes.
