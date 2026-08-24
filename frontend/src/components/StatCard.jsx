export default function StatCard({ label, value, sublabel, icon: Icon, accent = "gold" }) {
  const accentColor = {
    gold: "text-gold",
    moss: "text-moss",
    clay: "text-clay",
    teal: "text-teal",
  }[accent];

  return (
    <div className="panel p-5">
      <div className="flex items-start justify-between">
        <span className="eyebrow">{label}</span>
        {Icon && <Icon size={16} className={`${accentColor} opacity-80`} />}
      </div>
      <div className="mt-2 font-display text-3xl font-semibold text-ink_text-primary tabular-nums">
        {value}
      </div>
      {sublabel && <div className="mt-1 text-xs text-ink_text-muted">{sublabel}</div>}
    </div>
  );
}
