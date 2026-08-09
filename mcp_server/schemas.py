"""Pydantic models for MCP tool inputs/outputs.

Kept separate from the tool functions so the shape of every response is
reviewable in one place before the real data-source/RAG calls are wired in.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Structured stats tools
# ---------------------------------------------------------------------------


class PerGameStats(BaseModel):
    games_played: int
    minutes: float
    points: float
    rebounds: float
    assists: float
    steals: float
    blocks: float
    turnovers: float
    fg_pct: float
    three_pt_pct: float
    ft_pct: float


class AdvancedStats(BaseModel):
    per: float = Field(description="Player Efficiency Rating")
    ts_pct: float = Field(description="True Shooting %")
    usage_pct: float
    offensive_rating: float
    defensive_rating: float
    win_shares: float


class PlayerStatsResult(BaseModel):
    player_id: int
    player_name: str
    photo_url: str = Field(description="NBA.com CDN headshot URL")
    team: str
    season: str
    season_type: str = "Regular Season"
    per_game: PerGameStats
    advanced: AdvancedStats
    source: str = Field(description="Which data source served this response")


class GameLogEntry(BaseModel):
    game_date: str
    opponent: str
    home_away: str
    minutes: float
    points: int
    rebounds: int
    assists: int
    steals: int
    blocks: int
    turnovers: int
    fg_made: int
    fg_att: int
    three_made: int
    three_att: int
    plus_minus: int
    result: str


class PlayerGameLogResult(BaseModel):
    player_id: int
    player_name: str
    photo_url: str
    season: str
    games: list[GameLogEntry]
    source: str


class PlayerSearchHit(BaseModel):
    player_id: int
    player_name: str
    photo_url: str
    team: str
    position: str
    age: int
    points: float
    rebounds: float
    assists: float
    steals: float
    blocks: float
    three_pt_pct: float


class PlayerSearchResult(BaseModel):
    criteria: dict
    matches: list[PlayerSearchHit]
    source: str


class RosterEntry(BaseModel):
    player_id: int
    player_name: str
    photo_url: str
    position: str
    jersey_number: str
    age: int
    height: str
    weight: int
    experience_years: int


class TeamRosterResult(BaseModel):
    team_name: str
    team_abbreviation: str
    season: str
    players: list[RosterEntry]
    source: str


class PlayerComparisonEntry(BaseModel):
    player_id: int
    player_name: str
    photo_url: str
    team: str
    per_game: PerGameStats
    advanced: AdvancedStats


class ComparePlayersResult(BaseModel):
    season: str
    players: list[PlayerComparisonEntry]
    source: str


class ScheduledGame(BaseModel):
    game_date: str
    opponent: str
    home_away: str
    result: str | None = Field(default=None, description="e.g. 'W 112-108'; null for future games")


class TeamScheduleResult(BaseModel):
    team_name: str
    start_date: str
    end_date: str
    games: list[ScheduledGame]
    source: str


# ---------------------------------------------------------------------------
# RAG tools
# ---------------------------------------------------------------------------


class ScoutingPassage(BaseModel):
    content: str
    source_file: str
    player: str | None = None
    team: str | None = None
    doc_date: str | None = None
    relevance_score: float = Field(ge=0.0, le=1.0)


class ScoutingSearchResult(BaseModel):
    query: str
    results: list[ScoutingPassage]


class SimilarPlayerEntry(BaseModel):
    player_name: str
    photo_url: str | None = Field(
        default=None, description="Best-effort; not every historical player has a CDN headshot"
    )
    era: str
    overall_similarity: float = Field(ge=0.0, le=1.0)
    stat_similarity: float = Field(ge=0.0, le=1.0, description="Cosine similarity over the stat vector")
    style_similarity: float = Field(ge=0.0, le=1.0, description="Embedding similarity over written style profiles")
    explanation: str


class SimilarHistoricalPlayersResult(BaseModel):
    player_name: str
    similar_players: list[SimilarPlayerEntry]
