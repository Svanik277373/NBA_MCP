import type { SSEEvent, TraceItem, TraceToolItem } from "./types";

function isPendingTool(item: TraceItem): item is TraceToolItem {
  return item.kind === "tool" && !item.resolved;
}

/**
 * Merge a stream of SSE events into an ordered trace of thinking blocks +
 * tool call/result pairs. Tool calls and results are matched by insertion
 * order (the backend always emits tool_call then its own tool_result
 * before starting the next tool — see agent_backend/agent/loop.py), not
 * by name — a tool can legitimately be called more than once in one turn.
 */
export function applyEventToTrace(trace: TraceItem[], event: SSEEvent): TraceItem[] {
  if (event.type === "thinking") {
    return [...trace, { kind: "thinking", text: event.data.text }];
  }

  if (event.type === "tool_call") {
    return [
      ...trace,
      {
        kind: "tool",
        toolName: event.data.tool_name,
        category: event.data.category,
        arguments: event.data.arguments,
        resolved: false,
      },
    ];
  }

  if (event.type === "tool_result") {
    const reverseIdx = [...trace].reverse().findIndex(isPendingTool);
    if (reverseIdx === -1) return trace;
    const idx = trace.length - 1 - reverseIdx;
    const prior = trace[idx] as TraceToolItem;
    const resolvedItem: TraceToolItem = {
      ...prior,
      resolved: true,
      resultPreview: event.data.result_preview,
      result: event.data.result,
      error: event.data.error,
    };
    const updated = trace.slice();
    updated[idx] = resolvedItem;
    return updated;
  }

  return trace;
}
