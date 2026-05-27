"""
Web frontend for the Ollama + MCP Local Song Dataset RAG Agent.

Runs a FastAPI server that serves a chat-like web UI and handles
conversation turns over WebSockets.

Usage::

    uvicorn web_app:app --reload

Then open http://localhost:8000 in your browser.

The WebSocket protocol uses JSON messages in both directions:

Client → server
    {"message": "<user text>"}

Server → client (one or more per turn)
    {"type": "tool_call",   "name": "…", "args": {…}}
    {"type": "tool_result", "name": "…", "content": "…"}
    {"type": "answer",      "content": "…"}
    {"type": "error",       "content": "…"}
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from fastmcp import Client

from mcp_server import mcp
from ollama_client import run_agent

logger = logging.getLogger(__name__)

app = FastAPI(title="Local Song Dataset RAG Agent")

_STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")


@app.get("/", response_class=FileResponse)
async def index() -> FileResponse:
    """Serve the chat UI."""
    return FileResponse(str(_STATIC_DIR / "index.html"))


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    """Handle chat messages over WebSocket."""
    await websocket.accept()

    client = Client(mcp)

    async def send(payload: dict) -> None:
        await websocket.send_text(json.dumps(payload, ensure_ascii=False))

    async def on_event(event: dict) -> None:
        """Forward tool-call progress events to the browser."""
        await send(event)

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                data = json.loads(raw)
                user_message = str(data.get("message", "")).strip()
            except (json.JSONDecodeError, AttributeError):
                await send({"type": "error", "content": "Invalid JSON from client."})
                continue

            if not user_message:
                continue

            try:
                answer = await run_agent(
                    user_message,
                    client,
                    on_event=on_event,
                )
                await send({"type": "answer", "content": answer})
            except (SystemExit, KeyboardInterrupt):
                raise
            except Exception as exc:  # noqa: BLE001
                logger.exception("Error running agent: %s", exc)
                await send({"type": "error", "content": str(exc)})

    except WebSocketDisconnect:
        pass
