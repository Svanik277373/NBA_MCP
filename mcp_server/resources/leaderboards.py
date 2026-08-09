"""MCP resources exposing current-season leaderboards for context injection.

Registered onto the FastMCP instance in mcp_server/server.py under the
`nba://leaderboards/...` URI scheme. Wired to real nba_api data — no
balldontlie fallback here since balldontlie's free tier can't serve
league-wide per-game stats either (see data_sources/balldontlie_client.py).
"""

from __future__ import annotations

import asyncio

from mcp_server.data_sources import nba_api_client as nba
from mcp_server.tools.stats_tools import DEFAULT_SEASON
from mcp_server.utils import nba_headshot_url


async def scoring_leaders() -> dict:
    """Top scorers league-wide for the current season (points per game)."""
    leaders = await asyncio.to_thread(nba.get_scoring_leaders, DEFAULT_SEASON, 5)
    for entry in leaders:
        entry["photo_url"] = nba_headshot_url(entry["player_id"])
    return {
        "season": DEFAULT_SEASON,
        "category": "points_per_game",
        "leaders": leaders,
        "source": "nba_api",
    }


async def advanced_leaders() -> dict:
    """Top players league-wide by advanced efficiency metrics (PIE-based
    impact score standing in for Hollinger PER, TS%) — see the comment in
    data_sources/nba_api_client.py's get_player_season_stats for why."""
    leaders = await asyncio.to_thread(nba.get_advanced_leaders, DEFAULT_SEASON, 5)
    for entry in leaders:
        entry["photo_url"] = nba_headshot_url(entry["player_id"])
    return {
        "season": DEFAULT_SEASON,
        "categories": ["per", "ts_pct"],
        "leaders": leaders,
        "source": "nba_api",
    }
