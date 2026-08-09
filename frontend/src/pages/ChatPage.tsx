import { useCallback, useEffect, useRef, useState } from "react";
import { Nav } from "../components/Nav";
import { MessageTurn } from "../components/MessageTurn";
import { streamChat } from "../lib/api";
import { applyEventToTrace } from "../lib/trace";
import type { ChatTurn } from "../lib/types";

const EXAMPLE_QUERIES = [
  "Build me a scouting report on Anthony Edwards comparing him to similar historical players",
  "Find undervalued 3-and-D wings under age 25 this season",
  "Why has Anthony Edwards's efficiency dropped compared to last season?",
  "How does Minnesota perform against switch-heavy defenses?",
];

export function ChatPage() {
  const [turns, setTurns] = useState<ChatTurn[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [turns]);

  const updateLastTurn = useCallback((updater: (turn: ChatTurn) => ChatTurn) => {
    setTurns((prev) => {
      const next = prev.slice();
      next[next.length - 1] = updater(next[next.length - 1]);
      return next;
    });
  }, []);

  const send = useCallback(
    async (query: string) => {
      if (!query.trim() || busy) return;
      setBusy(true);
      setInput("");
      setTurns((prev) => [...prev, { query, trace: [], finalAnswer: null, status: "streaming", errorMessage: null }]);

      try {
        for await (const event of streamChat(query)) {
          if (event.type === "final_answer") {
            updateLastTurn((t) => ({ ...t, finalAnswer: event.data.text, status: "done" }));
          } else if (event.type === "error") {
            updateLastTurn((t) => ({ ...t, status: "error", errorMessage: event.data.message }));
          } else {
            updateLastTurn((t) => ({ ...t, trace: applyEventToTrace(t.trace, event) }));
          }
        }
      } catch (err) {
        updateLastTurn((t) => ({ ...t, status: "error", errorMessage: String((err as Error).message || err) }));
      } finally {
        setBusy(false);
      }
    },
    [busy, updateLastTurn]
  );

  const onKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send(input);
    }
  };

  return (
    <>
      <Nav />

      <div className="chat-scroll" ref={scrollRef}>
        {turns.length === 0 && (
          <div className="empty-state">
            <h2>Ask a scouting question</h2>
            <p>Structured stats and RAG-backed scouting notes, chained automatically.</p>
            <div className="example-queries">
              {EXAMPLE_QUERIES.map((q) => (
                <button key={q} className="example-query-btn" onClick={() => send(q)}>
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}
        {turns.map((turn, i) => (
          <MessageTurn key={i} turn={turn} />
        ))}
      </div>

      <div className="input-bar">
        <div className="input-inner">
          <textarea
            rows={1}
            placeholder="Ask about a player, team, or matchup…"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={onKeyDown}
          />
          <button className="send-btn" disabled={busy || !input.trim()} onClick={() => send(input)}>
            Send
          </button>
        </div>
      </div>
    </>
  );
}
