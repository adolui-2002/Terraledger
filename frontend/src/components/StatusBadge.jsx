const STATUS_LABELS = {
  SUBMITTED: "Submitted",
  PROCESSING: "Processing",
  VALIDATED: "Validated",
  AI_ANALYZED: "AI Analyzed",
  REVIEW_PENDING: "Review Pending",
  UNDER_REVIEW: "Under Review",
  NEEDS_INFO: "Needs Info",
  APPROVED: "Approved",
  REJECTED: "Rejected",
  CLOSED: "Closed",
};

const STATUS_COLORS = {
  SUBMITTED: "text-ink_text-muted",
  PROCESSING: "text-teal-soft",
  VALIDATED: "text-teal-soft",
  AI_ANALYZED: "text-gold-soft",
  REVIEW_PENDING: "text-gold-soft",
  UNDER_REVIEW: "text-gold",
  NEEDS_INFO: "text-clay-soft",
  APPROVED: "text-moss-soft",
  REJECTED: "text-clay-soft",
  CLOSED: "text-ink_text-faint",
};

export default function StatusBadge({ status }) {
  return (
    <span className={`font-mono text-xs uppercase tracking-wide ${STATUS_COLORS[status] || "text-ink_text-muted"}`}>
      {STATUS_LABELS[status] || status}
    </span>
  );
}
