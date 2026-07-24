"""OptoPuts backend (PLAN task I1.2): the one endpoint the frontend calls.

POST /chat streams CONTRACTS §3 SSE from the agent loop; GET /panel hydrates
page load; GET/POST /settings hold the user's regime bands; GET /health.
Protocol-identical to mock_server.py — the frontend must not care which one
it is talking to.

Run: cd backend && uv run uvicorn app:app --reload   (port 8000)
"""
from __future__ import annotations

import asyncio
import json
import uuid
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

import config
from agent import settlement
from agent.loop import run_turn
from agent.tools import build_panel, default_state

_pending_chain: list[dict] = []  # settle events from the worker, flushed on next stream


@asynccontextmanager
async def lifespan(_app: FastAPI):
    worker = asyncio.create_task(settlement.worker_loop(_pending_chain))
    yield
    worker.cancel()


app = FastAPI(title="OptoPuts backend", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)

_state = default_state()
_conversations: dict[str, list] = {}
_last_panel: dict | None = None


class ChatRequest(BaseModel):
    message: str
    conversation_id: str | None = None


class SettingsUpdate(BaseModel):
    regime_bands: dict[str, float] | None = None


def _sse(event: str, data) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


@app.post("/chat")
async def chat(req: ChatRequest):
    conv_id = req.conversation_id or uuid.uuid4().hex[:12]
    messages = _conversations.setdefault(conv_id, [])
    messages.append({"role": "user", "content": req.message})

    async def stream():
        global _last_panel
        while _pending_chain:  # settlements that fired between turns
            yield _sse("chain", _pending_chain.pop(0))
        try:
            async for event in run_turn(messages, _state):
                if event["event"] == "panel":
                    _last_panel = event["data"]
                yield _sse(event["event"], event["data"])
        except Exception as exc:
            yield _sse("error", {"message": str(exc)})
        yield _sse("done", {"conversation_id": conv_id})

    return StreamingResponse(stream(), media_type="text/event-stream")


@app.get("/panel")
async def panel():
    global _last_panel
    if _last_panel is None:
        _last_panel = build_panel(_state)
    return _last_panel


@app.get("/settings")
async def get_settings():
    return _state["settings"]


@app.post("/settings")
async def post_settings(update: SettingsUpdate):
    global _last_panel
    if update.regime_bands is not None:
        calm = update.regime_bands.get("calm")
        elevated = update.regime_bands.get("elevated")
        if calm is None or elevated is None or not (0 < calm < elevated < 1):
            raise HTTPException(422, "regime_bands need 0 < calm < elevated < 1")
        _state["settings"]["regime_bands"] = {"calm": calm, "elevated": elevated}
        _last_panel = build_panel(_state)  # regime recomputed under new bands
    return _state["settings"]


@app.get("/health")
async def health():
    return {"ok": True, "offline_mode": config.OFFLINE_MODE}


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
