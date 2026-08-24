import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { Applications as ApplicationsApi } from "../api/client";
import RiskBadge from "../components/RiskBadge";
import StatusBadge from "../components/StatusBadge";
import TopBar from "../components/TopBar";

const STATUS_OPTIONS = [
  "", "SUBMITTED", "PROCESSING", "VALIDATED", "AI_ANALYZED", "REVIEW_PENDING",
  "UNDER_REVIEW", "NEEDS_INFO", "APPROVED", "REJECTED", "CLOSED",
];

function latestScore(app) {
  return app.scores && app.scores.length ? app.scores[app.scores.length - 1] : null;
}

export default function Applications() {
  const [apps, setApps] = useState([]);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    ApplicationsApi.list({ status: statusFilter || undefined, q: search || undefined })
      .then(setApps)
      .finally(() => setLoading(false));
  }, [statusFilter, search]);

  return (
    <div>
      <TopBar title="Applications" subtitle="All submitted scheme applications" onSearch={setSearch} />

      <div className="px-8 py-6">
        <div className="mb-4 flex items-center gap-2">
          {STATUS_OPTIONS.map((s) => (
            <button
              key={s || "all"}
              onClick={() => setStatusFilter(s)}
              className={`rounded-full px-3 py-1 text-xs font-mono uppercase tracking-wide transition-colors ${
                statusFilter === s
                  ? "bg-gold/15 text-gold border border-gold-dim"
                  : "text-ink_text-muted border border-border hover:text-ink_text-primary"
              }`}
            >
              {s || "All"}
            </button>
          ))}
        </div>

        <div className="panel overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left">
                <th className="px-4 py-3 font-mono text-[11px] uppercase tracking-wide text-ink_text-faint">Reference</th>
                <th className="px-4 py-3 font-mono text-[11px] uppercase tracking-wide text-ink_text-faint">Applicant</th>
                <th className="px-4 py-3 font-mono text-[11px] uppercase tracking-wide text-ink_text-faint">Scheme</th>
                <th className="px-4 py-3 font-mono text-[11px] uppercase tracking-wide text-ink_text-faint">Status</th>
                <th className="px-4 py-3 font-mono text-[11px] uppercase tracking-wide text-ink_text-faint">Score</th>
                <th className="px-4 py-3 font-mono text-[11px] uppercase tracking-wide text-ink_text-faint">Risk</th>
              </tr>
            </thead>
            <tbody>
              {loading && (
                <tr>
                  <td colSpan={6} className="px-4 py-8 text-center text-ink_text-faint">Loading…</td>
                </tr>
              )}
              {!loading && apps.length === 0 && (
                <tr>
                  <td colSpan={6} className="px-4 py-8 text-center text-ink_text-faint">No applications match.</td>
                </tr>
              )}
              {apps.map((app) => {
                const score = latestScore(app);
                return (
                  <tr key={app.id} className="border-b border-border/60 last:border-0 hover:bg-surface-raised/50">
                    <td className="px-4 py-3">
                      <Link to={`/applications/${app.id}`} className="font-mono text-xs text-gold hover:underline">
                        {app.reference_code}
                      </Link>
                    </td>
                    <td className="px-4 py-3 text-ink_text-primary">{app.applicant_name}</td>
                    <td className="px-4 py-3 text-ink_text-muted">{app.scheme_name}</td>
                    <td className="px-4 py-3"><StatusBadge status={app.status} /></td>
                    <td className="px-4 py-3 font-mono tabular-nums text-ink_text-primary">
                      {score ? `${score.total_score}/100` : "—"}
                    </td>
                    <td className="px-4 py-3"><RiskBadge level={score?.risk_level} /></td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
