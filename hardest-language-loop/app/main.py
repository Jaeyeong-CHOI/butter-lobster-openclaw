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


def _agent_config_response(settings: dict[str, object]) -> dict[str, object]:
    return {
        "agent_a": {
            "model": settings.get("agent_a_model", "gpt-5.4"),
            "temperature": settings.get("agent_a_temperature", 0.7),
            "thinking": settings.get("agent_a_thinking", "high"),
            "api_key": store.get_agent_api_key_status("agent_a"),
        },
        "agent_b": {
            "model": settings.get("agent_b_model", "gpt-5.4"),
            "temperature": settings.get("agent_b_temperature", 0.2),
            "thinking": settings.get("agent_b_thinking", "medium"),
            "api_key": store.get_agent_api_key_status("agent_b"),
        },
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
            "agents": _agent_config_response(settings),
            "openai_models": list(OPENAI_MODEL_CATALOG.keys()),
            "thinking_options": list(THINKING_OPTIONS),
        }
    )


@app.post("/api/config")
async def api_config_update(payload: dict = Body(...)) -> JSONResponse:
    agents_payload = payload.get("agents") or {}
    changed: dict[str, list[str]] = {"agent_a": [], "agent_b": []}

    for agent_name in ("agent_a", "agent_b"):
        agent_payload = agents_payload.get(agent_name)
        if not isinstance(agent_payload, dict):
            continue

        model = agent_payload.get("model")
        if model is not None:
            if model not in OPENAI_MODEL_CATALOG:
                raise HTTPException(status_code=400, detail=f"Unknown model for {agent_name}")
            store.set_setting(f"{agent_name}_model", model)
            changed[agent_name].append("model")

        temperature = agent_payload.get("temperature")
        if temperature is not None:
            try:
                normalized_temp = _coerce_temperature(temperature)
            except (TypeError, ValueError) as exc:
                raise HTTPException(status_code=400, detail=f"Invalid temperature for {agent_name}: {exc}") from exc
            store.set_setting(f"{agent_name}_temperature", normalized_temp)
            changed[agent_name].append("temperature")

        thinking = agent_payload.get("thinking")
        if thinking is not None:
            if thinking not in THINKING_OPTIONS:
                raise HTTPException(status_code=400, detail=f"Invalid thinking value for {agent_name}")
            store.set_setting(f"{agent_name}_thinking", thinking)
            changed[agent_name].append("thinking")

        api_key = agent_payload.get("api_key")
        if isinstance(api_key, str) and api_key.strip():
            store.set_agent_api_key(agent_name, api_key.strip())
            changed[agent_name].append("api_key")

        if agent_payload.get("clear_api_key"):
            store.clear_agent_api_key(agent_name)
            changed[agent_name].append("api_key_cleared")

    flattened = {agent: keys for agent, keys in changed.items() if keys}
    if flattened:
        store.insert_event(
            "config_updated",
            {
                "message": "Agent settings updated",
                "changes": flattened,
                "note": "Applies to new iterations. Reset loop if you want a clean history under the new configuration.",
            },
            datetime.now(timezone.utc).isoformat(),
        )

    settings = store.get_settings()
    return JSONResponse(
        {
            "ok": True,
            "settings": settings,
            "agents": _agent_config_response(settings),
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
