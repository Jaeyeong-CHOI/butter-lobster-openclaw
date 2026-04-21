# Hardest Language Loop

Web dashboard + loop backend for exploring the hardest programming languages for current LLMs.

## What this MVP includes
- Agent-loop backend scaffold (Generator / Solver Bench / Analyzer-Curator)
- SQLite-backed run history
- Live web dashboard with SSE updates
- Start / pause / single-step / reset controls
- Candidate archive and evaluation drill-down
- Real JSON AST -> OCaml AST -> interpreter execution validator bridge
- Multi-model solver bench with configurable repeat count + max concurrent requests
- Automatic experiment backup snapshot before reset

## What is mocked for now
- Candidate language generation is still heuristic/simulated
- If no OpenAI API key is configured, solver calls fall back to simulated output
- Agent A search / scoring heuristics are not yet learned from real experiment history

## Run
```bash
cd hardest-language-loop
uv sync
uv run uvicorn app.main:app --host 127.0.0.1 --port 8787 --reload
```

Then open:
- http://127.0.0.1:8787

## Backup & durability

Runtime experiment data lives in:
- `data/loop.db`
- `data/candidates/`

Before a reset, the app now creates an automatic snapshot in:
- `data/backups/<timestamp>-reset/`

You can also trigger a manual backup snapshot:
```bash
cd hardest-language-loop
./scripts/backup_experiment_data.sh manual
```

This stores:
- `loop.db`
- `candidates/`
- `manifest.json`

It intentionally does **not** copy plaintext secrets.

## OCaml interpreter runtime

The generated `interpreter.ml` artifacts are intended to be directly executable with OCaml.

### Install runtime on macOS
```bash
brew install ocaml
```

### Run a generated candidate interpreter
```bash
cd hardest-language-loop
./scripts/run_candidate_interpreter.sh <candidate-id>
# or
./scripts/run_candidate_interpreter.sh "PL-010 L1"
```

This executes the candidate's `interpreter.ml` sample program through the local OCaml runtime.

### Run the JSON AST validator bridge for a candidate
```bash
cd hardest-language-loop
./scripts/run_candidate_validator.sh <candidate-id>
```

This regenerates the candidate bundle, converts `program_attempts.json` JSON AST into OCaml AST expressions, executes them through the candidate interpreter, and prints `validator_result.json`.

## Smoke test

For a quick end-to-end sanity check against a running local server:

```bash
cd hardest-language-loop
./scripts/smoke_test.py
```

This checks:
- config update
- reset
- single step
- candidate detail / artifacts
- manual backup creation

## Next integration points
- Replace `generate_candidate()` in `app/engine.py`
- Improve Agent A search heuristics from real run history
- Add richer provider support beyond shared OpenAI configuration
- Add deeper regression tests for solver bench / validator edge cases
