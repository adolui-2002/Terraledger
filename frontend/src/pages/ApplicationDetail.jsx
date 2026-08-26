import {
  AlertTriangle, CheckCircle2, Download, FileText, Loader2, MessageSquare,
  PlayCircle, ShieldAlert, Sparkles, ThumbsDown, ThumbsUp, Upload, XCircle,
} from "lucide-react";
import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";

import { Applications, Assistant, Documents, Feedback, Reports, Review } from "../api/client";
import AssistantPanel from "../components/AssistantPanel";
import RiskBadge from "../components/RiskBadge";
import ScoreGauge from "../components/ScoreGauge";
import StatusBadge from "../components/StatusBadge";
import Timeline from "../components/Timeline";
import TopBar from "../components/TopBar";

const DOC_TYPES = ["APPLICATION_FORM", "PROPOSAL", "BUDGET", "CERTIFICATE", "PREVIOUS_REPORT", "PHOTO", "OTHER"];
const NON_REPROCESSABLE = ["UNDER_REVIEW", "NEEDS_INFO", "APPROVED", "REJECTED", "CLOSED"];
const INLINE_EXTENSIONS = new Set([".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".txt"]);

const STATUS_ICON = {
  PASS: <CheckCircle2 size={14} className="text-moss" />,
  WARNING: <AlertTriangle size={14} className="text-gold" />,
  FAIL: <XCircle size={14} className="text-clay" />,
};

export default function ApplicationDetail() {
  const { id } = useParams();
  const [app, setApp] = useState(null);
  const [audit, setAudit] = useState([]);
  const [reviewers, setReviewers] = useState([]);
  const [docType, setDocType] = useState("APPLICATION_FORM");
  const [busy, setBusy] = useState(false);
  const [summary, setSummary] = useState(null);
  const [summaryLoading, setSummaryLoading] = useState(false);
  const [summaryError, setSummaryError] = useState("");
  const [feedbackList, setFeedbackList] = useState([]);
  const [feedbackForm, setFeedbackForm] = useState({
    reviewer_name: "", rating: "HELPFUL", score_accuracy: "ACCURATE", comment: "",
  });
  const [feedbackSubmitted, setFeedbackSubmitted] = useState(false);
  const [feedbackBusy, setFeedbackBusy] = useState(false);
  const [decisionForm, setDecisionForm] = useState({ reviewer_name: "", human_decision: "APPROVED", override_reason: "", notes: "" });
  const [error, setError] = useState("");

  function refresh() {
    Applications.get(id).then(setApp);
    Applications.audit(id).then(setAudit);
    Feedback.list(id).then(setFeedbackList).catch(() => {});
  }

  useEffect(() => {
    refresh();
    Review.reviewers().then(setReviewers).catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  if (!app) return <div className="p-8 text-ink_text-muted">Loading…</div>;

  const latestScore = app.scores.length ? app.scores[app.scores.length - 1] : null;

  async function handleGenerateSummary() {
    setSummaryLoading(true);
    setSummaryError("");
    try {
      const result = await Assistant.summarize(id);
      setSummary(result);
    } catch (err) {
      setSummaryError(err?.response?.data?.detail || "Could not generate summary.");
    } finally {
      setSummaryLoading(false);
    }
  }

  async function handleUpload(e) {
    const file = e.target.files[0];
    if (!file) return;
    setBusy(true);
    try {
      await Applications.uploadDocument(id, docType, file);
      refresh();
    } finally {
      setBusy(false);
      e.target.value = "";
    }
  }

  async function handleProcess() {
    setBusy(true);
    setError("");
    try {
      await Applications.process(id);
      refresh();
    } catch (err) {
      setError(err?.response?.data?.detail || "Processing failed.");
    } finally {
      setBusy(false);
    }
  }

  async function handleAssign(reviewerName) {
    await Review.assign(id, reviewerName);
    refresh();
  }

  async function handleDecision(e) {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      await Review.decide(id, decisionForm);
      refresh();
    } catch (err) {
      setError(err?.response?.data?.detail || "Could not record decision.");
    } finally {
      setBusy(false);
    }
  }

  async function handleFeedback(e) {
    e.preventDefault();
    setFeedbackBusy(true);
    try {
      const latestScoreId = app.scores.length
        ? app.scores[app.scores.length - 1].id
        : undefined;
      await Feedback.submit(id, { ...feedbackForm, score_id: latestScoreId });
      setFeedbackSubmitted(true);
      refresh();
    } finally {
      setFeedbackBusy(false);
    }
  }

  return (
    <div>
      <TopBar title={app.reference_code} subtitle={`${app.applicant_name} · ${app.scheme_name}`} showNew={false} />

      <div className="grid grid-cols-1 gap-6 px-8 py-6 xl:grid-cols-3">
        {/* LEFT: main content */}
        <div className="space-y-6 xl:col-span-2">
          {/* Overview */}
          <div className="panel p-6">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="flex items-center gap-3">
                <StatusBadge status={app.status} />
                {latestScore && <RiskBadge level={latestScore.risk_level} />}
                {app.synthetic_category && (
                  <span className="font-mono text-[10px] uppercase tracking-wide text-ink_text-faint">
                    synthetic:{app.synthetic_category}
                  </span>
                )}
              </div>
              {!NON_REPROCESSABLE.includes(app.status) && (
                <button className="btn-primary" onClick={handleProcess} disabled={busy || app.documents.length === 0}>
                  <PlayCircle size={15} />
                  {app.scores.length ? "Re-run pipeline" : "Run pipeline"}
                </button>
              )}
              <a
                href={Reports.applicationPDFUrl(app.id)}
                target="_blank"
                rel="noopener noreferrer"
                className="btn-secondary py-1.5 px-3 text-xs flex items-center gap-1.5"
                title="Download reviewer report as PDF"
              >
                <Download size={13} /> Export PDF
              </a>
            </div>
            {error && (
              <p className="mt-3 rounded-lg border border-clay-dim bg-clay-dim/20 px-3 py-2 text-sm text-clay-soft">
                {error}
              </p>
            )}
            <dl className="mt-5 grid grid-cols-2 gap-4 text-sm sm:grid-cols-3">
              <div>
                <dt className="eyebrow">Requested amount</dt>
                <dd className="mt-1 text-ink_text-primary">
                  {app.requested_amount ? `₹${app.requested_amount.toLocaleString()}` : "—"}
                </dd>
              </div>
              <div>
                <dt className="eyebrow">Assigned reviewer</dt>
                <dd className="mt-1 text-ink_text-primary">{app.assigned_reviewer || "Unassigned"}</dd>
              </div>
              <div>
                <dt className="eyebrow">Submitted</dt>
                <dd className="mt-1 text-ink_text-primary">{new Date(app.submitted_at).toLocaleDateString()}</dd>
              </div>
            </dl>
            {!app.assigned_reviewer && reviewers.length > 0 && (
              <div className="mt-4 flex items-center gap-2">
                <span className="text-xs text-ink_text-muted">Assign to:</span>
                {reviewers.map((r) => (
                  <button key={r.name} className="btn-secondary py-1 px-2.5 text-xs" onClick={() => handleAssign(r.name)}>
                    {r.name}
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* AI Summary */}
          {app.scores.length > 0 && (
            <div className="panel p-6">
              <div className="flex items-center justify-between mb-4">
                <h3 className="font-display text-lg font-semibold text-ink_text-primary flex items-center gap-2">
                  <Sparkles size={16} className="text-gold" />
                  AI Summary
                </h3>
                <button
                  className="btn-secondary py-1.5 px-3 text-xs"
                  onClick={handleGenerateSummary}
                  disabled={summaryLoading}
                >
                  {summaryLoading
                    ? <><Loader2 size={12} className="animate-spin" /> Generating…</>
                    : summary ? "Regenerate" : "Generate summary"
                  }
                </button>
              </div>

              {summaryError && (
                <p className="text-sm text-clay-soft">{summaryError}</p>
              )}

              {!summary && !summaryLoading && !summaryError && (
                <p className="text-sm text-ink_text-faint">
                  Click "Generate summary" to get an AI-assisted overview of this application for reviewer briefing.
                </p>
              )}

              {summary && (
                <div className="space-y-4">
                  {/* Prose summary */}
                  <p className="text-sm leading-relaxed text-ink_text-primary">{summary.summary}</p>

                  {/* Quick-glance chips */}
                  <div className="flex flex-wrap gap-2">
                    <span className="rounded-full border border-border px-2.5 py-1 text-[11px] text-ink_text-muted">
                      {summary.document_count} document{summary.document_count !== 1 ? "s" : ""}
                    </span>
                    {summary.total_score != null && (
                      <span className="rounded-full border border-border px-2.5 py-1 text-[11px] font-mono text-ink_text-muted">
                        score {summary.total_score}/100
                      </span>
                    )}
                    {summary.risk_level && (
                      <span className={`rounded-full border px-2.5 py-1 text-[11px] font-mono uppercase ${
                        summary.risk_level === "HIGH"
                          ? "border-clay-dim text-clay-soft"
                          : summary.risk_level === "MEDIUM"
                          ? "border-gold-dim text-gold-soft"
                          : "border-moss-dim text-moss-soft"
                      }`}>
                        {summary.risk_level} risk
                      </span>
                    )}
                    {summary.has_fraud_signals && (
                      <span className="rounded-full border border-clay-dim px-2.5 py-1 text-[11px] text-clay-soft">
                        ⚠ fraud signals
                      </span>
                    )}
                    {summary.has_validation_failures && (
                      <span className="rounded-full border border-gold-dim px-2.5 py-1 text-[11px] text-gold-soft">
                        ⚠ validation failures
                      </span>
                    )}
                  </div>

                  {/* Structured digest toggle */}
                  <details className="group">
                    <summary className="cursor-pointer text-[11px] text-ink_text-faint hover:text-ink_text-muted select-none">
                      View structured digest used as AI input ▸
                    </summary>
                    <pre className="mt-2 rounded-lg border border-border bg-ink-soft p-3 text-[11px] leading-relaxed text-ink_text-muted whitespace-pre-wrap">
                      {summary.structured_digest}
                    </pre>
                  </details>

                  <p className="text-[10px] text-ink_text-faint italic">
                    AI-generated summary for reviewer briefing only. Final determination rests with the assigned reviewer.
                  </p>
                </div>
              )}
            </div>
          )}

          {/* Documents */}
          <div className="panel p-6">
            <div className="mb-4 flex items-center justify-between">
              <h3 className="font-display text-lg font-semibold text-ink_text-primary">Documents</h3>
              <div className="flex items-center gap-2">
                <select className="input w-44" value={docType} onChange={(e) => setDocType(e.target.value)}>
                  {DOC_TYPES.map((t) => <option key={t} value={t}>{t.replaceAll("_", " ")}</option>)}
                </select>
                <label className="btn-secondary cursor-pointer">
                  <Upload size={14} /> Upload
                  <input type="file" className="hidden" onChange={handleUpload} disabled={busy} />
                </label>
              </div>
            </div>
            <div className="space-y-2">
              {app.documents.length === 0 && <p className="text-sm text-ink_text-faint">No documents uploaded yet.</p>}
              {app.documents.map((d) => (
                <div key={d.id} className="flex items-center justify-between rounded-lg border border-border px-3 py-2">
                  <div className="flex items-center gap-2.5">
                    <FileText size={14} className="text-ink_text-faint" />
                    <span className="text-sm text-ink_text-primary">{d.filename}</span>
                    <span className="font-mono text-[10px] uppercase text-ink_text-faint">{d.doc_type}</span>
                  </div>
                  <div className="flex items-center gap-3 text-xs text-ink_text-muted">
                    {d.ocr_used && <span>OCR conf. {(d.ocr_confidence * 100).toFixed(0)}%</span>}
                    <span className="font-mono uppercase">{d.detected_language}</span>
                    {(() => {
                      const ext = d.filename.slice(d.filename.lastIndexOf(".")).toLowerCase();
                      const isInline = INLINE_EXTENSIONS.has(ext);
                      return (
                        <a
                          href={Documents.downloadUrl(d.id)}
                          target={isInline ? "_blank" : undefined}
                          rel={isInline ? "noopener noreferrer" : undefined}
                          download={isInline ? undefined : d.filename}
                          className="rounded p-1 text-ink_text-muted transition-colors hover:bg-gold/15 hover:text-gold"
                          title={isInline ? `Open ${d.filename}` : `Download ${d.filename}`}
                        >
                          <Download size={13} />
                        </a>
                      );
                    })()}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Validation */}
          {app.validation_results.length > 0 && (
            <div className="panel p-6">
              <h3 className="mb-4 font-display text-lg font-semibold text-ink_text-primary">Validation</h3>
              <div className="space-y-2">
                {app.validation_results.map((v, i) => (
                  <div key={i} className="flex items-start gap-2.5 text-sm">
                    {STATUS_ICON[v.status]}
                    <div>
                      <span className="font-medium text-ink_text-primary">{v.check_name.replaceAll("_", " ")}: </span>
                      <span className="text-ink_text-muted">{v.message}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Fraud signals */}
          {app.fraud_signals.length > 0 && (
            <div className="panel border-clay-dim p-6">
              <h3 className="mb-4 flex items-center gap-2 font-display text-lg font-semibold text-clay-soft">
                <ShieldAlert size={17} /> Fraud &amp; risk signals
              </h3>
              <div className="space-y-2">
                {app.fraud_signals.map((f, i) => (
                  <div key={i} className="rounded-lg border border-clay-dim bg-clay-dim/10 px-3 py-2 text-sm">
                    <span className="font-mono text-[10px] uppercase tracking-wide text-clay-soft">
                      {f.signal_type} · {f.severity}
                    </span>
                    <p className="mt-0.5 text-ink_text-primary">{f.description}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Review decision form */}
          {app.status !== "CLOSED" && (
            <div className="panel p-6">
              <h3 className="mb-4 font-display text-lg font-semibold text-ink_text-primary">Record review decision</h3>
              <form onSubmit={handleDecision} className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="label">Reviewer</label>
                    <select
                      className="input"
                      value={decisionForm.reviewer_name}
                      onChange={(e) => setDecisionForm({ ...decisionForm, reviewer_name: e.target.value })}
                      required
                    >
                      <option value="">Select reviewer…</option>
                      {reviewers.map((r) => <option key={r.name} value={r.name}>{r.name}</option>)}
                    </select>
                  </div>
                  <div>
                    <label className="label">Decision</label>
                    <select
                      className="input"
                      value={decisionForm.human_decision}
                      onChange={(e) => setDecisionForm({ ...decisionForm, human_decision: e.target.value })}
                    >
                      <option value="APPROVED">Approve</option>
                      <option value="REJECTED">Reject</option>
                      <option value="NEEDS_INFO">Request more information</option>
                    </select>
                  </div>
                </div>
                <div>
                  <label className="label">Override reason (required if this differs from the AI recommendation)</label>
                  <textarea
                    className="input"
                    rows={2}
                    value={decisionForm.override_reason}
                    onChange={(e) => setDecisionForm({ ...decisionForm, override_reason: e.target.value })}
                  />
                </div>
                <div>
                  <label className="label">Notes</label>
                  <textarea
                    className="input"
                    rows={2}
                    value={decisionForm.notes}
                    onChange={(e) => setDecisionForm({ ...decisionForm, notes: e.target.value })}
                  />
                </div>
                <button className="btn-primary" type="submit" disabled={busy}>Submit decision</button>
              </form>
            </div>
          )}

          {/* Audit trail */}
          <div className="panel p-6">
            <h3 className="mb-4 font-display text-lg font-semibold text-ink_text-primary">Audit trail</h3>
            <Timeline entries={audit} />
          </div>
        </div>

        {/* RIGHT: score + assistant */}
        <div className="space-y-6">
          {latestScore ? (
            <div className="panel p-6 text-center">
              <p className="eyebrow mb-4">AI Recommendation</p>
              <div className="flex justify-center">
                <ScoreGauge score={latestScore.total_score} riskLevel={latestScore.risk_level} />
              </div>
              <p className="mt-3 font-display text-base font-semibold text-ink_text-primary">
                {latestScore.ai_recommendation.replaceAll("_", " ")}
              </p>
              <p className="text-xs text-ink_text-muted">confidence {(latestScore.confidence * 100).toFixed(0)}%</p>

              <div className="mt-5 space-y-1.5 text-left">
                {Object.entries(latestScore.breakdown).map(([cat, pts]) => (
                  <div key={cat} className="flex items-center justify-between text-xs">
                    <span className="text-ink_text-muted">{cat.replaceAll("_", " ")}</span>
                    <span className="font-mono text-ink_text-primary">
                      {pts}/{latestScore.max_breakdown[cat]}
                    </span>
                  </div>
                ))}
              </div>

              {latestScore.ml_approval_probability != null && (
                <div className="mt-5 rounded-lg border border-border bg-ink-soft p-3 text-left">
                  <div className="mb-1.5 flex items-center gap-1.5">
                    <Sparkles size={12} className="text-gold" />
                    <span className="eyebrow">ML second opinion</span>
                    {latestScore.model_agreement && (
                      <span className={`ml-auto text-[10px] font-mono uppercase ${
                        latestScore.model_agreement === "AGREE" ? "text-moss-soft" : "text-clay-soft"
                      }`}>
                        {latestScore.model_agreement}
                      </span>
                    )}
                  </div>
                  <p className="text-sm text-ink_text-primary">
                    {(latestScore.ml_approval_probability * 100).toFixed(0)}% predicted approval likelihood
                  </p>
                  <div className="mt-2 space-y-1">
                    {latestScore.shap_explanation.slice(0, 4).map((f, i) => (
                      <div key={i} className="flex items-center justify-between text-[11px]">
                        <span className="text-ink_text-muted">{f.feature}</span>
                        <span className={f.direction === "increases" ? "text-moss-soft" : "text-clay-soft"}>
                          {f.direction === "increases" ? "▲" : "▼"} {Math.abs(f.contribution)}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              <div className="mt-5 space-y-1.5 text-left">
                {latestScore.reasons_positive.map((r, i) => (
                  <p key={`p${i}`} className="text-xs text-moss-soft">✓ {r}</p>
                ))}
                {latestScore.reasons_concern.map((r, i) => (
                  <p key={`c${i}`} className="text-xs text-clay-soft">⚠ {r}</p>
                ))}
              </div>
            </div>
          ) : (
            <div className="panel p-6 text-center text-sm text-ink_text-faint">
              Upload documents and run the pipeline to see a score.
            </div>
          )}

          <AssistantPanel applicationId={id} compact />

          {/* AI Feedback */}
          {latestScore && (
            <div className="panel p-6">
              <h3 className="mb-4 font-display text-base font-semibold text-ink_text-primary flex items-center gap-2">
                <MessageSquare size={15} className="text-gold" />
                Rate AI Scoring
              </h3>

              {feedbackSubmitted ? (
                <div className="rounded-lg border border-moss-dim bg-moss/10 px-3 py-3 text-sm text-moss-soft">
                  ✓ Feedback recorded. Thank you for helping improve the AI.
                  <button
                    className="ml-2 text-xs text-ink_text-muted underline"
                    onClick={() => setFeedbackSubmitted(false)}
                  >
                    Submit another
                  </button>
                </div>
              ) : (
                <form onSubmit={handleFeedback} className="space-y-3">
                  <div>
                    <label className="label">Your name</label>
                    <select
                      className="input"
                      value={feedbackForm.reviewer_name}
                      onChange={(e) => setFeedbackForm({ ...feedbackForm, reviewer_name: e.target.value })}
                      required
                    >
                      <option value="">Select reviewer…</option>
                      {reviewers.map((r) => (
                        <option key={r.name} value={r.name}>{r.name}</option>
                      ))}
                    </select>
                  </div>

                  <div>
                    <label className="label">Was the AI recommendation useful?</label>
                    <div className="flex gap-2">
                      {[
                        { v: "HELPFUL", icon: <ThumbsUp size={13} />, label: "Helpful" },
                        { v: "PARTIALLY_HELPFUL", label: "Partially" },
                        { v: "NOT_HELPFUL", icon: <ThumbsDown size={13} />, label: "Not helpful" },
                      ].map(({ v, icon, label }) => (
                        <button
                          key={v}
                          type="button"
                          onClick={() => setFeedbackForm({ ...feedbackForm, rating: v })}
                          className={`flex-1 flex items-center justify-center gap-1 rounded-lg border py-1.5 text-xs transition-colors ${
                            feedbackForm.rating === v
                              ? "border-gold-dim bg-gold/15 text-gold"
                              : "border-border text-ink_text-muted hover:border-gold-dim"
                          }`}
                        >
                          {icon}{label}
                        </button>
                      ))}
                    </div>
                  </div>

                  <div>
                    <label className="label">Was the score accurate?</label>
                    <div className="flex gap-2">
                      {[
                        { v: "ACCURATE", label: "Accurate" },
                        { v: "PARTIALLY_ACCURATE", label: "Partial" },
                        { v: "INACCURATE", label: "Inaccurate" },
                      ].map(({ v, label }) => (
                        <button
                          key={v}
                          type="button"
                          onClick={() => setFeedbackForm({ ...feedbackForm, score_accuracy: v })}
                          className={`flex-1 rounded-lg border py-1.5 text-xs transition-colors ${
                            feedbackForm.score_accuracy === v
                              ? "border-gold-dim bg-gold/15 text-gold"
                              : "border-border text-ink_text-muted hover:border-gold-dim"
                          }`}
                        >
                          {label}
                        </button>
                      ))}
                    </div>
                  </div>

                  <div>
                    <label className="label">Comment (optional)</label>
                    <textarea
                      className="input"
                      rows={2}
                      placeholder="e.g. Score too high given missing documents…"
                      value={feedbackForm.comment}
                      onChange={(e) => setFeedbackForm({ ...feedbackForm, comment: e.target.value })}
                    />
                  </div>

                  <button className="btn-primary w-full justify-center text-xs" type="submit" disabled={feedbackBusy}>
                    {feedbackBusy ? <Loader2 size={12} className="animate-spin" /> : "Submit feedback"}
                  </button>
                </form>
              )}

              {feedbackList.length > 0 && (
                <div className="mt-4 space-y-2 border-t border-border pt-4">
                  <p className="eyebrow mb-2">Previous feedback ({feedbackList.length})</p>
                  {feedbackList.slice(0, 3).map((f) => (
                    <div key={f.id} className="rounded-lg border border-border bg-ink-soft px-3 py-2 text-xs">
                      <div className="flex items-center justify-between">
                        <span className="font-medium text-ink_text-primary">{f.reviewer_name}</span>
                        <span className="text-ink_text-faint">{new Date(f.submitted_at).toLocaleDateString()}</span>
                      </div>
                      <div className="mt-1 flex gap-2 text-ink_text-muted">
                        <span className={f.rating === "HELPFUL" ? "text-moss-soft" : f.rating === "NOT_HELPFUL" ? "text-clay-soft" : ""}>
                          {f.rating.replaceAll("_", " ")}
                        </span>
                        <span>·</span>
                        <span>{f.score_accuracy.replaceAll("_", " ")}</span>
                      </div>
                      {f.comment && <p className="mt-1 text-ink_text-muted italic">{f.comment}</p>}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
