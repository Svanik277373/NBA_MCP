"""Long-lived MCP client connection to the NBA Scout Agent MCP server.

The server is spawned as a subprocess over stdio and kept alive for the
lifetime of the FastAPI process (see agent_backend/main.py's lifespan) —
spawning a fresh subprocess per chat request would be needlessly slow.
"""

from __future__ import annotations

import os
import sys
from contextlib import AsyncExitStack
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# Tool names served by the RAG half of the MCP server — used by the agent
# loop to tag each tool call as "stats" or "rag" for the frontend's
# reasoning-trace UI (different icon/color per source).
RAG_TOOL_NAMES = {"search_scouting_context", "get_similar_historical_players"}


class MCPToolClient:
    """Wraps a single stdio MCP session: connect once, call_tool many times."""

    def __init__(self) -> None:
        self._exit_stack = AsyncExitStack()
        self._session: ClientSession | None = None
        self.anthropic_tools: list[dict[str, Any]] = []

    async def connect(self) -> None:
        # `or sys.executable`, not `.get(..., default)` — an *empty* env var
        # (as opposed to an unset one) should still fall back correctly.
        # Defaulting to sys.executable (this process's own interpreter)
        # rather than the bare string "python" matters: on a machine with
        # multiple Python installs, "python" resolves via PATH and can
        # silently land on an interpreter that doesn't have this project's
        # venv packages installed — sys.executable can't make that mistake.
        command = os.environ.get("MCP_SERVER_COMMAND") or sys.executable
        args = (os.environ.get("MCP_SERVER_ARGS") or "-m mcp_server.server").split()
        server_params = StdioServerParameters(command=command, args=args, env=dict(os.environ))

        read_stream, write_stream = await self._exit_stack.enter_async_context(
            stdio_client(server_params)
        )
        self._session = await self._exit_stack.enter_async_context(
            ClientSession(read_stream, write_stream)
        )
        await self._session.initialize()

        tools_result = await self._session.list_tools()
        self.anthropic_tools = [
            {
                "name": tool.name,
                "description": tool.description or "",
                "input_schema": tool.inputSchema,
            }
            for tool in tools_result.tools
        ]

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> str:
        """Call an MCP tool, returning its text content as a raw JSON string
        (our tools all return a single TextContent block — see
        mcp_server/server.py — so this doesn't handle image/embedded
        content blocks)."""
        if self._session is None:
            raise RuntimeError("MCPToolClient.connect() must be called before call_tool()")
        result = await self._session.call_tool(name, arguments)
        text_parts = [block.text for block in result.content if block.type == "text"]
        text = "\n".join(text_parts)
        if result.isError:
            raise RuntimeError(f"Tool '{name}' returned an error: {text}")
        return text

    def tool_category(self, name: str) -> str:
        return "rag" if name in RAG_TOOL_NAMES else "stats"

    async def close(self) -> None:
        await self._exit_stack.aclose()
        self._session = None
