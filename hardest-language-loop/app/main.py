from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncGenerator

from fastapi import Body, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from . import store
from .artifacts import load_candidate_bundle, materialize_candidate_bundle
from .engine import AgentLoopService, OPENAI_MODEL_CATALOG, THINKING_OPTIONS

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(title="Hardest Language Loop", version="0.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
loop_service = AgentLoopService()


def _config_response(settings: dict[str, object]) -> dict[str, object]:
    return {
        "agent_a": {
            "model": settings.get("agent_a_model", "gpt-5.4"),
            "temperature": settings.get("agent_a_temperature", 0.7),
            "thinking": settings.get("agent_a_thinking", "high"),
        },
        "solver_bench": {
            "enabled_models": settings.get("solver_models", list(OPENAI_MODEL_CATALOG.keys())),
            "temperature": settings.get("solver_temperature", 0.2),
            "thinking": settings.get("solver_thinking", "medium"),
            "repeat_count": settings.get("solver_repeat_count", 5),
            "parallelism": settings.get("solver_parallelism", 10),
        },
        "providers": {"openai": {"api_key": store.get_openai_api_key_status()}},
    }


def _coerce_temperature(value: object) -> float:
    temp = float(value)
    if temp < 0 or temp > 2:
        raise ValueError("temperature must be between 0 and 2")
    return round(temp, 3)


@app.on_event("startup")
async def startup() -> None:
    store.init_db()
    loop_service.bootstrap()


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/overview")
async def api_overview() -> JSONResponse:
    return JSONResponse(store.get_overview())


@app.get("/api/config")
async def api_config() -> JSONResponse:
    settings = store.get_settings()
    return JSONResponse(
        {
            "settings": settings,
            "config": _config_response(settings),
            "openai_models": list(OPENAI_MODEL_CATALOG.keys()),
            "thinking_options": list(THINKING_OPTIONS),
        }
    )


@app.post("/api/config")
async def api_config_update(payload: dict = Body(...)) -> JSONResponse:
    changed: dict[str, list[str]] = {}

    agent_a_payload = payload.get("agent_a") or payload.get("agents", {}).get("agent_a") or {}
    if isinstance(agent_a_payload, dict):
        agent_a_changes: list[str] = []
        model = agent_a_payload.get("model")
        if model is not None:
            if model not in OPENAI_MODEL_CATALOG:
                raise HTTPException(status_code=400, detail="Unknown model for agent_a")
            store.set_setting("agent_a_model", model)
            agent_a_changes.append("model")
        temperature = agent_a_payload.get("temperature")
        if temperature is not None:
            try:
                normalized_temp = _coerce_temperature(temperature)
            except (TypeError, ValueError) as exc:
                raise HTTPException(status_code=400, detail=f"Invalid temperature for agent_a: {exc}") from exc
            store.set_setting("agent_a_temperature", normalized_temp)
            agent_a_changes.append("temperature")
        thinking = agent_a_payload.get("thinking")
        if thinking is not None:
            if thinking not in THINKING_OPTIONS:
                raise HTTPException(status_code=400, detail="Invalid thinking value for agent_a")
            store.set_setting("agent_a_thinking", thinking)
            agent_a_changes.append("thinking")
        if agent_a_changes:
            changed["agent_a"] = agent_a_changes

    solver_payload = payload.get("solver_bench") or payload.get("agents", {}).get("solver_bench") or {}
    if isinstance(solver_payload, dict):
        solver_changes: list[str] = []
        enabled_models = solver_payload.get("enabled_models")
        if enabled_models is not None:
            if not isinstance(enabled_models, list) or not enabled_models:
                raise HTTPException(status_code=400, detail="enabled_models must be a non-empty list")
            unknown = [model for model in enabled_models if model not in OPENAI_MODEL_CATALOG]
            if unknown:
                raise HTTPException(status_code=400, detail=f"Unknown models in solver bench: {unknown}")
            store.set_setting("solver_models", enabled_models)
            solver_changes.append("enabled_models")
        temperature = solver_payload.get("temperature")
        if temperature is not None:
            try:
                normalized_temp = _coerce_temperature(temperature)
            except (TypeError, ValueError) as exc:
                raise HTTPException(status_code=400, detail=f"Invalid temperature for solver_bench: {exc}") from exc
            store.set_setting("solver_temperature", normalized_temp)
            solver_changes.append("temperature")
        thinking = solver_payload.get("thinking")
        if thinking is not None:
            if thinking not in THINKING_OPTIONS:
                raise HTTPException(status_code=400, detail="Invalid thinking value for solver_bench")
            store.set_setting("solver_thinking", thinking)
            solver_changes.append("thinking")
        repeat_count = solver_payload.get("repeat_count")
        if repeat_count is not None:
            repeats = int(repeat_count)
            if repeats < 1 or repeats > 20:
                raise HTTPException(status_code=400, detail="repeat_count must be between 1 and 20")
            store.set_setting("solver_repeat_count", repeats)
            solver_changes.append("repeat_count")
        parallelism = solver_payload.get("parallelism")
        if parallelism is not None:
            parallel = int(parallelism)
            if parallel < 1 or parallel > 50:
                raise HTTPException(status_code=400, detail="parallelism must be between 1 and 50")
            store.set_setting("solver_parallelism", parallel)
            solver_changes.append("parallelism")
        if solver_changes:
            changed["solver_bench"] = solver_changes

    providers_payload = payload.get("providers") or {}
    openai_payload = providers_payload.get("openai") if isinstance(providers_payload, dict) else None
    if isinstance(openai_payload, dict):
        provider_changes: list[str] = []
        api_key = openai_payload.get("api_key")
        if isinstance(api_key, str) and api_key.strip():
            store.set_openai_api_key(api_key.strip())
            provider_changes.append("api_key")
        if openai_payload.get("clear_api_key"):
            store.clear_openai_api_key()
            provider_changes.append("api_key_cleared")
        if provider_changes:
            changed["openai"] = provider_changes

    if changed:
        store.insert_event(
            "config_updated",
            {
                "message": "Loop configuration updated",
                "changes": changed,
                "note": "Applies to new iterations. Reset loop if you want a clean history under the new configuration.",
            },
            datetime.now(timezone.utc).isoformat(),
        )

    settings = store.get_settings()
    return JSONResponse(
        {
            "ok": True,
            "settings": settings,
            "config": _config_response(settings),
            "openai_models": list(OPENAI_MODEL_CATALOG.keys()),
            "thinking_options": list(THINKING_OPTIONS),
        }
    )


@app.get("/api/candidates")
async def api_candidates(limit: int = 50) -> JSONResponse:
    return JSONResponse({"items": store.list_candidates(limit=limit)})


@app.get("/api/candidates/{candidate_id}")
async def api_candidate(candidate_id: str) -> JSONResponse:
    item = store.get_candidate(candidate_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Candidate not found")
    parent_name = None
    if item.get("parent_id"):
        parent = store.get_candidate(item["parent_id"])
        parent_name = parent.get("name") if parent else None
    materialize_candidate_bundle(
        item,
        parent_name=parent_name,
        evaluations=item.get("evaluations", []),
        analysis={
            "status": item.get("status"),
            "archived": item.get("archived"),
            "failure_rate": item.get("failure_rate"),
            "metadata": item.get("metadata", {}),
        },
    )
    item["artifacts"] = load_candidate_bundle(item)
    return JSONResponse(item)


@app.get("/api/events")
async def api_events(after_id: int = 0, limit: int = 100) -> JSONResponse:
    return JSONResponse({"items": store.list_events(after_id=after_id, limit=limit)})


@app.get("/api/events/stream")
async def api_events_stream() -> StreamingResponse:
    async def event_gen() -> AsyncGenerator[str, None]:
        last_id = 0
        while True:
            events = store.list_events(after_id=last_id, limit=100)
            if events:
                for event in events:
                    last_id = max(last_id, int(event["id"]))
                    yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
            await asyncio.sleep(1)

    return StreamingResponse(event_gen(), media_type="text/event-stream")


@app.post("/api/loop/start")
async def api_start() -> JSONResponse:
    return JSONResponse(await loop_service.start())


@app.post("/api/loop/pause")
async def api_pause() -> JSONResponse:
    return JSONResponse(await loop_service.pause())


@app.post("/api/loop/step")
async def api_step() -> JSONResponse:
    return JSONResponse(await loop_service.step_once())


@app.post("/api/loop/reset")
async def api_reset() -> JSONResponse:
    return JSONResponse(await loop_service.reset())
