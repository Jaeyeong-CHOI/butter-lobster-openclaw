# Python-first agent prompts and settings

> Clean-slate scaffold created on 2026-04-24.

## Files

- `llm_failure_pl/agents/language_designer.py` — Agent A, candidate language generator + strategy-tree editor.
- `llm_failure_pl/agents/solver.py` — Agent B, JSON-AST program solver.
- `llm_failure_pl/agents/curator.py` — Agent C, experiment-result curator.
- `llm_failure_pl/strategy_tree.py` — tree creation, mutation, and result aggregation.
- `llm_failure_pl/interpreter.py` — Python JSON-AST interpreter for toy languages.
- `llm_failure_pl/data_store.py` — file-based run store with manifest/tree/events/artifacts.
- `llm_failure_pl/secrets.py` — local `.env` loader and masked API-key status helpers.
- `scripts/run_agent_smoke.py` — local smoke test; no model/API call.
- `scripts/check_secrets.py` — verify which provider keys are configured without printing raw secrets.
- `scripts/explore_languages.py` — API-backed language-search pilot over candidate semantics, solver models, and the problem set.
- `scripts/compare_runs.py` — compare candidate/problem hashes and failure-rate deltas across runs.

## Agent configuration

Defaults are in `llm_failure_pl/settings.py`.

| Agent | Role | Model | Temperature | Thinking | Output |
|---|---|---:|---:|---|---|
| `language_designer` | Generate candidate languages and maintain the strategy tree | `gpt-5.5` | `0.8` | `extra_high` | JSON object |
| `solver` default | Solve tasks by producing JSON AST programs | `gpt-5.5` | `0.0` | `medium` | JSON object |
| `curator` | Read results and recommend tree edits | `gpt-5.5` | `0.3` | `high` | JSON object |

Solver benchmark pool:

| Provider | Model | Temperature | Thinking | Repeats |
|---|---:|---:|---|---:|
| `openai` | `gpt-5.5` | `0.0` | `medium` | `10` |
| `openai` | `gpt-4o-mini` | `0.0` | `medium` | `10` |
| `vllm` | `gemma-4-31b-it` @ `http://100.78.221.93:8000/v1` | `0.0` | `off` | `10` |
| `vllm` | `qwen3.6-27b` @ `http://100.78.221.93:8001/v1` | `0.0` | `off` | `10` |

Local vLLM solver endpoints use OpenAI-compatible `/chat/completions` with `VLLM_API_KEY=EMPTY` by default. Qwen is configured with `extra_body={"chat_template_kwargs": {"enable_thinking": false}}` so the solver benchmark does not spend tokens/time in thinking mode.

Each solver model is run `10` times for every candidate/problem pair. Solver evaluations run concurrently by default with `RunSettings.max_parallel_solver_requests=8`; override per run with `--parallel-workers N`.

Default implementation problem set:

| Problem ID | Purpose |
|---|---|
| `abs-int` | Baseline branching/arithmetic sanity check |
| `max-two` | Baseline comparison check |
| `clamp-0-10` | Nested branch check |
| `sign-bucket` | Multi-way branch/equality check |
| `empty-token-bonus` | Candidate-language truthiness trap |
| `empty-guarded-select` | Hidden empty-value truthiness trap |

The current set has 6 problems and 55 public+hidden reference tests.
Run `python3 scripts/export_problem_set.py` to materialize a local preview at `data/problem_set_preview.json`.

`dry_run=True` by default in settings, but `scripts/explore_languages.py` calls the configured API unless `--no-api` is passed. For reproducibility, use `--candidate-source seed` for deterministic seed-catalog candidates or `--candidate-source file --candidate-file ...` to replay a prior run exactly.

## API key management

Use `.env.example` as the committed template and `.env` for local secrets.

```bash
cp .env.example .env
# fill OPENAI_API_KEY / ANTHROPIC_API_KEY / GOOGLE_API_KEY locally
python3 scripts/check_secrets.py
# VLLM_API_KEY can remain EMPTY for the local 100.78.221.93 servers.
```

`llm_failure_pl/secrets.py` masks keys when reporting status and never needs real keys committed to git.

## Minimal prompt policy

The first version intentionally avoids heavy language-generation rules. The only hard requirements are:

1. Keep the candidate executable by the Python JSON-AST interpreter.
2. Maintain the strategy tree through auditable operations.
3. Return machine-readable JSON.

## Agent A system prompt

```text
You are the Language Designer agent.
Your job is to propose candidate programming-language semantics that may expose LLM failure.
Keep the language executable by the provided Python JSON-AST interpreter.
Maintain a strategy tree: create, revise, pause, or extend strategy nodes based on results.
Do not assume the best answer is Python-near. Explore broadly across semantic families while keeping each candidate auditable.
Prefer one clear hypothesis per candidate, but preserve diversity across the tree.
Return JSON only.
```

## Agent B system prompt

```text
You are the Solver agent.
Given a candidate language spec, a JSON-AST interpreter contract, and a task, produce a JSON AST program.
Do not write free-form source code. Return JSON only.
```

## Agent C system prompt

```text
You are the Curator agent.
Read experiment results and recommend what to do with the strategy tree next.
Prefer small auditable edits: add_child, mutate_node, or record_result.
Return JSON only.
```

## Strategy-tree operations

Supported operations are deliberately small:

```json
{"op": "add_child", "parent_id": "...", "title": "...", "hypothesis": "...", "tags": ["..."], "note": "..."}
{"op": "mutate_node", "node_id": "...", "title": "...", "hypothesis": "...", "status": "active|paused|retired", "add_tags": ["..."], "remove_tags": ["..."], "note": "..."}
{"op": "record_result", "node_id": "...", "result": {"case_id": "...", "success": false, "note": "..."}}
```

## Run smoke test

```bash
cd hardest-language-loop
python3 scripts/run_agent_smoke.py
```

This creates `data/smoke_runs/vN/` with:

- `strategy_tree.json`
- `events.jsonl`
- `artifacts/language_spec.json`
- `artifacts/interpreter_results.json`
- rendered prompts for all three agents
