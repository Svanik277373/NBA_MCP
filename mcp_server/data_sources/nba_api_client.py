"""Primary stats data source: wraps `nba_api`, which itself wraps the
public (unofficial, undocumented) JSON endpoints behind stats.nba.com.

No API key — nba_api just makes HTTP requests directly to stats.nba.com.
It's unofficial and can be rate-limited or blocked without warning, which
is exactly why balldontlie_client.py exists as a fallback (see
mcp_server/data_sources/balldontlie_client.py for what that fallback can
and can't actually cover on a free-tier key).

All functions are synchronous (nba_api itself is sync/requests-based) —
called from the MCP tool functions via asyncio.to_thread so a slow
stats.nba.com response doesn't block the event loop.
"""

from __future__ import annotations

from datetime import datetime

from nba_api.stats.endpoints import (
    commonteamroster,
    leaguedashplayerstats,
    leaguegamefinder,
    leagueleaders,
    playergamelog,
)
from nba_api.stats.static import players as static_players
from nba_api.stats.static import teams as static_teams

DEFAULT_TIMEOUT = 20


class NotFoundError(Exception):
    """Raised when a player/team name can't be resolved to an ID."""


def resolve_player_id(player_name: str) -> int:
    """Resolve a player name to their nba_api player_id. Prefers an exact
    full-name match; falls back to the first active player whose name
    contains the query, then the first match of any kind."""
    matches = static_players.find_players_by_full_name(player_name)
    if not matches:
        raise NotFoundError(f"No player found matching '{player_name}'")

    exact = [m for m in matches if m["full_name"].lower() == player_name.lower()]
    if exact:
        return exact[0]["id"]

    active = [m for m in matches if m["is_active"]]
    if active:
        return active[0]["id"]

    return matches[0]["id"]


def resolve_team_id(team_name: str) -> int:
    """Resolve a team name/city/nickname/abbreviation to its nba_api
    team_id. Tries each lookup style nba_api's static data supports."""
    query = team_name.strip()

    by_abbr = static_teams.find_team_by_abbreviation(query.upper())
    if by_abbr:
        return by_abbr["id"]

    for finder in (
        static_teams.find_teams_by_full_name,
        static_teams.find_teams_by_nickname,
        static_teams.find_teams_by_city,
    ):
        matches = finder(query)
        if matches:
            return matches[0]["id"]

    raise NotFoundError(f"No team found matching '{team_name}'")


def get_player_season_stats(player_id: int, season: str) -> dict | None:
    """Per-game base + advanced stats for one player in one season, merged
    into a single row. Returns None if the player didn't play that season
    (e.g. rookie in a prior season, or a bad season string).
    """
    base_df = leaguedashplayerstats.LeagueDashPlayerStats(
        season=season,
        per_mode_detailed="PerGame",
        measure_type_detailed_defense="Base",
        timeout=DEFAULT_TIMEOUT,
    ).get_data_frames()[0]
    base_row = base_df[base_df["PLAYER_ID"] == player_id]
    if base_row.empty:
        return None

    adv_df = leaguedashplayerstats.LeagueDashPlayerStats(
        season=season,
        per_mode_detailed="PerGame",
        measure_type_detailed_defense="Advanced",
        timeout=DEFAULT_TIMEOUT,
    ).get_data_frames()[0]
    adv_row = adv_df[adv_df["PLAYER_ID"] == player_id]

    base = base_row.iloc[0]
    result = {
        "team": base["TEAM_ABBREVIATION"],
        "games_played": int(base["GP"]),
        "minutes": float(base["MIN"]),
        "points": float(base["PTS"]),
        "rebounds": float(base["REB"]),
        "assists": float(base["AST"]),
        "steals": float(base["STL"]),
        "blocks": float(base["BLK"]),
        "turnovers": float(base["TOV"]),
        "fg_pct": float(base["FG_PCT"]),
        "three_pt_pct": float(base["FG3_PCT"]),
        "ft_pct": float(base["FT_PCT"]),
    }

    if not adv_row.empty:
        adv = adv_row.iloc[0]
        result.update(
            {
                # NBA's advanced-stats endpoint doesn't expose Hollinger PER
                # directly (it requires league-wide totals to compute) — PIE
                # (Player Impact Estimate) is NBA.com's own comparable
                # all-in-one impact metric, used here in its place.
                "per": round(float(adv["PIE"]) * 100, 1),
                "ts_pct": float(adv["TS_PCT"]),
                "usage_pct": float(adv["USG_PCT"]),
                "offensive_rating": float(adv["OFF_RATING"]),
                "defensive_rating": float(adv["DEF_RATING"]),
                # win_shares isn't in nba_api's advanced measure type; NBA's
                # own estimated-metrics endpoint has E_NET_RATING but no
                # direct win-shares equivalent either, so this stays 0.0
                # rather than fabricating a number. TODO(real-data): pull
                # from basketball-reference or compute from box-score data.
                "win_shares": 0.0,
            }
        )

    return result


def get_player_game_log(player_id: int, season: str, last_n_games: int) -> list[dict]:
    df = playergamelog.PlayerGameLog(player_id=player_id, season=season, timeout=DEFAULT_TIMEOUT).get_data_frames()[0]
    games = []
    for _, row in df.head(last_n_games).iterrows():
        matchup = row["MATCHUP"]  # e.g. "MIN vs. OKC" (home) or "MIN @ OKC" (away)
        is_home = "vs." in matchup
        opponent = matchup.split()[-1]
        games.append(
            {
                # playergamelog's GAME_DATE is "APR 13, 2025"; normalize to
                # ISO to match every other date field this project returns
                # (leaguegamefinder's GAME_DATE, used by get_team_schedule,
                # is already ISO — only this endpoint needs the conversion).
                "game_date": datetime.strptime(row["GAME_DATE"], "%b %d, %Y").date().isoformat(),
                "opponent": opponent,
                "home_away": "home" if is_home else "away",
                "minutes": float(row["MIN"]),
                "points": int(row["PTS"]),
                "rebounds": int(row["REB"]),
                "assists": int(row["AST"]),
                "steals": int(row["STL"]),
                "blocks": int(row["BLK"]),
                "turnovers": int(row["TOV"]),
                "fg_made": int(row["FGM"]),
                "fg_att": int(row["FGA"]),
                "three_made": int(row["FG3M"]),
                "three_att": int(row["FG3A"]),
                "plus_minus": int(row["PLUS_MINUS"]) if row["PLUS_MINUS"] == row["PLUS_MINUS"] else 0,  # NaN guard
                "result": row["WL"],
            }
        )
    return games


_position_cache: dict[str, dict[int, str]] = {}


def get_position_map(season: str) -> dict[int, str]:
    """player_id -> position, for one season.

    No single league-wide nba_api endpoint includes position (neither
    leaguedashplayerstats nor leaguedashplayerbiostats carry it), so this
    builds the map from all 30 teams' rosters — one commonteamroster call
    each. Costs ~30 requests (a few seconds) the first time a season is
    requested; cached in-process after that since rosters don't change
    within a session.
    """
    if season in _position_cache:
        return _position_cache[season]

    position_map: dict[int, str] = {}
    for team in static_teams.get_teams():
        try:
            roster_df = commonteamroster.CommonTeamRoster(
                team_id=team["id"], season=season, timeout=DEFAULT_TIMEOUT
            ).get_data_frames()[0]
        except Exception:
            continue  # one team's roster failing shouldn't blow up the whole map
        for _, row in roster_df.iterrows():
            position_map[int(row["PLAYER_ID"])] = row["POSITION"] or ""

    _position_cache[season] = position_map
    return position_map


def search_players_league_wide(season: str) -> list[dict]:
    """Per-game base stats for every player league-wide in a season —
    the raw material search_players_by_criteria filters in-process
    (nba_api's endpoint doesn't support this filter combination
    server-side, so filtering happens after the fetch)."""
    base_df = leaguedashplayerstats.LeagueDashPlayerStats(
        season=season,
        per_mode_detailed="PerGame",
        measure_type_detailed_defense="Base",
        timeout=DEFAULT_TIMEOUT,
    ).get_data_frames()[0]
    bio_cols = ["PLAYER_ID", "PLAYER_NAME", "TEAM_ABBREVIATION", "AGE", "PTS", "REB", "AST", "STL", "BLK", "FG3_PCT"]
    return base_df[bio_cols].to_dict("records")


def get_team_roster(team_id: int, season: str) -> list[dict]:
    df = commonteamroster.CommonTeamRoster(team_id=team_id, season=season, timeout=DEFAULT_TIMEOUT).get_data_frames()[0]
    roster = []
    for _, row in df.iterrows():
        exp = row["EXP"]
        roster.append(
            {
                "player_id": int(row["PLAYER_ID"]),
                "player_name": row["PLAYER"],
                "position": row["POSITION"] or "",
                "jersey_number": str(row["NUM"]),
                "age": int(row["AGE"]),
                "height": row["HEIGHT"],
                "weight": int(row["WEIGHT"]) if str(row["WEIGHT"]).isdigit() else 0,
                "experience_years": 0 if exp == "R" else int(exp),
            }
        )
    return roster


def get_team_schedule(team_id: int, season: str) -> list[dict]:
    df = leaguegamefinder.LeagueGameFinder(
        team_id_nullable=team_id, season_nullable=season, timeout=DEFAULT_TIMEOUT
    ).get_data_frames()[0]
    games = []
    for _, row in df.iterrows():
        matchup = row["MATCHUP"]
        is_home = "vs." in matchup
        opponent = matchup.split()[-1]
        result = f"{row['WL']} {int(row['PTS'])}" if row["WL"] else None
        games.append(
            {
                "game_date": row["GAME_DATE"],
                "opponent": opponent,
                "home_away": "home" if is_home else "away",
                "result": result,
            }
        )
    return games


def get_scoring_leaders(season: str, top_n: int = 5) -> list[dict]:
    df = leagueleaders.LeagueLeaders(
        season=season, stat_category_abbreviation="PTS", per_mode48="PerGame", timeout=DEFAULT_TIMEOUT
    ).get_data_frames()[0]
    leaders = []
    for i, row in df.head(top_n).iterrows():
        leaders.append(
            {
                "rank": int(row["RANK"]),
                "player_id": int(row["PLAYER_ID"]),
                "player_name": row["PLAYER"],
                "team": row["TEAM"],
                "value": float(row["PTS"]),
            }
        )
    return leaders


def get_advanced_leaders(season: str, top_n: int = 5) -> list[dict]:
    df = leaguedashplayerstats.LeagueDashPlayerStats(
        season=season,
        per_mode_detailed="PerGame",
        measure_type_detailed_defense="Advanced",
        timeout=DEFAULT_TIMEOUT,
    ).get_data_frames()[0]
    # PIE stands in for PER here — see the comment in get_player_season_stats.
    df = df[df["MIN"] >= 20.0].sort_values("PIE", ascending=False)
    leaders = []
    for i, (_, row) in enumerate(df.head(top_n).iterrows(), start=1):
        leaders.append(
            {
                "rank": i,
                "player_id": int(row["PLAYER_ID"]),
                "player_name": row["PLAYER_NAME"],
                "team": row["TEAM_ABBREVIATION"],
                "per": round(float(row["PIE"]) * 100, 1),
                "ts_pct": float(row["TS_PCT"]),
            }
        )
    return leaders
