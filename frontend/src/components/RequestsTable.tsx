import type { AdminRequestRow } from "../lib/types";

function formatUsd(n: number): string {
  return `$${n.toFixed(4)}`;
}

export function RequestsTable({ requests }: { requests: AdminRequestRow[] }) {
  if (requests.length === 0) {
    return <div className="loading">No requests logged yet — send a chat message to see it here.</div>;
  }
  return (
    <table className="requests-table">
      <thead>
        <tr>
          <th>Time</th>
          <th>Query</th>
          <th>Status</th>
          <th>Tools</th>
          <th>Tokens (in/out)</th>
          <th>Cost</th>
          <th>Latency</th>
        </tr>
      </thead>
      <tbody>
        {requests.map((r) => (
          <tr key={r.id}>
            <td className="mono">{r.created_at}</td>
            <td className="query-cell">{r.query}</td>
            <td className={r.status === "ok" ? "status-ok" : "status-error"}>{r.status}</td>
            <td className="mono">{r.tool_calls.join(", ") || "—"}</td>
            <td className="mono">
              {r.input_tokens} / {r.output_tokens}
            </td>
            <td className="mono">{formatUsd(r.estimated_cost_usd)}</td>
            <td className="mono">{(r.latency_ms / 1000).toFixed(1)}s</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
