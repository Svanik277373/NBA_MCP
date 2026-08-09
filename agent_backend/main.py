"""FastAPI entrypoint for the NBA Scout Agent.

Run with:
    uvicorn agent_backend.main:app --reload --port 8000
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import anthropic
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

load_dotenv()

from agent_backend import db
from agent_backend.agent.loop import run_agent
from agent_backend.agent.mcp_client import MCPToolClient
from agent_backend.db import RequestStats

mcp_client: MCPToolClient | None = None
anthropic_client: anthropic.AsyncAnthropic | None = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    global mcp_client, anthropic_client
    db.init_db()
    mcp_client = MCPToolClient()
    await mcp_client.connect()
    anthropic_client = anthropic.AsyncAnthropic()
    print(f"[startup] connected to MCP server, {len(mcp_client.anthropic_tools)} tools loaded")
    yield
    await mcp_client.close()


app = FastAPI(title="NBA Scout Agent", lifespan=lifespan)

# Dev-server origins for the Vite frontend (default port 5173) and the
# separate admin dashboard, if served from a different port. This is
# VITE_API_BASE_URL's counterpart from the *frontend's* side — this var is
# the *backend's* own address, not a CORS origin, so it's not used here.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    query: str


@app.get("/health")
async def health() -> dict:
    return {
        "status": "ok",
        "tools_loaded": len(mcp_client.anthropic_tools) if mcp_client else 0,
        "model": os.environ.get("AGENT_MODEL", "claude-sonnet-5"),
    }


@app.post("/chat")
async def chat(req: ChatRequest) -> EventSourceResponse:
    assert mcp_client is not None and anthropic_client is not None, "app not started via lifespan"

    stats = RequestStats(query=req.query, model=os.environ.get("AGENT_MODEL", "claude-sonnet-5"))

    async def event_generator() -> AsyncIterator[dict[str, str]]:
        try:
            async for event in run_agent(req.query, mcp_client, anthropic_client, stats=stats):
                yield event
        except Exception as exc:  # noqa: BLE001 — log then let the stream close; client sees a truncated response
            stats.status = "error"
            stats.error_message = str(exc)
            raise
        finally:
            db.record_request(stats)

    return EventSourceResponse(event_generator())


@app.get("/admin/requests")
async def admin_requests(limit: int = 50) -> list[dict]:
    """Recent chat requests with per-request token/cost/latency detail."""
    return db.get_recent_requests(limit=limit)


@app.get("/admin/stats")
async def admin_stats() -> dict:
    """Aggregate totals across all logged requests (tokens, cost, tool usage)."""
    return db.get_aggregate_stats()
