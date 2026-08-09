"""SSE event shapes streamed to the frontend.

Every event is `{"event": <type>, "data": <json string>}`, consumed by
sse-starlette's EventSourceResponse. Event types:

- thinking      — a chunk of Claude's (summarized) reasoning before it acts
- tool_call     — Claude is invoking a tool: name, category, arguments
- tool_result   — that tool call's result: truncated preview + full parsed result
- final_answer  — the synthesized markdown answer; terminal event on success
- error         — something went wrong; terminal event on failure
"""

from __future__ import annotations

import json
from typing import Any


def sse_event(event_type: str, data: dict[str, Any]) -> dict[str, str]:
    return {"event": event_type, "data": json.dumps(data)}


def preview(text: str, max_chars: int = 220) -> str:
    collapsed = " ".join(text.split())
    if len(collapsed) <= max_chars:
        return collapsed
    return collapsed[:max_chars].rsplit(" ", 1)[0] + "..."
