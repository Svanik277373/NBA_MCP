import type { ScoutingSearchResult, SimilarHistoricalPlayersResult, ToolResult } from "../lib/types";

function isScoutingSearchResult(result: ToolResult): result is ScoutingSearchResult {
  return Array.isArray((result as ScoutingSearchResult).results);
}

function isSimilarHistoricalPlayersResult(result: ToolResult): result is SimilarHistoricalPlayersResult {
  return Array.isArray((result as SimilarHistoricalPlayersResult).similar_players);
}

/** Renders the retrieved passages/comps for a RAG tool's result — the
 * spec calls for showing citations in the trace itself, not just folding
 * them into the final answer. */
export function Citations({ result }: { result?: ToolResult }) {
  if (!result) return null;

  if (isScoutingSearchResult(result)) {
    if (result.results.length === 0) return null;
    return (
      <div className="citations">
        {result.results.map((p, i) => (
          <div className="citation-card" key={i}>
            <div className="citation-source">
              {p.source_file}
              {p.player ? ` · ${p.player}` : ""} · relevance {p.relevance_score.toFixed(2)}
            </div>
            <div className="citation-content">
              {p.content.slice(0, 260)}
              {p.content.length > 260 ? "…" : ""}
            </div>
          </div>
        ))}
      </div>
    );
  }

  if (isSimilarHistoricalPlayersResult(result)) {
    if (result.similar_players.length === 0) return null;
    return (
      <div className="citations">
        {result.similar_players.map((c, i) => (
          <div className="comp-card" key={i}>
            {c.photo_url && (
              <img
                src={c.photo_url}
                alt={c.player_name}
                onError={(e) => {
                  (e.currentTarget as HTMLImageElement).style.display = "none";
                }}
              />
            )}
            <div className="comp-card-body">
              <div className="comp-card-name">{c.player_name}</div>
              <div className="comp-card-era">{c.era}</div>
            </div>
            <div className="comp-card-score">overall {(c.overall_similarity * 100).toFixed(0)}%</div>
          </div>
        ))}
      </div>
    );
  }

  return null;
}
