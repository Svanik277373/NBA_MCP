"""The agent loop: Claude + MCP tools, streamed as SSE events.

Manual tool-use loop (not the SDK's beta tool runner) because we need to
emit an SSE event around each individual tool call/result as it happens,
which the tool runner's higher-level iteration doesn't expose cleanly.
"""

from __future__ import annotations

import json
import os
from collections.abc import AsyncIterator
from typing import Any

import anthropic

from agent_backend.agent.mcp_client import MCPToolClient
from agent_backend.agent.sse import preview, sse_event
from agent_backend.db import RequestStats

MODEL = os.environ.get("AGENT_MODEL", "claude-sonnet-5")
MAX_TOKENS = 4096
MAX_TOOL_ITERATIONS = 8

SYSTEM_PROMPT = """You are an NBA scouting assistant with two kinds of tools:

1. Structured stats tools (get_player_stats, get_player_game_log,
   search_players_by_criteria, get_team_roster, compare_players,
   get_team_schedule) — for numbers: season averages, game logs, filtering
   players by stat thresholds, rosters, schedules.
2. RAG tools (search_scouting_context, get_similar_historical_players) —
   for playing-style narrative, scheme fit, and historical comps, drawn
   from written scouting notes. Use these for "why" and "how" questions
   that raw stats can't answer on their own.

Decide which tool(s) a question actually needs — don't call a tool whose
result you won't use. Many questions need both kinds: e.g. "why has X's
efficiency dropped" needs a game log or season comparison (stats) AND
scouting context explaining the shift (RAG). Call multiple tools when the
question calls for it, in whatever order makes sense; you don't need to
front-load every possible tool call before reasoning about the results.

When citing scouting context from search_scouting_context, reference the
source_file so the reader knows where a claim came from.

Render side-by-side stat comparisons as markdown tables. Keep the final
answer focused: lead with the direct answer, then support it with the
specific numbers or scouting detail that justify it."""


def _build_tool_result_message(tool_use_id: str, content: str, is_error: bool = False) -> dict[str, Any]:
    block: dict[str, Any] = {"type": "tool_result", "tool_use_id": tool_use_id, "content": content}
    if is_error:
        block["is_error"] = True
    return block


async def run_agent(
    user_query: str,
    mcp_client: MCPToolClient,
    client: anthropic.AsyncAnthropic,
    stats: RequestStats | None = None,
) -> AsyncIterator[dict[str, str]]:
    messages: list[dict[str, Any]] = [{"role": "user", "content": user_query}]

    for _ in range(MAX_TOOL_ITERATIONS):
        response = await client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT,
            thinking={"type": "adaptive", "display": "summarized"},
            tools=mcp_client.anthropic_tools,
            messages=messages,
        )
        if stats is not None:
            stats.add_usage(response.usage)

        for block in response.content:
            if block.type == "thinking" and block.thinking:
                yield sse_event("thinking", {"text": block.thinking})

        messages.append({"role": "assistant", "content": response.content})

        tool_use_blocks = [b for b in response.content if b.type == "tool_use"]

        if response.stop_reason != "tool_use" or not tool_use_blocks:
            final_text = "".join(b.text for b in response.content if b.type == "text")
            yield sse_event("final_answer", {"text": final_text})
            return

        tool_result_blocks: list[dict[str, Any]] = []
        for block in tool_use_blocks:
            category = mcp_client.tool_category(block.name)
            if stats is not None:
                stats.tool_calls.append(block.name)
            yield sse_event(
                "tool_call",
                {"tool_name": block.name, "category": category, "arguments": block.input},
            )
            try:
                result_text = await mcp_client.call_tool(block.name, block.input)
                yield sse_event(
                    "tool_result",
                    {
                        "tool_name": block.name,
                        "category": category,
                        "result_preview": preview(result_text),
                        "result": json.loads(result_text),
                    },
                )
                tool_result_blocks.append(_build_tool_result_message(block.id, result_text))
            except Exception as exc:  # noqa: BLE001 — surface any tool failure to Claude + the UI
                error_message = str(exc)
                yield sse_event(
                    "tool_result",
                    {"tool_name": block.name, "category": category, "error": error_message},
                )
                tool_result_blocks.append(
                    _build_tool_result_message(block.id, error_message, is_error=True)
                )

        messages.append({"role": "user", "content": tool_result_blocks})

    error_message = f"Stopped after {MAX_TOOL_ITERATIONS} tool-call rounds without a final answer."
    if stats is not None:
        stats.status = "error"
        stats.error_message = error_message
    yield sse_event("error", {"message": error_message})
