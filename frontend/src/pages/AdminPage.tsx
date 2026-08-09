import { useCallback, useEffect, useState } from "react";
import { Nav } from "../components/Nav";
import { StatCard } from "../components/StatCard";
import { ToolUsageBar } from "../components/ToolUsageBar";
import { RequestsTable } from "../components/RequestsTable";
import { fetchAdminRequests, fetchAdminStats } from "../lib/api";
import type { AdminRequestRow, AdminStats } from "../lib/types";

const RAG_TOOLS = new Set(["search_scouting_context", "get_similar_historical_players"]);

function formatUsd(n: number): string {
  return `$${n.toFixed(4)}`;
}

export function AdminPage() {
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [requests, setRequests] = useState<AdminRequestRow[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      const [s, r] = await Promise.all([fetchAdminStats(), fetchAdminRequests(50)]);
      setStats(s);
      setRequests(r);
      setError(null);
    } catch (err) {
      setError(String((err as Error).message || err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    const interval = setInterval(load, 10000);
    return () => clearInterval(interval);
  }, [load]);

  const maxToolCount = stats ? Math.max(1, ...Object.values(stats.tool_call_counts)) : 1;

  return (
    <>
      <Nav />

      <div className="admin-page">
        <div className="admin-header">
          <h1>Request &amp; token dashboard</h1>
          <button className="refresh-btn" onClick={load}>
            Refresh
          </button>
        </div>

        {loading && <div className="loading">Loading…</div>}
        {error && <div className="error-banner">{error} — is the agent backend running on :8000?</div>}

        {stats && (
          <>
            <div className="stat-grid">
              <StatCard label="Total requests" value={stats.total_requests} />
              <StatCard label="Errors" value={stats.error_count} />
              <StatCard label="Avg latency" value={`${(stats.avg_latency_ms / 1000).toFixed(1)}s`} />
              <StatCard
                label="Total tokens"
                value={(stats.total_input_tokens + stats.total_output_tokens).toLocaleString()}
              />
              <StatCard label="Cache read tokens" value={stats.total_cache_read_tokens.toLocaleString()} />
              <StatCard label="Estimated total cost" value={formatUsd(stats.total_estimated_cost_usd)} accent />
            </div>

            <div className="section-title">Tool call breakdown</div>
            <div className="stat-card">
              {Object.keys(stats.tool_call_counts).length === 0 ? (
                <div style={{ color: "var(--text-faint)", fontSize: 12.5 }}>No tool calls yet.</div>
              ) : (
                Object.entries(stats.tool_call_counts)
                  .sort((a, b) => b[1] - a[1])
                  .map(([name, count]) => (
                    <ToolUsageBar key={name} name={name} count={count} max={maxToolCount} isRag={RAG_TOOLS.has(name)} />
                  ))
              )}
            </div>

            <div className="section-title">Recent requests</div>
            <RequestsTable requests={requests} />
          </>
        )}
      </div>
    </>
  );
}
