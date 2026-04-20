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

## Next integration points
- Replace `generate_candidate()` in `app/engine.py`
- Replace `simulate_solver()` with real model wrappers + interpreter execution
- Add candidate folder artifact writer (`spec.md`, `interpreter.py`, `tasks.json`)
