"""Small shared helpers used across tool implementations."""

from __future__ import annotations

from datetime import date


def current_nba_season() -> str:
    """The current (or most recently completed) NBA season, as "YYYY-YY".

    NBA seasons start in October — Aug/Sep is offseason with no season
    "in progress" yet, so this points back at the season that just
    finished rather than forward at one that hasn't started:

        Aug 2026 -> "2025-26" (2025-26 finished in June; 2026-27 hasn't started)
        Nov 2025 -> "2025-26" (in progress)
        Mar 2026 -> "2025-26" (in progress)

    Evaluated once at import time (used as a function default value, which
    Python binds at def-time) — correct in practice since seasons only
    turn over a couple of times a year; a long-running process would only
    be off right at that boundary until restarted.
    """
    today = date.today()
    start_year = today.year if today.month >= 10 else today.year - 1
    return f"{start_year}-{str(start_year + 1)[-2:]}"


def nba_headshot_url(player_id: int) -> str:
    """Build the standard NBA.com CDN headshot URL for a player_id.

    This is a static, well-known URL pattern — no API call needed once you
    have the player_id (resolved via nba_api's static players lookup).
    Not every player_id has an image on the CDN (very old/obscure players
    may 404); callers needing a guarantee should treat this as best-effort.
    """
    return f"https://cdn.nba.com/headshots/nba/latest/1040x760/{player_id}.png"
