export type ToolCategory = "stats" | "rag";

export interface ScoutingPassage {
  content: string;
  source_file: string;
  player: string | null;
  team: string | null;
  doc_date: string | null;
  relevance_score: number;
}

export interface ScoutingSearchResult {
  query: string;
  results: ScoutingPassage[];
}

export interface SimilarPlayerEntry {
  player_name: string;
  photo_url: string | null;
  era: string;
  overall_similarity: number;
  stat_similarity: number;
  style_similarity: number;
  explanation: string;
}

export interface SimilarHistoricalPlayersResult {
  player_name: string;
  similar_players: SimilarPlayerEntry[];
}

/** Loose shape covering every tool's response — only the two RAG shapes
 * above are narrowed/rendered specially; everything else just shows the
 * backend's truncated result_preview string. */
export type ToolResult = ScoutingSearchResult | SimilarHistoricalPlayersResult | Record<string, unknown>;

export interface TraceThinkingItem {
  kind: "thinking";
  text: string;
}

export interface TraceToolItem {
  kind: "tool";
  toolName: string;
  category: ToolCategory;
  arguments: Record<string, unknown>;
  resolved: boolean;
  resultPreview?: string;
  result?: ToolResult;
  error?: string;
}

export type TraceItem = TraceThinkingItem | TraceToolItem;

export type TurnStatus = "streaming" | "done" | "error";

export interface ChatTurn {
  query: string;
  trace: TraceItem[];
  finalAnswer: string | null;
  status: TurnStatus;
  errorMessage: string | null;
}

// ---- SSE wire events (agent_backend/agent/sse.py) ----

export interface SSEThinkingEvent {
  type: "thinking";
  data: { text: string };
}

export interface SSEToolCallEvent {
  type: "tool_call";
  data: { tool_name: string; category: ToolCategory; arguments: Record<string, unknown> };
}

export interface SSEToolResultEvent {
  type: "tool_result";
  data: {
    tool_name: string;
    category: ToolCategory;
    result_preview?: string;
    result?: ToolResult;
    error?: string;
  };
}

export interface SSEFinalAnswerEvent {
  type: "final_answer";
  data: { text: string };
}

export interface SSEErrorEvent {
  type: "error";
  data: { message: string };
}

export type SSEEvent =
  | SSEThinkingEvent
  | SSEToolCallEvent
  | SSEToolResultEvent
  | SSEFinalAnswerEvent
  | SSEErrorEvent;

// ---- Admin API (agent_backend/db.py) ----

export interface AdminRequestRow {
  id: number;
  created_at: string;
  query: string;
  model: string;
  status: "ok" | "error";
  error_message: string | null;
  latency_ms: number;
  api_calls: number;
  tool_calls: string[];
  input_tokens: number;
  output_tokens: number;
  cache_creation_tokens: number;
  cache_read_tokens: number;
  estimated_cost_usd: number;
}

export interface AdminStats {
  total_requests: number;
  total_input_tokens: number;
  total_output_tokens: number;
  total_cache_creation_tokens: number;
  total_cache_read_tokens: number;
  total_estimated_cost_usd: number;
  avg_latency_ms: number;
  error_count: number;
  tool_call_counts: Record<string, number>;
}
