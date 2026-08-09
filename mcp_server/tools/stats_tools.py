"""Structured NBA stats tools.

Primary source is nba_api (wraps stats.nba.com directly, no key). On
failure, falls back to balldontlie.io where that fallback can actually
serve the data — see mcp_server/data_sources/balldontlie_client.py for
exactly which endpoints that covers on a free-tier key (schedule and
partial roster info; NOT season stats or game logs, which the free tier
doesn't expose).

nba_api itself is synchronous (built on `requests`), so every call here
goes through asyncio.to_thread to avoid blocking the MCP server's event
loop while stats.nba.com responds.
"""

from __future__ import annotations

import asyncio

from mcp_server.data_sources import balldontlie_client as bdl
from mcp_server.data_sources import nba_api_client as nba
from mcp_server.schemas import (
    AdvancedStats,
    ComparePlayersResult,
    GameLogEntry,
    PerGameStats,
    PlayerComparisonEntry,
    PlayerGameLogResult,
    PlayerSearchHit,
    PlayerSearchResult,
    PlayerStatsResult,
    RosterEntry,
    ScheduledGame,
    TeamRosterResult,
    TeamScheduleResult,
)
from mcp_server.utils import current_nba_season, nba_headshot_url

DEFAULT_SEASON = current_nba_season()


def _bdl_season_year(season: str) -> int:
    """"2024-25" -> 2024 (balldontlie identifies a season by its start year)."""
    return int(season.split("-")[0])


def _infer_nba_season(date_str: str) -> str:
    """"2025-01-09" -> "2024-25" (NBA seasons start in October, so
    Jan-Jun dates belong to the season that started the prior year)."""
    year, month = int(date_str[:4]), int(date_str[5:7])
    season_start_year = year if month >= 8 else year - 1
    return f"{season_start_year}-{str(season_start_year + 1)[-2:]}"


async def _resolve_player(player_name: str) -> tuple[int, str]:
    """Returns (player_id, source). Only nba_api can resolve a player for
    stats purposes — balldontlie resolution alone isn't useful since it
    can't serve the stats endpoints on this tier — so this doesn't fall
    back; a resolution failure here means the name genuinely wasn't found.
    """
    player_id = await asyncio.to_thread(nba.resolve_player_id, player_name)
    return player_id, "nba_api"


async def get_player_stats(player_name: str, season: str = DEFAULT_SEASON) -> dict:
    """Get a player's season averages and advanced stats.

    Args:
        player_name: Full or partial player name, e.g. "Anthony Edwards".
        season: Season string in "YYYY-YY" format, e.g. "2024-25".
    """
    player_id = await asyncio.to_thread(nba.resolve_player_id, player_name)

    try:
        stats = await asyncio.to_thread(nba.get_player_season_stats, player_id, season)
        source = "nba_api"
    except Exception as nba_exc:
        try:
            bdl_player_id = await asyncio.to_thread(bdl.resolve_player_id, player_name)
            stats = await asyncio.to_thread(bdl.get_player_season_stats, bdl_player_id, _bdl_season_year(season))
            source = "balldontlie"
        except Exception as bdl_exc:
            raise RuntimeError(
                f"nba_api failed ({nba_exc}); balldontlie fallback also failed ({bdl_exc})"
            ) from nba_exc

    if stats is None:
        raise ValueError(f"No stats found for '{player_name}' in season {season} — check spelling and season format")

    result = PlayerStatsResult(
        player_id=player_id,
        player_name=player_name,
        photo_url=nba_headshot_url(player_id),
        team=stats["team"],
        season=season,
        per_game=PerGameStats(
            games_played=stats["games_played"],
            minutes=stats["minutes"],
            points=stats["points"],
            rebounds=stats["rebounds"],
            assists=stats["assists"],
            steals=stats["steals"],
            blocks=stats["blocks"],
            turnovers=stats["turnovers"],
            fg_pct=stats["fg_pct"],
            three_pt_pct=stats["three_pt_pct"],
            ft_pct=stats["ft_pct"],
        ),
        advanced=AdvancedStats(
            per=stats.get("per", 0.0),
            ts_pct=stats.get("ts_pct", 0.0),
            usage_pct=stats.get("usage_pct", 0.0),
            offensive_rating=stats.get("offensive_rating", 0.0),
            defensive_rating=stats.get("defensive_rating", 0.0),
            win_shares=stats.get("win_shares", 0.0),
        ),
        source=source,
    )
    return result.model_dump()


async def get_player_game_log(
    player_name: str,
    season: str = DEFAULT_SEASON,
    last_n_games: int = 10,
) -> dict:
    """Get a player's game-by-game log for recent performance analysis.

    Args:
        player_name: Full or partial player name.
        season: Season string in "YYYY-YY" format.
        last_n_games: How many of the most recent games to return.
    """
    player_id, _ = await _resolve_player(player_name)

    try:
        games_raw = await asyncio.to_thread(nba.get_player_game_log, player_id, season, last_n_games)
        source = "nba_api"
    except Exception as nba_exc:
        try:
            bdl_player_id = await asyncio.to_thread(bdl.resolve_player_id, player_name)
            games_raw = await asyncio.to_thread(
                bdl.get_player_game_log, bdl_player_id, _bdl_season_year(season), last_n_games
            )
            source = "balldontlie"
        except Exception as bdl_exc:
            raise RuntimeError(
                f"nba_api failed ({nba_exc}); balldontlie fallback also failed ({bdl_exc})"
            ) from nba_exc

    games = [GameLogEntry(**g) for g in games_raw]
    result = PlayerGameLogResult(
        player_id=player_id,
        player_name=player_name,
        photo_url=nba_headshot_url(player_id),
        season=season,
        games=games,
        source=source,
    )
    return result.model_dump()


async def search_players_by_criteria(
    position: str | None = None,
    max_age: int | None = None,
    min_stat_thresholds: dict[str, float] | None = None,
    season: str = DEFAULT_SEASON,
) -> dict:
    """Filter league-wide players by position, age, and minimum stat thresholds.

    Args:
        position: "G", "F", or "C" (nba_api's roster data only carries
            coarse position categories — G/F/C and combos like "G-F" —
            not the fine-grained PG/SG/SF/PF distinction; "SG" or "PG"
            are accepted as aliases for "G", "SF"/"PF" for "F", matched
            against any player whose position contains that letter, so
            "F" also matches combo forwards like "G-F"). None = any position.
        max_age: Upper bound on player age (inclusive). None = no limit.
        min_stat_thresholds: Map of stat name -> minimum value, e.g.
            {"three_pt_pct": 0.38, "steals": 1.2}. Supported keys mirror
            PlayerSearchHit fields (points, rebounds, assists, steals,
            blocks, three_pt_pct).
        season: Season string in "YYYY-YY" format, e.g. "2024-25".
    """
    criteria = {
        "position": position,
        "max_age": max_age,
        "min_stat_thresholds": min_stat_thresholds or {},
    }
    thresholds = min_stat_thresholds or {}

    # Map fine-grained position queries onto the coarse G/F/C letter the
    # underlying roster data actually distinguishes — see the docstring.
    position_letter_aliases = {"PG": "G", "SG": "G", "SF": "F", "PF": "F", "G": "G", "F": "F", "C": "C"}
    position_letter = position_letter_aliases.get((position or "").upper()) if position else None

    league_wide = await asyncio.to_thread(nba.search_players_league_wide, season)
    position_map: dict[int, str] = {}
    if position_letter:
        position_map = await asyncio.to_thread(nba.get_position_map, season)

    stat_key_map = {
        "points": "PTS",
        "rebounds": "REB",
        "assists": "AST",
        "steals": "STL",
        "blocks": "BLK",
        "three_pt_pct": "FG3_PCT",
    }

    matches: list[PlayerSearchHit] = []
    for row in league_wide:
        player_id = int(row["PLAYER_ID"])

        if position_letter and position_letter not in position_map.get(player_id, ""):
            continue
        if max_age is not None and row["AGE"] > max_age:
            continue
        if any(row[stat_key_map[k]] < v for k, v in thresholds.items() if k in stat_key_map):
            continue

        matches.append(
            PlayerSearchHit(
                player_id=player_id,
                player_name=row["PLAYER_NAME"],
                photo_url=nba_headshot_url(player_id),
                team=row["TEAM_ABBREVIATION"],
                position=position_map.get(player_id, ""),
                age=int(row["AGE"]),
                points=float(row["PTS"]),
                rebounds=float(row["REB"]),
                assists=float(row["AST"]),
                steals=float(row["STL"]),
                blocks=float(row["BLK"]),
                three_pt_pct=float(row["FG3_PCT"]),
            )
        )

    result = PlayerSearchResult(criteria=criteria, matches=matches, source="nba_api")
    return result.model_dump()


async def get_team_roster(team_name: str, season: str = DEFAULT_SEASON) -> dict:
    """Get a team's roster with position, age, and physical info.

    Args:
        team_name: Team name, city, or abbreviation, e.g. "Timberwolves",
            "Minnesota", or "MIN".
        season: Season string in "YYYY-YY" format, e.g. "2024-25". Defaults
            to the current (or most recently completed) season.
    """
    team_id = await asyncio.to_thread(nba.resolve_team_id, team_name)

    try:
        roster_raw = await asyncio.to_thread(nba.get_team_roster, team_id, season)
        source = "nba_api"
    except Exception as nba_exc:
        try:
            bdl_team_id = await asyncio.to_thread(bdl.resolve_team_id, team_name)
            roster_raw = await asyncio.to_thread(bdl.get_team_roster_partial, bdl_team_id)
            source = "balldontlie"
        except Exception as bdl_exc:
            raise RuntimeError(
                f"nba_api failed ({nba_exc}); balldontlie fallback also failed ({bdl_exc})"
            ) from nba_exc

    players = [
        RosterEntry(**{**p, "photo_url": nba_headshot_url(p["player_id"])}) for p in roster_raw
    ]
    # team_abbreviation isn't part of the roster row shape from either
    # source, so it's resolved separately via the static teams lookup.
    team_abbreviation = await asyncio.to_thread(_team_abbreviation, team_id)
    result = TeamRosterResult(
        team_name=team_name,
        team_abbreviation=team_abbreviation,
        season=season,
        players=players,
        source=source,
    )
    return result.model_dump()


def _team_abbreviation(team_id: int) -> str:
    from nba_api.stats.static import teams as static_teams

    for t in static_teams.get_teams():
        if t["id"] == team_id:
            return t["abbreviation"]
    return ""


async def compare_players(player_names: list[str], season: str = DEFAULT_SEASON) -> dict:
    """Get side-by-side season stats for two or more players.

    Args:
        player_names: List of player names to compare, e.g.
            ["Anthony Edwards", "Jaylen Brown"].
        season: Season string in "YYYY-YY" format.
    """
    stats_dicts = await asyncio.gather(*(get_player_stats(name, season) for name in player_names))

    players = [
        PlayerComparisonEntry(
            player_id=s["player_id"],
            player_name=s["player_name"],
            photo_url=s["photo_url"],
            team=s["team"],
            per_game=PerGameStats(**s["per_game"]),
            advanced=AdvancedStats(**s["advanced"]),
        )
        for s in stats_dicts
    ]
    source = "nba_api" if all(s["source"] == "nba_api" for s in stats_dicts) else "mixed"
    result = ComparePlayersResult(season=season, players=players, source=source)
    return result.model_dump()


async def get_team_schedule(
    team_name: str,
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict:
    """Get a team's schedule (past results and/or upcoming games) within a date range.

    Args:
        team_name: Team name, city, or abbreviation.
        start_date: ISO date "YYYY-MM-DD". None = today.
        end_date: ISO date "YYYY-MM-DD". None = 14 days after start_date.
    """
    import datetime

    start = start_date or datetime.date.today().isoformat()
    end = end_date or (datetime.date.fromisoformat(start) + datetime.timedelta(days=14)).isoformat()
    season = _infer_nba_season(start)

    team_id = await asyncio.to_thread(nba.resolve_team_id, team_name)

    try:
        games_raw = await asyncio.to_thread(nba.get_team_schedule, team_id, season)
        source = "nba_api"
    except Exception as nba_exc:
        try:
            bdl_team_id = await asyncio.to_thread(bdl.resolve_team_id, team_name)
            games_raw = await asyncio.to_thread(bdl.get_team_schedule, bdl_team_id, _bdl_season_year(season))
            source = "balldontlie"
        except Exception as bdl_exc:
            raise RuntimeError(
                f"nba_api failed ({nba_exc}); balldontlie fallback also failed ({bdl_exc})"
            ) from nba_exc

    games = [ScheduledGame(**g) for g in games_raw if start <= g["game_date"] <= end]
    result = TeamScheduleResult(
        team_name=team_name,
        start_date=start,
        end_date=end,
        games=games,
        source=source,
    )
    return result.model_dump()
