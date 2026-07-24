"""Mock chat backend: replays fixtures/chat_scripts.json over the exact SSE
protocol from docs/CONTRACTS.md §3. PLAN task S0.5.

The frontend is built against this and must not care whether it's talking to
the mock or the real app.py. Keep it dumb: keyword-match a script, replay its
events with a small delay.

Run: cd backend && uv run python mock_server.py   (port 8000)
"""
import asyncio
import json

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from config import FIXTURES_DIR

SCRIPTS = json.loads((FIXTURES_DIR / "chat_scripts.json").read_text())
DELAY_S = 0.25

app = FastAPI(title="OptoPuts mock server")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)

_state = {
    "panel": SCRIPTS["initial_panel"],
    "settings": {"regime_bands": {"calm": 0.33, "elevated": 0.66}},
}


class ChatRequest(BaseModel):
    message: str
    conversation_id: str | None = None


def pick_script(message: str) -> dict:
    text = message.lower()
    for script in SCRIPTS["scripts"]:
        if any(kw in text for kw in script["match"]):
            return script
    return next(s for s in SCRIPTS["scripts"] if s["name"] == SCRIPTS["default"])


async def replay(script: dict):
    for item in script["events"]:
        event, data = item["event"], item["data"]
        if event == "panel":
            _state["panel"] = data
        yield f"event: {event}\ndata: {json.dumps(data)}\n\n"
        # stream tokens fast, pause on tool calls/chain events like real work
        await asyncio.sleep(0.04 if event == "token" else DELAY_S)


@app.post("/chat")
async def chat(req: ChatRequest):
    return StreamingResponse(
        replay(pick_script(req.message)), media_type="text/event-stream"
    )


@app.get("/panel")
async def panel():
    return _state["panel"]


@app.get("/settings")
async def get_settings():
    return _state["settings"]


@app.post("/settings")
async def post_settings(settings: dict):
    bands = settings.get("regime_bands", {})
    calm, elevated = bands.get("calm"), bands.get("elevated")
    if calm is not None and elevated is not None:
        if not (0 < calm < elevated < 1):
            return {"error": "invalid bands: need 0 < calm < elevated < 1"}
        _state["settings"]["regime_bands"] = {"calm": calm, "elevated": elevated}
        _state["panel"]["regime"]["bands"] = dict(
            _state["settings"]["regime_bands"]
        )
    return _state["settings"]


@app.get("/health")
async def health():
    return {"ok": True, "offline_mode": True, "mock": True}


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
