"""NBA Scout Agent — MCP server entrypoint.

Exposes structured NBA stats tools, RAG tools over a scouting-notes corpus,
and current-season leaderboard resources. Run directly for stdio transport
(the way the agent backend spawns it):

    python -m mcp_server.server
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from mcp_server.resources.leaderboards import advanced_leaders, scoring_leaders
from mcp_server.tools.rag_tools import get_similar_historical_players, search_scouting_context
from mcp_server.tools.stats_tools import (
    compare_players,
    get_player_game_log,
    get_player_stats,
    get_team_roster,
    get_team_schedule,
    search_players_by_criteria,
)

mcp = FastMCP(
    name="nba-scout-agent",
    instructions=(
        "Tools for scouting NBA players: structured season/game stats "
        "(get_player_stats, get_player_game_log, search_players_by_criteria, "
        "get_team_roster, compare_players, get_team_schedule) and semantic "
        "search over written scouting notes (search_scouting_context, "
        "get_similar_historical_players). Use stats tools for numbers, RAG "
        "tools for playing-style narrative and historical comps, and both "
        "together for questions that need explanation behind the numbers."
    ),
)

# --- Structured stats tools -------------------------------------------------
mcp.add_tool(get_player_stats)
mcp.add_tool(get_player_game_log)
mcp.add_tool(search_players_by_criteria)
mcp.add_tool(get_team_roster)
mcp.add_tool(compare_players)
mcp.add_tool(get_team_schedule)

# --- RAG tools ---------------------------------------------------------------
mcp.add_tool(search_scouting_context)
mcp.add_tool(get_similar_historical_players)

# --- Resources ---------------------------------------------------------------
mcp.resource(
    "nba://leaderboards/scoring",
    name="scoring_leaders",
    description="Current-season league scoring leaders (points per game).",
    mime_type="application/json",
)(scoring_leaders)

mcp.resource(
    "nba://leaderboards/advanced",
    name="advanced_leaders",
    description="Current-season league leaders in advanced efficiency metrics (PER, TS%).",
    mime_type="application/json",
)(advanced_leaders)


if __name__ == "__main__":
    mcp.run()
