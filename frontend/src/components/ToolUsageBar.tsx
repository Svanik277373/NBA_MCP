export function ToolUsageBar({
  name,
  count,
  max,
  isRag,
}: {
  name: string;
  count: number;
  max: number;
  isRag: boolean;
}) {
  const pct = max > 0 ? Math.round((count / max) * 100) : 0;
  return (
    <div className="tool-usage-row">
      <span className="tool-usage-name">{name}</span>
      <div className="tool-usage-bar">
        <div className={`tool-usage-fill${isRag ? " rag" : ""}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="tool-usage-count">{count}</span>
    </div>
  );
}
