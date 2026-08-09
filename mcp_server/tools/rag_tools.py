"""RAG tools over the scouting-corpus vector store.

Wired to the real rag_pipeline: Chroma + the configured embedding backend
(local all-MiniLM-L6-v2 by default, see rag_pipeline/embeddings.py).
"""

from __future__ import annotations

from mcp_server.schemas import (
    ScoutingPassage,
    ScoutingSearchResult,
    SimilarHistoricalPlayersResult,
    SimilarPlayerEntry,
)
from rag_pipeline import vectorstore
from rag_pipeline.embeddings import embed_query
from mcp_server.utils import nba_headshot_url
from rag_pipeline.historical_stats import (
    HISTORICAL_PLAYER_IDS,
    HISTORICAL_STAT_VECTORS,
    cosine_similarity,
    current_player_vector,
)

# Cosine distance from Chroma is ~[0, 2]; in practice embeddings of related
# text sit well under 1. Clamp so relevance/similarity scores stay in the
# [0, 1] range the schema promises even on an unusually distant match.
def _distance_to_score(distance: float) -> float:
    return max(0.0, min(1.0, 1.0 - distance))


def search_scouting_context(
    query: str,
    player_name: str | None = None,
    top_k: int = 5,
) -> dict:
    """Semantic search over scouting write-ups, game recaps, and player style
    profiles. Returns the top-k most relevant passages with source
    attribution, for questions about playing style, tendencies, scheme fit,
    or narrative context that raw stats can't answer.

    Args:
        query: Natural-language question or topic, e.g. "drop coverage vs
            switch-heavy defense" or "why has his 3pt shooting declined".
        player_name: If set, pre-filter the corpus to passages tagged with
            this player before running semantic search (hybrid metadata +
            vector filtering).
        top_k: Number of passages to return.
    """
    query_embedding = embed_query(query)
    where = {"player": player_name} if player_name else None
    raw = vectorstore.query(query_embedding, top_k=top_k, where=where)

    passages: list[ScoutingPassage] = []
    documents = raw["documents"][0] if raw["documents"] else []
    metadatas = raw["metadatas"][0] if raw["metadatas"] else []
    distances = raw["distances"][0] if raw["distances"] else []
    for doc, meta, dist in zip(documents, metadatas, distances):
        passages.append(
            ScoutingPassage(
                content=doc,
                source_file=meta.get("source_file", "unknown"),
                player=meta.get("player"),
                team=meta.get("team"),
                doc_date=meta.get("date"),
                relevance_score=_distance_to_score(dist),
            )
        )

    result = ScoutingSearchResult(query=query, results=passages)
    return result.model_dump()


async def get_similar_historical_players(player_name: str, top_k: int = 5) -> dict:
    """Find historical players with a similar playing style, combining
    stat-vector distance (season averages + advanced stats) with embedding
    similarity over written style profiles — so results reflect how a
    player plays, not just their raw box score.

    Args:
        player_name: The current player to find historical comps for.
        top_k: Number of comps to return.
    """
    # Style half: use the current player's own scouting profile as the
    # query (if the corpus has one) so we're comparing narrative style
    # descriptions to narrative style descriptions, not stats to prose.
    # Falls back to a synthetic query when no profile doc exists for them.
    own_profile = vectorstore.get_by_metadata(
        where={"$and": [{"player": player_name}, {"doc_type": "player_profile"}]},
        limit=1,
    )
    if own_profile["documents"]:
        query_text = own_profile["documents"][0]
    else:
        query_text = f"{player_name} playing style, shot creation, athleticism, defense"

    query_embedding = embed_query(query_text)
    raw = vectorstore.query(
        query_embedding,
        top_k=top_k,
        where={"historical": True},
    )

    # Stat half: current player's per_game+advanced vector, imported lazily
    # to avoid a hard import-time dependency between the two tool modules.
    from mcp_server.tools.stats_tools import get_player_stats

    current_stats = await get_player_stats(player_name)
    current_vector = current_player_vector(current_stats["per_game"], current_stats["advanced"])

    comps: list[SimilarPlayerEntry] = []
    documents = raw["documents"][0] if raw["documents"] else []
    metadatas = raw["metadatas"][0] if raw["metadatas"] else []
    distances = raw["distances"][0] if raw["distances"] else []
    for doc, meta, dist in zip(documents, metadatas, distances):
        historical_name = meta.get("player", "Unknown")
        style_similarity = _distance_to_score(dist)

        historical_vector = HISTORICAL_STAT_VECTORS.get(historical_name)
        if historical_vector is not None:
            stat_similarity = cosine_similarity(current_vector, historical_vector)
        else:
            # No stat table entry for this historical player (corpus has a
            # style profile but we haven't hardcoded their stat line) —
            # fall back to style similarity alone rather than fabricating
            # a stat comparison.
            stat_similarity = style_similarity

        overall_similarity = 0.5 * stat_similarity + 0.5 * style_similarity
        explanation = doc if len(doc) <= 400 else doc[:400].rsplit(" ", 1)[0] + "..."

        historical_player_id = HISTORICAL_PLAYER_IDS.get(historical_name)
        comps.append(
            SimilarPlayerEntry(
                player_name=historical_name,
                photo_url=nba_headshot_url(historical_player_id) if historical_player_id else None,
                era=meta.get("era", "unknown era"),
                overall_similarity=overall_similarity,
                stat_similarity=stat_similarity,
                style_similarity=style_similarity,
                explanation=explanation,
            )
        )

    result = SimilarHistoricalPlayersResult(player_name=player_name, similar_players=comps)
    return result.model_dump()
