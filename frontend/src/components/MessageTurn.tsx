import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { ChatTurn } from "../lib/types";
import { ReasoningPanel } from "./ReasoningPanel";

export function MessageTurn({ turn }: { turn: ChatTurn }) {
  return (
    <div className="turn">
      <div className="user-msg">{turn.query}</div>
      <div className="assistant-msg">
        <ReasoningPanel trace={turn.trace} streaming={turn.status === "streaming"} />

        {turn.finalAnswer !== null && (
          <div className="markdown-body">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{turn.finalAnswer}</ReactMarkdown>
          </div>
        )}

        {turn.status === "streaming" && turn.finalAnswer === null && turn.trace.length === 0 && (
          <div className="markdown-body">
            <span className="streaming-cursor" />
          </div>
        )}

        {turn.status === "error" && (
          <div className="markdown-body" style={{ color: "var(--error)" }}>
            {turn.errorMessage || "Something went wrong."}
          </div>
        )}
      </div>
    </div>
  );
}
