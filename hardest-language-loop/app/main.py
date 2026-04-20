from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from . import store
from .engine import AgentLoopService

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(title="Hardest Language Loop", version="0.1.0")
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


@app.get("/api/candidates")
async def api_candidates(limit: int = 50) -> JSONResponse:
    return JSONResponse({"items": store.list_candidates(limit=limit)})


@app.get("/api/candidates/{candidate_id}")
async def api_candidate(candidate_id: str) -> JSONResponse:
    item = store.get_candidate(candidate_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Candidate not found")
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
