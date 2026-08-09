"""Small hardcoded historical stat-vector table.

This is the "current player" side of get_similar_historical_players'
stat-vector half — see mcp_server/tools/rag_tools.py. A production version
would build this from nba_api's career-stats endpoints (which do cover
historical seasons), indexed once and cached; this hardcoded table exists
so the hybrid stat+style similarity method can be demonstrated for real
before that broader historical index is built.
"""

from __future__ import annotations

import math

# Values are the requested comparison season's per-game + advanced stats,
# on the same keys PerGameStats/AdvancedStats use for current players.
HISTORICAL_STAT_VECTORS: dict[str, dict[str, float]] = {
    "Tracy McGrady": {
        "points": 32.1,
        "rebounds": 6.5,
        "assists": 5.5,
        "steals": 1.4,
        "blocks": 0.8,
        "usage_pct": 0.334,
        "ts_pct": 0.552,
    },
    "Vince Carter": {
        "points": 25.7,
        "rebounds": 5.3,
        "assists": 3.9,
        "steals": 1.1,
        "blocks": 0.8,
        "usage_pct": 0.289,
        "ts_pct": 0.548,
    },
    "Kobe Bryant": {
        "points": 28.5,
        "rebounds": 5.9,
        "assists": 4.5,
        "steals": 1.5,
        "blocks": 0.5,
        "usage_pct": 0.318,
        "ts_pct": 0.559,
    },
    "Dwyane Wade": {
        "points": 27.2,
        "rebounds": 4.7,
        "assists": 6.7,
        "steals": 1.5,
        "blocks": 0.8,
        "usage_pct": 0.301,
        "ts_pct": 0.564,
    },
}

# Real, well-known NBA.com player_ids — confident enough to hardcode
# directly, same treatment as mcp_server/tools/stats_tools.py's
# _STUB_PLAYER_IDS. Lets get_similar_historical_players resolve a real
# headshot via mcp_server.utils.nba_headshot_url instead of leaving
# historical comps photo-less.
HISTORICAL_PLAYER_IDS: dict[str, int] = {
    "Tracy McGrady": 1503,
    "Vince Carter": 1713,
    "Kobe Bryant": 977,
    "Dwyane Wade": 2548,
}

_KEYS = ("points", "rebounds", "assists", "steals", "blocks", "usage_pct", "ts_pct")

# Rough "typical max" per stat, used to scale every dimension into a
# comparable numeric range before computing cosine similarity. Without this,
# raw dot products are dominated entirely by whichever stat has the largest
# scale (points, ~25-35) and usage_pct/ts_pct (~0.3-0.6) barely register —
# every high scorer ends up looking ~99% similar to every other high scorer
# regardless of actual stylistic differences in rebounding, playmaking, or
# efficiency. Scaling first makes the metric sensitive to shape, not just
# magnitude.
_STAT_SCALE = {
    "points": 35.0,
    "rebounds": 15.0,
    "assists": 12.0,
    "steals": 3.0,
    "blocks": 3.0,
    "usage_pct": 0.35,
    "ts_pct": 0.65,
}


def _scaled_vector(stats: dict[str, float]) -> list[float]:
    return [stats.get(k, 0.0) / _STAT_SCALE[k] for k in _KEYS]


def cosine_similarity(a: dict[str, float], b: dict[str, float]) -> float:
    """Cosine similarity over the fixed stat-key set (each dimension scaled
    to a comparable range first — see _STAT_SCALE), mapped from [-1, 1] to
    [0, 1] to match the other similarity scores in SimilarPlayerEntry.

    Note: cosine similarity on all-positive stat vectors compresses toward
    1.0 for any two reasonably-similar players (everyone sits in the same
    orthant), so absolute values cluster high — what matters is the
    relative ordering, which the fixed-scale fix above makes meaningful. A
    larger real historical index would z-score each dimension against the
    full population instead of fixed constants, widening the spread.
    """
    vec_a = _scaled_vector(a)
    vec_b = _scaled_vector(b)
    dot = sum(x * y for x, y in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(x * x for x in vec_a))
    norm_b = math.sqrt(sum(y * y for y in vec_b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    cos = dot / (norm_a * norm_b)
    return (cos + 1) / 2


def current_player_vector(per_game: dict, advanced: dict) -> dict[str, float]:
    """Extract the comparable subset from a PerGameStats/AdvancedStats pair
    (as returned by get_player_stats) into the same key shape as
    HISTORICAL_STAT_VECTORS.
    """
    return {
        "points": per_game["points"],
        "rebounds": per_game["rebounds"],
        "assists": per_game["assists"],
        "steals": per_game["steals"],
        "blocks": per_game["blocks"],
        "usage_pct": advanced["usage_pct"],
        "ts_pct": advanced["ts_pct"],
    }
