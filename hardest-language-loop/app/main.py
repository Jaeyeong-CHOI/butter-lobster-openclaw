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
from .engine import AgentLoopService, OPENAI_MODEL_CATALOG

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
            "openai_models": list(OPENAI_MODEL_CATALOG.keys()),
            "openai_api_key": store.get_openai_api_key_status(),
        }
    )


@app.post("/api/config")
async def api_config_update(payload: dict = Body(...)) -> JSONResponse:
    agent2_model = payload.get("agent2_model")
    openai_api_key = payload.get("openai_api_key")
    clear_openai_api_key = payload.get("clear_openai_api_key")
    if agent2_model is not None:
        if agent2_model not in OPENAI_MODEL_CATALOG:
            raise HTTPException(status_code=400, detail="Unknown Agent 2 model")
        store.set_setting("agent2_model", agent2_model)
        store.insert_event(
            "config_updated",
            {
                "message": "Agent 2 model updated",
                "agent2_model": agent2_model,
                "note": "Applies to new iterations. Reset loop for a clean benchmark history.",
            },
            datetime.now(timezone.utc).isoformat(),
        )
    if isinstance(openai_api_key, str) and openai_api_key.strip():
        store.set_openai_api_key(openai_api_key.strip())
        store.insert_event(
            "config_updated",
            {
                "message": "OpenAI API key updated",
                "configured": True,
            },
            datetime.now(timezone.utc).isoformat(),
        )
    if clear_openai_api_key:
        store.clear_openai_api_key()
        store.insert_event(
            "config_updated",
            {
                "message": "OpenAI API key cleared",
                "configured": False,
            },
            datetime.now(timezone.utc).isoformat(),
        )
    return JSONResponse({
        "ok": True,
        "settings": store.get_settings(),
        "openai_models": list(OPENAI_MODEL_CATALOG.keys()),
        "openai_api_key": store.get_openai_api_key_status(),
    })


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
