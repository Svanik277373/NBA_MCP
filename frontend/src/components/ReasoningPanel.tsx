import { useState } from "react";
import type { TraceItem } from "../lib/types";
import { Caret } from "./icons";
import { ToolCallCard } from "./ToolCallCard";

function ThinkingBlock({ text }: { text: string }) {
  return <div className="thinking-block">{text}</div>;
}

export function ReasoningPanel({ trace, streaming }: { trace: TraceItem[]; streaming: boolean }) {
  const [open, setOpen] = useState(true);
  if (trace.length === 0) return null;

  const toolItems = trace.filter((t): t is Extract<TraceItem, { kind: "tool" }> => t.kind === "tool");
  const ragCount = toolItems.filter((t) => t.category === "rag").length;

  return (
    <div className="reasoning-panel">
      <div className="reasoning-header" onClick={() => setOpen(!open)}>
        <Caret open={open} />
        {streaming && <span className="spinner" />}
        <span>
          Reasoning — {toolItems.length} tool call{toolItems.length === 1 ? "" : "s"}
          {ragCount > 0 ? ` (${ragCount} RAG)` : ""}
        </span>
      </div>
      {open && (
        <div className="reasoning-body">
          {trace.map((item, i) =>
            item.kind === "thinking" ? <ThinkingBlock key={i} text={item.text} /> : <ToolCallCard key={i} item={item} />
          )}
        </div>
      )}
    </div>
  );
}
