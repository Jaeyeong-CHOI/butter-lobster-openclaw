# Hardest Language Loop

Web dashboard + loop backend for exploring the hardest programming languages for current LLMs.

## What this MVP includes
- Agent-loop backend scaffold (Generator / Solver Bench / Analyzer-Curator)
- SQLite-backed run history
- Live web dashboard with SSE updates
- Start / pause / single-step / reset controls
- Candidate archive and evaluation drill-down

## What is mocked for now
- Model calls are simulated
- Candidate language generation is heuristic/simulated
- Interpreter-as-spec execution path is scaffolded but not yet connected to real interpreters

## Run
```bash
cd hardest-language-loop
uv sync
uv run uvicorn app.main:app --host 127.0.0.1 --port 8787 --reload
```

Then open:
- http://127.0.0.1:8787

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

## Next integration points
- Replace `generate_candidate()` in `app/engine.py`
- Replace `simulate_solver()` with real model wrappers + interpreter execution
- Wire real Agent B model output into `program_attempts.json`
