import { AlertTriangle, Clock, Copy, FileWarning, Gauge, Leaf } from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";

import { Analytics, Applications } from "../api/client";
import ContourBackground from "../components/ContourBackground";
import RiskBadge from "../components/RiskBadge";
import StatCard from "../components/StatCard";
import StatusBadge from "../components/StatusBadge";
import TopBar from "../components/TopBar";

const RISK_COLORS = { LOW: "#5FAE86", MEDIUM: "#D4A54A", HIGH: "#C1584B" };

export default function Dashboard() {
  const [summary, setSummary] = useState(null);
  const [recent, setRecent] = useState([]);

  useEffect(() => {
    Analytics.summary().then(setSummary).catch(() => {});
    Applications.list().then((apps) => setRecent(apps.slice(0, 6))).catch(() => {});
  }, []);

  const riskData = summary
    ? Object.entries(summary.by_risk).map(([name, value]) => ({ name, value }))
    : [];

  return (
    <div>
      <TopBar title="Dashboard" subtitle="Environmental Scheme Application Intelligence Platform" />

      <div className="relative overflow-hidden border-b border-border px-8 py-10">
        <ContourBackground />
        <div className="relative flex items-center gap-4">
          <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-gold/15 text-gold">
            <Leaf size={22} />
          </div>
          <div>
            <p className="eyebrow">Directorate of Environment &amp; Climate Change</p>
            <h2 className="mt-1 font-display text-3xl font-semibold text-ink_text-primary">
              {summary ? summary.total_applications : "—"} applications on record
            </h2>
            <p className="mt-1 text-sm text-ink_text-muted">
              AI recommends, extracts, and flags. Every final determination is made by a human reviewer.
            </p>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-5 px-8 py-8 md:grid-cols-2 xl:grid-cols-4">
        <StatCard
          label="Average score"
          value={summary ? summary.average_score : "—"}
          sublabel="across all analyzed applications"
          icon={Gauge}
          accent="gold"
        />
        <StatCard
          label="Avg. processing time"
          value={summary?.average_processing_hours != null ? `${summary.average_processing_hours}h` : "—"}
          sublabel="submission to AI analysis"
          icon={Clock}
          accent="teal"
        />
        <StatCard
          label="Duplicates flagged"
          value={summary ? summary.duplicates_flagged : "—"}
          sublabel="applicant + bank reference matches"
          icon={Copy}
          accent="clay"
        />
        <StatCard
          label="Missing documents"
          value={summary ? summary.missing_documents_flagged : "—"}
          sublabel="incomplete required document sets"
          icon={FileWarning}
          accent="moss"
        />
      </div>

      <div className="grid grid-cols-1 gap-6 px-8 pb-10 lg:grid-cols-3">
        <div className="panel p-6 lg:col-span-1">
          <h3 className="mb-1 font-display text-lg font-semibold text-ink_text-primary">Risk distribution</h3>
          <p className="mb-4 text-xs text-ink_text-muted">Latest score per application</p>
          {riskData.length > 0 ? (
            <ResponsiveContainer width="100%" height={200}>
              <PieChart>
                <Pie data={riskData} dataKey="value" nameKey="name" innerRadius={45} outerRadius={75} paddingAngle={3}>
                  {riskData.map((entry) => (
                    <Cell key={entry.name} fill={RISK_COLORS[entry.name] || "#8FA89E"} />
                  ))}
                </Pie>
                <Tooltip contentStyle={{ background: "#182D27", border: "1px solid #24413A", borderRadius: 8 }} />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <p className="flex h-[200px] items-center justify-center text-sm text-ink_text-faint">
              No scored applications yet.
            </p>
          )}
          <div className="mt-3 flex justify-center gap-4">
            {riskData.map((r) => (
              <div key={r.name} className="flex items-center gap-1.5 text-xs text-ink_text-muted">
                <span className="h-2 w-2 rounded-full" style={{ background: RISK_COLORS[r.name] }} />
                {r.name} ({r.value})
              </div>
            ))}
          </div>
        </div>

        <div className="panel p-6 lg:col-span-2">
          <div className="mb-4 flex items-center justify-between">
            <h3 className="font-display text-lg font-semibold text-ink_text-primary">Recent applications</h3>
            <Link to="/applications" className="text-xs font-medium text-gold hover:underline">
              View all
            </Link>
          </div>
          <div className="divide-y divide-border">
            {recent.length === 0 && <p className="py-6 text-sm text-ink_text-faint">No applications yet.</p>}
            {recent.map((app) => (
              <Link
                key={app.id}
                to={`/applications/${app.id}`}
                className="flex items-center justify-between gap-4 py-3 hover:bg-surface-raised/60 -mx-2 px-2 rounded-lg transition-colors"
              >
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-xs text-ink_text-faint">{app.reference_code}</span>
                    <span className="text-sm font-medium text-ink_text-primary">{app.applicant_name}</span>
                  </div>
                  <p className="mt-0.5 text-xs text-ink_text-muted">{app.scheme_name}</p>
                </div>
                <div className="flex items-center gap-3">
                  <StatusBadge status={app.status} />
                </div>
              </Link>
            ))}
          </div>
        </div>
      </div>

      {summary && summary.override_rate > 0.3 && (
        <div className="mx-8 mb-8 flex items-center gap-3 rounded-xl border border-clay-dim bg-clay-dim/20 px-4 py-3 text-sm text-clay-soft">
          <AlertTriangle size={16} />
          Reviewer override rate is {(summary.override_rate * 100).toFixed(0)}% — consider revisiting scoring weights.
        </div>
      )}
    </div>
  );
}
