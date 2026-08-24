import { Plus, Search } from "lucide-react";
import { useNavigate } from "react-router-dom";

export default function TopBar({ title, subtitle, onSearch, showNew = true }) {
  const navigate = useNavigate();
  return (
    <header className="sticky top-0 z-10 flex items-center justify-between border-b border-border bg-ink/85 px-8 py-5 backdrop-blur">
      <div>
        <h1 className="font-display text-2xl font-semibold text-ink_text-primary">{title}</h1>
        {subtitle && <p className="mt-0.5 text-sm text-ink_text-muted">{subtitle}</p>}
      </div>
      <div className="flex items-center gap-3">
        {onSearch && (
          <div className="relative">
            <Search size={15} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-ink_text-faint" />
            <input
              type="text"
              placeholder="Search reference or applicant..."
              onChange={(e) => onSearch(e.target.value)}
              className="input w-72 pl-9"
            />
          </div>
        )}
        {showNew && (
          <button className="btn-primary" onClick={() => navigate("/applications/new")}>
            <Plus size={15} />
            New application
          </button>
        )}
      </div>
    </header>
  );
}
