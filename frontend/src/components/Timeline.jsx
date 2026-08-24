const ACTION_LABELS = {
  APPLICATION_SUBMITTED: "Application submitted",
  DOCUMENT_UPLOADED: "Document uploaded",
  EXTRACTION_COMPLETE: "Extraction complete",
  FRAUD_SIGNALS_DETECTED: "Fraud signals detected",
  STATUS_CHANGE: "Status changed",
  REVIEWER_ASSIGNED: "Reviewer assigned",
  REVIEW_DECISION: "Review decision recorded",
};

function formatDetails(action, details) {
  if (!details) return null;
  if (action === "STATUS_CHANGE") return `${details.from} \u2192 ${details.to}`;
  if (action === "DOCUMENT_UPLOADED") return `${details.filename} (${details.doc_type})`;
  if (action === "REVIEWER_ASSIGNED") return details.reviewer;
  if (action === "REVIEW_DECISION")
    return `${details.decision}${details.override ? " (override)" : ""}${
      details.reason ? ` \u2014 ${details.reason}` : ""
    }`;
  if (action === "FRAUD_SIGNALS_DETECTED") return `${details.count} signal(s): ${(details.types || []).join(", ")}`;
  return Object.entries(details)
    .map(([k, v]) => `${k}: ${v}`)
    .join(", ");
}

export default function Timeline({ entries = [] }) {
  if (entries.length === 0) {
    return <p className="text-sm text-ink_text-muted">No audit history yet.</p>;
  }
  return (
    <ol className="relative border-l border-border pl-5">
      {entries.map((entry, i) => (
        <li key={i} className="mb-5 last:mb-0">
          <span className="absolute -left-[5px] mt-1.5 h-2 w-2 rounded-full bg-gold" />
          <div className="flex flex-wrap items-baseline gap-x-2">
            <span className="font-mono text-[11px] text-ink_text-faint">
              {new Date(entry.timestamp).toLocaleString()}
            </span>
            <span className="text-sm font-medium text-ink_text-primary">
              {ACTION_LABELS[entry.action] || entry.action}
            </span>
            <span className="font-mono text-[11px] text-teal-soft">{entry.actor}</span>
          </div>
          {formatDetails(entry.action, entry.details) && (
            <p className="mt-0.5 text-xs text-ink_text-muted">{formatDetails(entry.action, entry.details)}</p>
          )}
        </li>
      ))}
    </ol>
  );
}
