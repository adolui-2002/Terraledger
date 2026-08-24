import { useEffect, useState } from "react";

import { Applications } from "../api/client";
import AssistantPanel from "../components/AssistantPanel";
import TopBar from "../components/TopBar";

export default function AssistantPage() {
  const [apps, setApps] = useState([]);
  const [selected, setSelected] = useState("");

  useEffect(() => {
    Applications.list().then(setApps);
  }, []);

  return (
    <div>
      <TopBar title="Reviewer Assistant" subtitle="Ask about any application's score, flags, or history" showNew={false} />
      <div className="mx-auto max-w-2xl px-8 py-6">
        <div className="mb-4">
          <label className="label">Application context (optional)</label>
          <select className="input" value={selected} onChange={(e) => setSelected(e.target.value)}>
            <option value="">General question — no application selected</option>
            {apps.map((a) => (
              <option key={a.id} value={a.id}>{a.reference_code} — {a.applicant_name}</option>
            ))}
          </select>
        </div>
        <AssistantPanel applicationId={selected || null} />
      </div>
    </div>
  );
}
