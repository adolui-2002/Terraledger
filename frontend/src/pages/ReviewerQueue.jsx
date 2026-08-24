import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { Applications, Review } from "../api/client";
import RiskBadge from "../components/RiskBadge";
import ScoreGauge from "../components/ScoreGauge";
import StatusBadge from "../components/StatusBadge";
import TopBar from "../components/TopBar";

const QUEUE_STATUSES = ["REVIEW_PENDING", "UNDER_REVIEW", "NEEDS_INFO"];

export default function ReviewerQueue() {
  const [apps, setApps] = useState([]);
  const [reviewers, setReviewers] = useState([]);
  const [filterReviewer, setFilterReviewer] = useState("");

  function refresh() {
    Promise.all(QUEUE_STATUSES.map((s) => Applications.list({ status: s, reviewer: filterReviewer || undefined })))
      .then((results) => setApps(results.flat()));
  }

  useEffect(() => {
    refresh();
    Review.reviewers().then(setReviewers);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filterReviewer]);

  return (
    <div>
      <TopBar title="Reviewer Queue" subtitle="Applications awaiting human review" showNew={false} />

      <div className="px-8 py-6">
        <div className="mb-5 flex items-center gap-2">
          <button
            onClick={() => setFilterReviewer("")}
            className={`rounded-full border px-3 py-1 text-xs ${!filterReviewer ? "border-gold-dim bg-gold/15 text-gold" : "border-border text-ink_text-muted"}`}
          >
            Everyone
          </button>
          {reviewers.map((r) => (
            <button
              key={r.name}
              onClick={() => setFilterReviewer(r.name)}
              className={`rounded-full border px-3 py-1 text-xs ${filterReviewer === r.name ? "border-gold-dim bg-gold/15 text-gold" : "border-border text-ink_text-muted"}`}
            >
              {r.name}
            </button>
          ))}
        </div>

        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
          {apps.length === 0 && (
            <p className="col-span-full py-12 text-center text-sm text-ink_text-faint">Queue is empty.</p>
          )}
          {apps.map((app) => {
            const score = app.scores?.length ? app.scores[app.scores.length - 1] : null;
            return (
              <Link key={app.id} to={`/applications/${app.id}`} className="panel flex items-center gap-4 p-5 hover:border-gold-dim transition-colors">
                {score && <ScoreGauge score={score.total_score} riskLevel={score.risk_level} size={80} />}
                <div className="min-w-0 flex-1">
                  <p className="font-mono text-[11px] text-ink_text-faint">{app.reference_code}</p>
                  <p className="truncate font-medium text-ink_text-primary">{app.applicant_name}</p>
                  <p className="mb-2 truncate text-xs text-ink_text-muted">{app.scheme_name}</p>
                  <div className="flex flex-wrap items-center gap-2">
                    <StatusBadge status={app.status} />
                    {score && <RiskBadge level={score.risk_level} />}
                  </div>
                  {score && (
                    <p className="mt-1.5 font-mono text-[10px] uppercase tracking-wide text-gold-soft">
                      AI: {score.ai_recommendation.replaceAll("_", " ")}
                    </p>
                  )}
                </div>
              </Link>
            );
          })}
        </div>
      </div>
    </div>
  );
}
