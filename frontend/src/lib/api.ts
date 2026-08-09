import type { AdminRequestRow, AdminStats, SSEEvent } from "./types";

export const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

/**
 * POST /chat and yield parsed SSE events as they arrive.
 *
 * The backend (sse-starlette) is POST-friendly, but the native browser
 * EventSource API is GET-only — so this hand-parses the
 * `event: ...\ndata: ...\n\n` wire format from a streamed fetch() body
 * instead of using EventSource.
 */
export async function* streamChat(query: string): AsyncGenerator<SSEEvent> {
  const response = await fetch(`${API_BASE}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query }),
  });

  if (!response.ok || !response.body) {
    throw new Error(`Chat request failed: ${response.status}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    // Normalize CRLF to LF — uvicorn on Windows streams "\r\n\r\n" as the
    // blank-line event separator, which does NOT contain "\n\n" as a
    // substring, so boundary detection below would silently never fire
    // without this (the whole stream would buffer forever and no event
    // would ever be parsed).
    buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, "\n");

    // SSE events are separated by a blank line.
    let boundary: number;
    while ((boundary = buffer.indexOf("\n\n")) !== -1) {
      const rawEvent = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);
      const parsed = parseSSEBlock(rawEvent);
      if (parsed) yield parsed;
    }
  }
}

function parseSSEBlock(block: string): SSEEvent | null {
  let eventType = "message";
  const dataLines: string[] = [];
  for (const line of block.split("\n")) {
    if (line.startsWith(":")) continue; // comment/ping line
    if (line.startsWith("event:")) eventType = line.slice(6).trim();
    else if (line.startsWith("data:")) dataLines.push(line.slice(5).trim());
  }
  if (dataLines.length === 0) return null;
  const data = JSON.parse(dataLines.join("\n"));
  return { type: eventType, data } as SSEEvent;
}

export async function fetchAdminRequests(limit = 50): Promise<AdminRequestRow[]> {
  const r = await fetch(`${API_BASE}/admin/requests?limit=${limit}`);
  if (!r.ok) throw new Error(`Failed to load requests: ${r.status}`);
  return r.json();
}

export async function fetchAdminStats(): Promise<AdminStats> {
  const r = await fetch(`${API_BASE}/admin/stats`);
  if (!r.ok) throw new Error(`Failed to load stats: ${r.status}`);
  return r.json();
}
