import { useEffect, useState } from "react";
import {
  Bar, BarChart, CartesianGrid, Line, LineChart,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";

import { Analytics as AnalyticsApi } from "../api/client";
import StatCard from "../components/StatCard";
import TopBar from "../components/TopBar";

const CHART_GRID = "#24413A";
const CHART_TEXT = "#8FA89E";

export default function Analytics() {
  const [summary, setSummary] = useState(null);
  const [timeline, setTimeline] = useState({});

  useEffect(() => {
    AnalyticsApi.summary().then(setSummary);
    AnalyticsApi.timeline().then(setTimeline);
  }, []);

  const statusData = summary
    ? Object.entries(summary.by_status).map(([name, count]) => ({ name: name.replaceAll("_", " "), count }))
    : [];
  const timelineData = Object.entries(timeline).map(([date, count]) => ({ date, count }));

  return (
    <div>
      <TopBar title="Analytics" subtitle="Operational metrics across the review pipeline" showNew={false} />

      <div className="px-8 py-6 space-y-6">
        <div className="grid grid-cols-2 gap-5 md:grid-cols-4">
          <StatCard label="Total applications" value={summary?.total_applications ?? "—"} accent="gold" />
          <StatCard label="Average score" value={summary?.average_score ?? "—"} accent="teal" />
          <StatCard
            label="Override rate"
            value={summary ? `${(summary.override_rate * 100).toFixed(0)}%` : "—"}
            sublabel="reviewer decisions differing from AI"
            accent="clay"
          />
          <StatCard
            label="Avg. processing time"
            value={summary?.average_processing_hours != null ? `${summary.average_processing_hours}h` : "—"}
            accent="moss"
          />
        </div>

        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          <div className="panel p-6">
            <h3 className="mb-4 font-display text-lg font-semibold text-ink_text-primary">Applications by status</h3>
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={statusData}>
                <CartesianGrid stroke={CHART_GRID} vertical={false} />
                <XAxis dataKey="name" tick={{ fill: CHART_TEXT, fontSize: 10 }} interval={0} angle={-30} textAnchor="end" height={60} />
                <YAxis tick={{ fill: CHART_TEXT, fontSize: 11 }} allowDecimals={false} />
                <Tooltip contentStyle={{ background: "#182D27", border: "1px solid #24413A", borderRadius: 8 }} />
                <Bar dataKey="count" fill="#D4A54A" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>

          <div className="panel p-6">
            <h3 className="mb-4 font-display text-lg font-semibold text-ink_text-primary">Submissions over time</h3>
            <ResponsiveContainer width="100%" height={260}>
              <LineChart data={timelineData}>
                <CartesianGrid stroke={CHART_GRID} vertical={false} />
                <XAxis dataKey="date" tick={{ fill: CHART_TEXT, fontSize: 10 }} />
                <YAxis tick={{ fill: CHART_TEXT, fontSize: 11 }} allowDecimals={false} />
                <Tooltip contentStyle={{ background: "#182D27", border: "1px solid #24413A", borderRadius: 8 }} />
                <Line type="monotone" dataKey="count" stroke="#5FAE86" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>
    </div>
  );
}
