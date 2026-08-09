"""Fallback stats data source: balldontlie.io's v1 REST API.

Used when nba_api / stats.nba.com is unreachable or rate-limited — see
mcp_server/data_sources/nba_api_client.py, which is the primary source.

Honest scope note: balldontlie's free tier (the only tier this project is
configured with — set BALLDONTLIE_API_KEY in .env) does NOT include the
`/stats` or `/season_averages` endpoints (confirmed live: they return 401
even with a valid free-tier key — that's a plan restriction, not a bug).
So this client can meaningfully cover:

  - player/team lookup            (get_player_stats, compare_players, etc.
                                    fall back to this only for *resolving*
                                    a name, not for the stats themselves)
  - team schedule/results (/games) (get_team_schedule — full fallback)
  - team roster (/players)         (get_team_roster — partial: no
                                    age/experience_years from this endpoint)

It cannot fall back for get_player_stats, get_player_game_log,
compare_players, or search_players_by_criteria's stat thresholds — those
raise TierRestrictedError if called, so callers can distinguish "this
endpoint needs a paid balldontlie plan" from "the network request failed".
"""

from __future__ import annotations

import os

import httpx

BASE_URL = "https://api.balldontlie.io/v1"
DEFAULT_TIMEOUT = 15


class NotFoundError(Exception):
    """Raised when a player/team name can't be resolved."""


class TierRestrictedError(Exception):
    """Raised when the endpoint needs a paid balldontlie plan (401)."""


def _headers() -> dict[str, str]:
    api_key = os.environ.get("BALLDONTLIE_API_KEY", "")
    return {"Authorization": api_key} if api_key else {}


def _get(path: str, params: dict | None = None) -> dict:
    response = httpx.get(f"{BASE_URL}{path}", params=params, headers=_headers(), timeout=DEFAULT_TIMEOUT)
    if response.status_code == 401:
        raise TierRestrictedError(f"balldontlie {path} requires a paid plan (free tier returned 401)")
    response.raise_for_status()
    return response.json()


def resolve_team_id(team_name: str) -> int:
    query = team_name.strip().lower()
    data = _get("/teams")["data"]
    for team in data:
        if query in (team["full_name"].lower(), team["city"].lower(), team["name"].lower(), team["abbreviation"].lower()):
            return team["id"]
    for team in data:
        if query in team["full_name"].lower():
            return team["id"]
    raise NotFoundError(f"No team found matching '{team_name}'")


def resolve_player_id(player_name: str) -> int:
    # balldontlie's search matches against first/last name fields
    # separately — searching the full "First Last" string sometimes misses,
    # so search on the last word (usually the surname) and pick the best
    # full-name match from the results.
    last_word = player_name.strip().split()[-1]
    data = _get("/players", params={"search": last_word})["data"]
    if not data:
        raise NotFoundError(f"No player found matching '{player_name}'")

    exact = [p for p in data if f"{p['first_name']} {p['last_name']}".lower() == player_name.lower()]
    if exact:
        return exact[0]["id"]
    return data[0]["id"]


def get_team_schedule(team_id: int, season: int) -> list[dict]:
    games = []
    cursor = None
    while True:
        params = {"seasons[]": season, "team_ids[]": team_id, "per_page": 100}
        if cursor is not None:
            params["cursor"] = cursor
        payload = _get("/games", params=params)
        for g in payload["data"]:
            is_home = g["home_team"]["id"] == team_id
            opponent = g["visitor_team"]["abbreviation"] if is_home else g["home_team"]["abbreviation"]
            result = None
            if g["status"] == "Final":
                own_score = g["home_team_score"] if is_home else g["visitor_team_score"]
                opp_score = g["visitor_team_score"] if is_home else g["home_team_score"]
                result = f"{'W' if own_score > opp_score else 'L'} {own_score}-{opp_score}"
            games.append(
                {
                    "game_date": g["date"],
                    "opponent": opponent,
                    "home_away": "home" if is_home else "away",
                    "result": result,
                }
            )
        cursor = payload.get("meta", {}).get("next_cursor")
        if not cursor:
            break
    return games


def get_team_roster_partial(team_id: int) -> list[dict]:
    """Partial roster info — two limitations vs. nba_api's
    commonteamroster: (1) age/experience_years aren't in this endpoint's
    response, left at a documented placeholder; (2) `team_ids[]` filters
    correctly by team but returns everyone ever associated with that
    team_id, not just the current roster — there's no "currently active"
    flag on the free tier, so this can include players who were later
    traded or waived. Best-effort only; nba_api's roster is authoritative."""
    data = _get("/players", params={"team_ids[]": team_id, "per_page": 100})["data"]
    roster = []
    for p in data:
        roster.append(
            {
                "player_id": p["id"],
                "player_name": f"{p['first_name']} {p['last_name']}",
                "position": p["position"] or "",
                "jersey_number": p["jersey_number"] or "",
                "age": 0,  # not available from this endpoint
                "height": p["height"] or "",
                "weight": int(p["weight"]) if str(p["weight"]).isdigit() else 0,
                "experience_years": 0,  # not available from this endpoint
            }
        )
    return roster


def get_player_season_stats(player_id: int, season: int) -> dict:
    raise TierRestrictedError(
        "balldontlie's free tier does not include /season_averages — no fallback available for player stats"
    )


def get_player_game_log(player_id: int, season: int, last_n_games: int) -> list[dict]:
    raise TierRestrictedError(
        "balldontlie's free tier does not include /stats — no fallback available for game logs"
    )
