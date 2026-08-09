"""SQLite-backed request/token usage log, for the admin dashboard.

Deliberately not a heavier persistence layer (Postgres, etc.) — this is a
single-process demo app, and sqlite3 (stdlib, zero new dependency) is
sufficient for logging request history and serving simple aggregate stats.

No auth on the /admin endpoints that read this — consistent with the rest
of the app ("no auth needed" per spec). In a real deployment, gate these
behind auth before exposing them.
"""

from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

DB_PATH = Path(__file__).parent / "admin.db"

# USD per 1M tokens. claude-sonnet-5 intro pricing ($2/$10) runs through
# 2026-08-31; standard rates ($3/$15) shown here — swap if you want the
# intro numbers reflected in the cost estimate.
PRICING_PER_MTOK: dict[str, dict[str, float]] = {
    "claude-sonnet-5": {"input": 3.00, "output": 15.00, "cache_write": 3.75, "cache_read": 0.30},
    "claude-opus-5": {"input": 5.00, "output": 25.00, "cache_write": 6.25, "cache_read": 0.50},
    "claude-haiku-4-5": {"input": 1.00, "output": 5.00, "cache_write": 1.25, "cache_read": 0.10},
}
_DEFAULT_PRICING = PRICING_PER_MTOK["claude-sonnet-5"]


@dataclass
class RequestStats:
    """Accumulates usage across every Claude API call made while answering
    one /chat request (a single chat turn is usually several API calls —
    one per tool-use round-trip). Populated in-place by agent/loop.py,
    persisted by db.record_request() once the SSE stream finishes.
    """

    query: str
    model: str
    started_at: float = field(default_factory=time.monotonic)
    api_calls: int = 0
    tool_calls: list[str] = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_tokens: int = 0
    cache_read_tokens: int = 0
    status: str = "ok"
    error_message: str | None = None

    def add_usage(self, usage: Any) -> None:
        self.api_calls += 1
        self.input_tokens += usage.input_tokens or 0
        self.output_tokens += usage.output_tokens or 0
        self.cache_creation_tokens += getattr(usage, "cache_creation_input_tokens", 0) or 0
        self.cache_read_tokens += getattr(usage, "cache_read_input_tokens", 0) or 0

    def estimated_cost_usd(self) -> float:
        p = PRICING_PER_MTOK.get(self.model, _DEFAULT_PRICING)
        cost = (
            self.input_tokens * p["input"]
            + self.output_tokens * p["output"]
            + self.cache_creation_tokens * p["cache_write"]
            + self.cache_read_tokens * p["cache_read"]
        ) / 1_000_000
        return round(cost, 6)

    def latency_ms(self) -> int:
        return round((time.monotonic() - self.started_at) * 1000)


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                query TEXT NOT NULL,
                model TEXT NOT NULL,
                status TEXT NOT NULL,
                error_message TEXT,
                latency_ms INTEGER NOT NULL,
                api_calls INTEGER NOT NULL,
                tool_calls TEXT NOT NULL,
                input_tokens INTEGER NOT NULL,
                output_tokens INTEGER NOT NULL,
                cache_creation_tokens INTEGER NOT NULL,
                cache_read_tokens INTEGER NOT NULL,
                estimated_cost_usd REAL NOT NULL
            )
            """
        )


def record_request(stats: RequestStats) -> None:
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO requests (
                created_at, query, model, status, error_message, latency_ms,
                api_calls, tool_calls, input_tokens, output_tokens,
                cache_creation_tokens, cache_read_tokens, estimated_cost_usd
            ) VALUES (datetime('now'), ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                stats.query[:500],
                stats.model,
                stats.status,
                stats.error_message,
                stats.latency_ms(),
                stats.api_calls,
                json.dumps(stats.tool_calls),
                stats.input_tokens,
                stats.output_tokens,
                stats.cache_creation_tokens,
                stats.cache_read_tokens,
                stats.estimated_cost_usd(),
            ),
        )


def get_recent_requests(limit: int = 50) -> list[dict[str, Any]]:
    with _connect() as conn:
        rows = conn.execute("SELECT * FROM requests ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    return [{**dict(row), "tool_calls": json.loads(row["tool_calls"])} for row in rows]


def get_aggregate_stats() -> dict[str, Any]:
    with _connect() as conn:
        summary = conn.execute(
            """
            SELECT
                COUNT(*) AS total_requests,
                COALESCE(SUM(input_tokens), 0) AS total_input_tokens,
                COALESCE(SUM(output_tokens), 0) AS total_output_tokens,
                COALESCE(SUM(cache_creation_tokens), 0) AS total_cache_creation_tokens,
                COALESCE(SUM(cache_read_tokens), 0) AS total_cache_read_tokens,
                COALESCE(SUM(estimated_cost_usd), 0) AS total_estimated_cost_usd,
                COALESCE(AVG(latency_ms), 0) AS avg_latency_ms,
                COALESCE(SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END), 0) AS error_count
            FROM requests
            """
        ).fetchone()
        tool_rows = conn.execute("SELECT tool_calls FROM requests").fetchall()

    tool_call_counts: dict[str, int] = {}
    for row in tool_rows:
        for name in json.loads(row["tool_calls"]):
            tool_call_counts[name] = tool_call_counts.get(name, 0) + 1

    return {**dict(summary), "tool_call_counts": tool_call_counts}
