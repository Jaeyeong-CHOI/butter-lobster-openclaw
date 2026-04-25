# Reproducibility Protocol

_Last updated: 2026-04-25_

## Goal

The language-search loop should not depend on one lucky agent generation. Another researcher should be able to:

1. run the same fixed seed-catalog search,
2. replay the exact candidate languages from a prior agent run,
3. verify that the benchmark/problem set and candidate set are identical,
4. compare solver failure rates across runs.

Hosted LLM APIs may still change over time, so the target is **reproducible candidate/search setup and comparable aggregate rankings**, not byte-identical model responses. Local vLLM solver endpoints are recorded with base URLs in run artifacts.

---

## Reproducibility features

Every `scripts/explore_languages.py` run writes:

- `manifest.json` — run id, timestamp, settings, solver model pool.
- `strategy_tree.json` — full tree state and result history.
- `events.jsonl` — append-only event log.
- `artifacts/candidate_languages.json` — exact candidate language specs.
- `artifacts/problem_set.json` — exact public+hidden benchmark cases.
- `artifacts/prompts/*.json` — exact solver prompts sent per evaluation.
- `artifacts/evaluations/*.json` — solver output, validation results, retry notes.
- `artifacts/candidate_result_summary.json` — aggregate pass/fail summaries by candidate, model, and problem.
- `artifacts/expansion_plan.json` — result-guided diversity expansion candidates for the next loop round.
- `artifacts/summary.json` — aggregate failure rates and hashes.
- `artifacts/reproducibility.json` — seed, CLI args, candidate/problem hashes, git info, code fingerprints, replay command.
- `artifacts/replay_command.txt` — command to replay the exact candidate set.

Fresh runs are stored under `loop_result/v0`, `loop_result/v1`, ... by default. The next version is chosen automatically. Use `--result-root <path>` to override the root.

Important hashes:

- `candidate_set_hash`: hash of the ordered candidate language specs.
- `problem_set_hash`: hash of all benchmark problems and hidden tests.
- per-candidate `candidate_hash`: hash of each individual language spec.

---

## Three run modes

### 1) Agent discovery mode

Uses the language-designer model to propose candidates, then evaluates them.

```bash
python3 scripts/explore_languages.py --candidate-source agent --candidates 6 --problem-limit 6 --seed 20260424 --parallel-workers 8
```

This is useful for discovery, but candidate generation can vary by model/provider/version. For paper-grade reproduction, save and replay `artifacts/candidate_languages.json`.

### 2) Fixed seed-catalog mode

Uses the deterministic built-in seed catalog, bypassing stochastic candidate generation while still evaluating solver models.

```bash
python3 scripts/explore_languages.py --candidate-source seed --candidates 6 --problem-limit 6 --seed 20260424 --parallel-workers 8
```

This is the baseline reproducibility run. Candidate order and candidate hashes should match across machines using the same code revision.

### 3) Exact candidate replay mode

Replays a prior run's exact candidate languages.

```bash
python3 scripts/explore_languages.py \
  --candidate-source file \
  --candidate-file loop_result/<version>/artifacts/candidate_languages.json \
  --candidates 6 \
  --problem-limit 6 \
  --seed 20260424 \
  --parallel-workers 8
```

This is the preferred way to reproduce a reported discovery run.

### 4) Resume an existing version folder

Continue an existing result folder instead of creating a new `vN`:

```bash
python3 scripts/explore_languages.py --resume --run-id v0
```

If `--run-id` is omitted, `--resume` resumes the latest version. When resuming and no `--candidate-source` is provided, an existing `artifacts/candidate_languages.json` is reused automatically. Previously successful evaluations are skipped, so interrupted runs can continue in place.

### Result-guided tree expansion

By default, an evaluation run appends up to 25 new candidate languages after the batch:

```bash
python3 scripts/explore_languages.py --resume --run-id v0 --expand-after-eval 25
```

The expansion policy uses tree-recorded failure rates to exploit neighborhoods around hard candidates while adding a diversity bonus for underrepresented semantic families. Set `--expand-after-eval 0` for a pure evaluation pass with no new candidates.

---

## Compare two runs

```bash
python3 scripts/compare_runs.py loop_result/<baseline_version> loop_result/<replay_version>
```

The comparison reports:

- whether `candidate_set_hash` matches,
- whether `problem_set_hash` matches,
- whether each candidate hash matches,
- failure-rate deltas per candidate.

A reproducibility claim should report at least:

```text
candidate_set_hash: ...
problem_set_hash: ...
code commit: ...
solver models: gpt-5.5, gpt-4o-mini, gemma-4-31b-it, qwen3.6-27b
repeats: 10 per candidate/problem/model
temperature: 0.0
parallel workers: 8 by default
candidate source: seed_catalog or candidate_file
```

---

## Recommended paper-grade protocol

For any headline result:

1. Run discovery once or several times with `--candidate-source agent`.
2. Select top candidates by failure rate and diversity, not manually by taste.
3. Commit/save the exact `candidate_languages.json` used for the reported result.
4. Replay the candidates with `--candidate-source file` in a fresh run.
5. Report both the discovery result and replay result.
6. Include `candidate_set_hash`, `problem_set_hash`, run IDs, and solver model settings.
7. If hosted model outputs drift, report confidence intervals over repeated replay runs rather than claiming byte-identical reproduction.

---

## Current caution

The current benchmark still uses a small toy JSON-AST language and 6 implementation problems. The reproducibility scaffold is in place, but stronger evidence will require:

- more problem families,
- repeated runs,
- held-out problems,
- prompt paraphrase controls,
- explicit distinction between semantic failures and interface/JSON parse failures.
