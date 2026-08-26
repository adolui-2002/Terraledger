import { CheckCircle2, Upload } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { Applications } from "../api/client";
import TopBar from "../components/TopBar";

const DOC_TYPES = [
  { key: "APPLICATION_FORM", label: "Application form", required: true },
  { key: "PROPOSAL", label: "Proposal", required: true },
  { key: "BUDGET", label: "Budget", required: true },
  { key: "CERTIFICATE", label: "Certificate", required: true },
  { key: "PREVIOUS_REPORT", label: "Previous report", required: false },
];

export default function NewApplication() {
  const navigate = useNavigate();
  const [form, setForm] = useState({
    applicant_name: "", scheme_name: "Environmental Scheme", applicant_bank_ref: "",
    requested_amount: "", language: "en",
  });
  const [files, setFiles] = useState({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const created = await Applications.create({
        ...form,
        requested_amount: form.requested_amount ? Number(form.requested_amount) : null,
      });
      for (const [docType, file] of Object.entries(files)) {
        if (file) await Applications.uploadDocument(created.id, docType, file);
      }
      if (Object.values(files).some(Boolean)) {
        await Applications.process(created.id);
      }
      navigate(`/applications/${created.id}`);
    } catch (err) {
      setError(err?.response?.data?.detail || "Could not create application.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <TopBar title="New Application" subtitle="Submit a scheme application for processing" showNew={false} />
      <form onSubmit={handleSubmit} className="mx-auto max-w-2xl space-y-6 px-8 py-8">
        {error && (
          <p className="rounded-lg border border-clay-dim bg-clay-dim/20 px-3 py-2 text-sm text-clay-soft">{error}</p>
        )}

        <div className="panel space-y-4 p-6">
          <h3 className="font-display text-lg font-semibold text-ink_text-primary">Applicant details</h3>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="label">Applicant name</label>
              <input className="input" required value={form.applicant_name}
                onChange={(e) => setForm({ ...form, applicant_name: e.target.value })} />
            </div>
            <div>
              <label className="label">Scheme</label>
              <select className="input" value={form.scheme_name}
                onChange={(e) => setForm({ ...form, scheme_name: e.target.value })}>
                <option>Environmental Scheme</option>
                <option>Climate Resilience Grant</option>
              </select>
            </div>
            <div>
              <label className="label">Bank reference</label>
              <input className="input" value={form.applicant_bank_ref}
                onChange={(e) => setForm({ ...form, applicant_bank_ref: e.target.value })} />
            </div>
            <div>
              <label className="label">Requested amount (₹)</label>
              <input type="number" className="input" value={form.requested_amount}
                onChange={(e) => setForm({ ...form, requested_amount: e.target.value })} />
            </div>
            <div className="col-span-2">
              <label className="label">Application language</label>
              <select className="input" value={form.language}
                onChange={(e) => setForm({ ...form, language: e.target.value })}>
                <option value="en">English</option>
                <option value="hi">Hindi — हिंदी</option>
                <option value="bn">Bengali — বাংলা</option>
                <option value="ta">Tamil — தமிழ்</option>
                <option value="te">Telugu — తెలుగు</option>
                <option value="mr">Marathi — मराठी</option>
                <option value="gu">Gujarati — ગુજરાતી</option>
                <option value="kn">Kannada — ಕನ್ನಡ</option>
                <option value="ml">Malayalam — മലയാളം</option>
                <option value="pa">Punjabi — ਪੰਜਾਬੀ</option>
                <option value="ur">Urdu — اردو</option>
              </select>
              {form.language !== "en" && (
                <p className="mt-1.5 text-[11px] text-gold-soft">
                  Non-English documents will be language-detected automatically. Enable a translation adapter for full extraction support.
                </p>
              )}
            </div>
          </div>
        </div>

        <div className="panel space-y-3 p-6">
          <h3 className="mb-1 font-display text-lg font-semibold text-ink_text-primary">Documents</h3>
          <p className="mb-3 text-xs text-ink_text-muted">
            Attach files now to run the pipeline immediately, or leave blank and upload later from the application page.
          </p>
          {DOC_TYPES.map((d) => (
            <div key={d.key} className="flex items-center justify-between rounded-lg border border-border px-3 py-2.5">
              <span className="text-sm text-ink_text-primary">
                {d.label} {d.required && <span className="text-clay-soft">*</span>}
              </span>
              <label className="btn-secondary cursor-pointer py-1 text-xs">
                {files[d.key] ? (
                  <span className="flex items-center gap-1 text-moss-soft"><CheckCircle2 size={13} /> {files[d.key].name}</span>
                ) : (
                  <span className="flex items-center gap-1"><Upload size={13} /> Choose file</span>
                )}
                <input type="file" className="hidden"
                  onChange={(e) => setFiles({ ...files, [d.key]: e.target.files[0] })} />
              </label>
            </div>
          ))}
        </div>

        <button className="btn-primary w-full justify-center py-2.5" type="submit" disabled={busy}>
          {busy ? "Submitting…" : "Submit application"}
        </button>
      </form>
    </div>
  );
}
