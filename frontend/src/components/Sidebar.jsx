import { BarChart3, ClipboardList, LayoutDashboard, Leaf, MessagesSquare, ScrollText } from "lucide-react";
import { NavLink } from "react-router-dom";

const NAV_ITEMS = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard, end: true },
  { to: "/applications", label: "Applications", icon: ScrollText },
  { to: "/reviewer-queue", label: "Reviewer Queue", icon: ClipboardList },
  { to: "/analytics", label: "Analytics", icon: BarChart3 },
  { to: "/assistant", label: "Assistant", icon: MessagesSquare },
];

export default function Sidebar() {
  return (
    <aside className="fixed inset-y-0 left-0 z-20 flex w-60 flex-col border-r border-border bg-surface/80 backdrop-blur">
      <div className="flex items-center gap-2.5 px-6 py-6">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gold/15 text-gold">
          <Leaf size={17} strokeWidth={2.25} />
        </div>
        <div>
          <div className="font-display text-lg font-semibold leading-none text-ink_text-primary">
            Terraledger
          </div>
          <div className="font-mono text-[10px] uppercase tracking-widest text-ink_text-faint">
            Directorate console
          </div>
        </div>
      </div>

      <nav className="mt-2 flex-1 space-y-1 px-3">
        {NAV_ITEMS.map(({ to, label, icon: Icon, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            className={({ isActive }) =>
              `flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors ${
                isActive
                  ? "bg-gold/12 text-gold"
                  : "text-ink_text-muted hover:bg-surface-raised hover:text-ink_text-primary"
              }`
            }
          >
            <Icon size={16} strokeWidth={2} />
            {label}
          </NavLink>
        ))}
      </nav>

      <div className="border-t border-border px-4 py-4">
        <div className="rounded-lg border border-border bg-ink-soft p-3">
          <div className="eyebrow mb-1">Data sovereignty</div>
          <p className="text-[11px] leading-relaxed text-ink_text-muted">
            Restricted records are processed on this deployment only. No citizen
            data leaves this network.
          </p>
        </div>
      </div>
    </aside>
  );
}
