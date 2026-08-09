"""Eval harness: run the fixed query set against the live agent and score
tool-selection correctness.

This does NOT judge answer quality — only whether the agent reached for
the right tool(s) for each query category (stats-only, RAG-only, hybrid).
A query passes if every tool in its `expected_tools` list was called at
least once; calling additional tools beyond that is reported but not
treated as a failure, since a reasonable agent may pull in extra context.

Hits the real Claude API and real MCP tools — costs a small amount per
run (see agent_backend/db.py's pricing table).

Usage:
    python -m agent_backend.eval.run_eval
"""

from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path

import anthropic
from dotenv import load_dotenv

from agent_backend.agent.loop import run_agent
from agent_backend.agent.mcp_client import MCPToolClient

EVAL_QUERIES_PATH = Path(__file__).parent / "eval_queries.json"


async def run_one(mcp_client: MCPToolClient, client: anthropic.AsyncAnthropic, case: dict) -> dict:
    called_tools: list[str] = []
    final_answer: str | None = None
    error: str | None = None
    started = time.monotonic()

    async for event in run_agent(case["query"], mcp_client, client):
        # sse_event() (agent_backend/agent/sse.py) returns {"event": ..., "data": ...}
        # — matching sse-starlette's wire format, not {"type": ...}.
        if event["event"] == "tool_call":
            called_tools.append(json.loads(event["data"])["tool_name"])
        elif event["event"] == "final_answer":
            final_answer = json.loads(event["data"])["text"]
        elif event["event"] == "error":
            error = json.loads(event["data"])["message"]

    expected = set(case["expected_tools"])
    actual = set(called_tools)
    missing = expected - actual
    extra = actual - expected

    return {
        "id": case["id"],
        "category": case["category"],
        "query": case["query"],
        "expected_tools": sorted(expected),
        "called_tools": called_tools,
        "missing": sorted(missing),
        "extra": sorted(extra),
        "passed": not missing and error is None,
        "error": error,
        "has_final_answer": final_answer is not None,
        "elapsed_s": round(time.monotonic() - started, 1),
    }


async def main() -> int:
    load_dotenv()
    cases = json.loads(EVAL_QUERIES_PATH.read_text(encoding="utf-8"))

    mcp_client = MCPToolClient()
    await mcp_client.connect()
    client = anthropic.AsyncAnthropic()

    results = []
    for case in cases:
        print(f"running {case['id']} [{case['category']}] — {case['query'][:60]}...")
        result = await run_one(mcp_client, client, case)
        results.append(result)
        status = "PASS" if result["passed"] else "FAIL"
        print(f"  {status}  called={result['called_tools']}  ({result['elapsed_s']}s)")
        if result["missing"]:
            print(f"    missing expected tool(s): {result['missing']}")
        if result["extra"]:
            print(f"    (also called, not required): {result['extra']}")
        if result["error"]:
            print(f"    error: {result['error']}")

    await mcp_client.close()

    passed = sum(1 for r in results if r["passed"])
    total = len(results)
    print(f"\n{passed}/{total} passed")

    by_category: dict[str, list[dict]] = {}
    for r in results:
        by_category.setdefault(r["category"], []).append(r)
    for category, rows in sorted(by_category.items()):
        cat_passed = sum(1 for r in rows if r["passed"])
        print(f"  {category}: {cat_passed}/{len(rows)}")

    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
