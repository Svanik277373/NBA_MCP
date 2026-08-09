import { useState } from "react";
import type { TraceToolItem } from "../lib/types";
import { Caret, RagIcon, StatsIcon } from "./icons";
import { Citations } from "./Citations";

export function ToolCallCard({ item }: { item: TraceToolItem }) {
  const [open, setOpen] = useState(true);
  const isRag = item.category === "rag";

  return (
    <div className={`tool-card${isRag ? " category-rag" : ""}`}>
      <div className="tool-card-header" onClick={() => setOpen(!open)}>
        <Caret open={open} />
        <span className="tool-icon">{isRag ? <RagIcon /> : <StatsIcon />}</span>
        <span className="tool-name">{item.toolName}</span>
        <span className="tool-badge">{isRag ? "RAG" : "stats"}</span>
        <span className={`tool-status${item.error ? " error" : ""}`}>
          {!item.resolved ? "running…" : item.error ? "error" : "done"}
        </span>
      </div>
      {open && (
        <div className="tool-card-body">
          {item.arguments && Object.keys(item.arguments).length > 0 && (
            <div className="tool-args">{JSON.stringify(item.arguments, null, 2)}</div>
          )}
          {item.error ? (
            <div className="tool-preview" style={{ color: "var(--error)" }}>
              {item.error}
            </div>
          ) : (
            <div className="tool-preview">{item.resultPreview}</div>
          )}
          <Citations result={item.result} />
        </div>
      )}
    </div>
  );
}
