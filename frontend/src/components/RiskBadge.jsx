const STYLES = {
  LOW: "bg-moss-dim/40 text-moss-soft border-moss-dim",
  MEDIUM: "bg-gold-dim/30 text-gold-soft border-gold-dim",
  HIGH: "bg-clay-dim/40 text-clay-soft border-clay-dim",
};

export default function RiskBadge({ level }) {
  if (!level) return null;
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-[11px] font-mono
                  uppercase tracking-wide ${STYLES[level] || STYLES.LOW}`}
    >
      <span className="h-1.5 w-1.5 rounded-full bg-current" />
      {level} risk
    </span>
  );
}
