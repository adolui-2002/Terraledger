import { ChevronDown, ChevronUp, Download, FileText } from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { Applications, Documents, Review } from "../api/client";
import RiskBadge from "../components/RiskBadge";
import ScoreGauge from "../components/ScoreGauge";
import StatusBadge from "../components/StatusBadge";
import TopBar from "../components/TopBar";

const QUEUE_STATUSES = ["REVIEW_PENDING", "UNDER_REVIEW", "NEEDS_INFO"];

const INLINE_EXTENSIONS = new Set([".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".txt"]);

function DocumentList({ documents }) {
  if (documents.length === 0) {
    return <p className="text-xs text-ink_text-faint">No documents uploaded.</p>;
  }
  return (
    <ul className="space-y-1.5">
      {documents.map((doc) => {
        const ext = doc.filename.slice(doc.filename.lastIndexOf(".")).toLowerCase();
        const isInline = INLINE_EXTENSIONS.has(ext);
        return (
          <li key={doc.id} className="flex items-center justify-between rounded-md border border-border bg-ink-soft px-2.5 py-1.5">
            <div className="flex min-w-0 items-center gap-2">
              <FileText size={12} className="shrink-0 text-ink_text-faint" />
              <span className="truncate text-xs text-ink_text-primary">{doc.filename}</span>
              <span className="shrink-0 font-mono text-[10px] uppercase text-ink_text-faint">
                {doc.doc_type.replaceAll("_", " ")}
              </span>
            </div>
            <a
              href={Documents.downloadUrl(doc.id)}
              target={isInline ? "_blank" : undefined}
              rel={isInline ? "noopener noreferrer" : undefined}
              download={isInline ? undefined : doc.filename}
              onClick={(e) => e.stopPropagation()}
              className="ml-2 shrink-0 rounded p-1 text-ink_text-muted transition-colors hover:bg-gold/15 hover:text-gold"
              title={isInline ? `Open ${doc.filename}` : `Download ${doc.filename}`}
            >
              <Download size={13} />
            </a>
          </li>
        );
      })}
    </ul>
  );
}

function QueueCard({ app }) {
  const [expanded, setExpanded] = useState(false);
  const score = app.scores?.length ? app.scores[app.scores.length - 1] : null;
  const documents = app.documents ?? [];

  return (
    <div className="panel flex flex-col p-5 transition-colors hover:border-gold-dim">
      {/* Main card row — clicking navigates to detail */}
      <Link to={`/applications/${app.id}`} className="flex items-center gap-4">
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

      {/* Documents toggle */}
      <div className="mt-4 border-t border-border pt-3">
        <button
          onClick={() => setExpanded((v) => !v)}
          className="flex w-full items-center justify-between text-xs text-ink_text-muted hover:text-ink_text-primary transition-colors"
        >
          <span className="flex items-center gap-1.5">
            <FileText size={12} />
            {documents.length} document{documents.length !== 1 ? "s" : ""}
          </span>
          {expanded ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
        </button>

        {expanded && (
          <div className="mt-2.5">
            <DocumentList documents={documents} />
          </div>
        )}
      </div>
    </div>
  );
}

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
          {apps.map((app) => (
            <QueueCard key={app.id} app={app} />
          ))}
        </div>
      </div>
    </div>
  );
}
