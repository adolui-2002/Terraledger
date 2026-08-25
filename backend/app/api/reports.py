"""
Reporting & export endpoints.

  GET /api/v1/reports/applications.csv
      Full applications register — one row per application with latest
      score, risk level, AI recommendation, fraud signal count, and
      human decision. Safe to filter by status/reviewer via query params.

  GET /api/v1/reports/applications/{id}/pdf
      Single-application reviewer report as a PDF. Covers all sections
      a reviewer needs: overview, validation, fraud signals, score
      breakdown, ML second opinion, review decisions, and audit trail.

Both endpoints use only structured DB records — no raw document text is
ever included — so they are safe to generate for RESTRICTED applications
regardless of AI_PROVIDER setting.
"""
from __future__ import annotations

import csv
import io
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Application, ReviewDecision

router = APIRouter(prefix="/api/v1/reports", tags=["reports"])


def _safe(text: str) -> str:
    """Replace characters outside latin-1 range so fpdf2 built-in fonts don't crash."""
    return (
        text
        .replace("—", "-")
        .replace("–", "-")
        .replace("\u2019", "'")
        .replace("\u2018", "'")
        .replace("\u201c", '"')
        .replace("\u201d", '"')
        .replace("₹", "Rs.")
        .replace("\u2026", "...")
        .encode("latin-1", errors="replace")
        .decode("latin-1")
    )


# ---------------------------------------------------------------------------
# CSV export — full register
# ---------------------------------------------------------------------------

def _latest_score(application: Application):
    if not application.scores:
        return None
    return sorted(application.scores, key=lambda s: s.created_at)[-1]


def _latest_decision(application: Application):
    if not application.review_decisions:
        return None
    return sorted(application.review_decisions, key=lambda d: d.decided_at)[-1]


@router.get("/applications.csv")
def export_applications_csv(
    status: str | None = None,
    reviewer: str | None = None,
    db: Session = Depends(get_db),
):
    """Export the applications register as a CSV file.

    Query params:
      ?status=APPROVED          filter by application status
      ?reviewer=A.+Sharma       filter by assigned reviewer
    """
    query = db.query(Application)
    if status:
        query = query.filter(Application.status == status)
    if reviewer:
        query = query.filter(Application.assigned_reviewer == reviewer)
    applications = query.order_by(Application.submitted_at.desc()).all()

    buf = io.StringIO()
    writer = csv.writer(buf)

    # Header
    writer.writerow([
        "reference_code",
        "applicant_name",
        "scheme_name",
        "status",
        "sensitivity",
        "requested_amount",
        "assigned_reviewer",
        "submitted_at",
        "total_score",
        "risk_level",
        "ai_recommendation",
        "ml_approval_probability",
        "model_agreement",
        "fraud_signal_count",
        "fraud_high_count",
        "validation_fail_count",
        "human_decision",
        "override_reason",
        "decided_at",
        "language",
        "synthetic_category",
    ])

    for app in applications:
        score = _latest_score(app)
        decision = _latest_decision(app)
        fraud = list(app.fraud_signals)
        writer.writerow([
            app.reference_code,
            app.applicant_name,
            app.scheme_name,
            app.status,
            app.sensitivity,
            app.requested_amount or "",
            app.assigned_reviewer or "",
            app.submitted_at.strftime("%Y-%m-%d %H:%M:%S"),
            score.total_score if score else "",
            score.risk_level if score else "",
            score.ai_recommendation if score else "",
            f"{score.ml_approval_probability:.2f}" if score and score.ml_approval_probability is not None else "",
            score.model_agreement if score else "",
            len(fraud),
            sum(1 for f in fraud if f.severity == "HIGH"),
            sum(1 for v in app.validation_results if v.status == "FAIL"),
            decision.human_decision if decision else "",
            decision.override_reason or "" if decision else "",
            decision.decided_at.strftime("%Y-%m-%d %H:%M:%S") if decision else "",
            app.language,
            app.synthetic_category or "",
        ])

    csv_bytes = buf.getvalue().encode("utf-8-sig")  # BOM for Excel compatibility
    filename = f"applications_export_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
    return Response(
        content=csv_bytes,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ---------------------------------------------------------------------------
# PDF report — single application
# ---------------------------------------------------------------------------

def _pdf_section(pdf, title: str):
    """Add a bold section heading with a rule."""
    pdf.ln(4)
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 7, _safe(title), ln=True)
    pdf.set_draw_color(60, 100, 80)
    pdf.set_line_width(0.4)
    pdf.line(pdf.get_x(), pdf.get_y(), pdf.get_x() + 170, pdf.get_y())
    pdf.ln(2)
    pdf.set_font("Helvetica", "", 9)


def _pdf_row(pdf, label: str, value: str):
    """Two-column label/value row that never overflows or runs inline."""
    label_w = 50
    value_w = 170 - label_w  # usable content width = 210 - 20 left - 20 right = 170

    # Always reset to left margin — previous multi_cell may leave X anywhere
    pdf.set_x(20)
    pdf.set_font("Helvetica", "B", 9)
    pdf.cell(label_w, 6, _safe(label) + ":", ln=False)

    pdf.set_font("Helvetica", "", 9)
    safe_val = _safe(str(value).strip()) if value else "-"
    # multi_cell always ends with a newline, so next call starts at left margin
    pdf.multi_cell(value_w, 6, safe_val)


@router.get("/applications/{application_id}/pdf")
def export_application_pdf(application_id: str, db: Session = Depends(get_db)):
    """Generate a reviewer-ready PDF report for a single application."""
    from fpdf import FPDF

    application = db.get(Application, application_id)
    if not application:
        raise HTTPException(404, "Application not found")

    score = _latest_score(application)
    decision = _latest_decision(application)
    fraud_signals = list(application.fraud_signals)
    validations = list(application.validation_results)
    audit_logs = sorted(application.audit_logs, key=lambda a: a.timestamp)

    pdf = FPDF()
    pdf.set_margins(20, 20, 20)
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=20)

    # ---- Header ----
    pdf.set_fill_color(24, 45, 39)
    pdf.rect(0, 0, 210, 28, "F")
    pdf.set_text_color(212, 165, 74)
    pdf.set_font("Helvetica", "B", 14)
    pdf.set_y(8)
    pdf.cell(0, 8, "Terraledger - Application Review Report", ln=True, align="C")
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(180, 210, 195)
    pdf.cell(0, 5, "Directorate of Environment and Climate Change", ln=True, align="C")
    pdf.set_text_color(40, 40, 40)
    pdf.ln(10)

    # ---- Overview ----
    _pdf_section(pdf, "1. Application Overview")
    _pdf_row(pdf, "Reference", application.reference_code)
    _pdf_row(pdf, "Applicant", application.applicant_name)
    _pdf_row(pdf, "Scheme", application.scheme_name)
    _pdf_row(pdf, "Status", application.status.replace("_", " "))
    _pdf_row(pdf, "Sensitivity", application.sensitivity)
    _pdf_row(pdf, "Requested amount",
             f"Rs. {application.requested_amount:,.0f}" if application.requested_amount else "")
    _pdf_row(pdf, "Language", application.language)
    _pdf_row(pdf, "Assigned reviewer", application.assigned_reviewer or "Unassigned")
    _pdf_row(pdf, "Submitted", application.submitted_at.strftime("%d %b %Y %H:%M UTC"))
    if application.synthetic_category:
        _pdf_row(pdf, "Dataset category", application.synthetic_category)

    # ---- Documents ----
    _pdf_section(pdf, "2. Submitted Documents")
    docs = list(application.documents)
    if docs:
        for d in docs:
            ocr_note = ""
            if d.ocr_used:
                conf = f"{d.ocr_confidence * 100:.0f}%" if d.ocr_confidence is not None else "n/a"
                ocr_note = f"  [OCR conf. {conf}]"
            lang = f"  [{d.detected_language}]" if d.detected_language else ""
            pdf.cell(0, 6, _safe(f"  {d.doc_type.replace('_', ' ')}: {d.filename}{lang}{ocr_note}"), ln=True)
    else:
        pdf.cell(0, 6, "  No documents uploaded.", ln=True)

    # ---- Extracted fields ----
    fields = list(application.extracted_fields)
    if fields:
        _pdf_section(pdf, "3. Extracted Fields")
        for f in fields[:12]:
            pdf.cell(0, 6, _safe(f"  {f.field_name}: {f.field_value}  (confidence {f.confidence:.0%})"), ln=True)

    # ---- Validation ----
    _pdf_section(pdf, "4. Validation Results")
    if validations:
        for v in validations:
            icon = {"PASS": "[PASS]", "WARNING": "[WARN]", "FAIL": "[FAIL]"}.get(v.status, v.status)
            pdf.set_x(20)
            pdf.multi_cell(170, 6, _safe(f"  {icon}  {v.check_name.replace('_', ' ')}: {v.message}"))
    else:
        pdf.cell(0, 6, "  No validation results recorded.", ln=True)

    # ---- Fraud signals ----
    _pdf_section(pdf, "5. Fraud & Risk Signals")
    if fraud_signals:
        for f in fraud_signals:
            pdf.set_x(20)
            pdf.multi_cell(170, 6, _safe(f"  [{f.severity}] {f.signal_type}: {f.description}"))
    else:
        pdf.cell(0, 6, "  No fraud signals detected.", ln=True)

    # ---- Score ----
    _pdf_section(pdf, "6. AI Scoring & Recommendation")
    if score:
        _pdf_row(pdf, "Total score", f"{score.total_score}/100")
        _pdf_row(pdf, "Risk level", score.risk_level)
        _pdf_row(pdf, "AI recommendation", score.ai_recommendation.replace("_", " "))
        _pdf_row(pdf, "Confidence", f"{score.confidence:.0%}")
        pdf.ln(2)
        pdf.set_font("Helvetica", "B", 9)
        pdf.cell(0, 6, "Score breakdown:", ln=True)
        pdf.set_font("Helvetica", "", 9)
        for cat, pts in score.breakdown.items():
            max_pts = score.max_breakdown.get(cat, "?")
            pdf.cell(0, 6, f"    {cat.replace('_', ' ').title()}: {pts} / {max_pts}", ln=True)
        if score.reasons_positive:
            pdf.ln(2)
            pdf.set_font("Helvetica", "B", 9)
            pdf.cell(0, 6, "Positive factors:", ln=True)
            pdf.set_font("Helvetica", "", 9)
            for r in score.reasons_positive:
                pdf.set_x(20)
                pdf.multi_cell(170, 6, _safe(f"    + {r}"))
        if score.reasons_concern:
            pdf.ln(2)
            pdf.set_font("Helvetica", "B", 9)
            pdf.cell(0, 6, "Concerns:", ln=True)
            pdf.set_font("Helvetica", "", 9)
            for r in score.reasons_concern:
                pdf.set_x(20)
                pdf.multi_cell(170, 6, _safe(f"    ! {r}"))
        if score.ml_approval_probability is not None:
            pdf.ln(2)
            pdf.set_font("Helvetica", "B", 9)
            pdf.cell(0, 6, _safe(f"ML second opinion ({score.ml_model_version}):"), ln=True)
            pdf.set_font("Helvetica", "", 9)
            pdf.cell(0, 6, _safe(
                f"    Predicted approval likelihood: {score.ml_approval_probability * 100:.0f}%"
                f"  |  Model agreement: {score.model_agreement}"), ln=True)
            if score.shap_explanation:
                pdf.cell(0, 6, "    Top SHAP factors:", ln=True)
                for feat in score.shap_explanation[:4]:
                    pdf.cell(0, 6, _safe(
                        f"      {feat['feature']}: {feat['direction']} likelihood "
                        f"(contribution {feat['contribution']}, value {feat['value']})"), ln=True)
    else:
        pdf.cell(0, 6, "  Pipeline has not been run yet.", ln=True)

    # ---- Human review decision ----
    _pdf_section(pdf, "7. Human Review Decision")
    if decision:
        _pdf_row(pdf, "Reviewer", decision.reviewer_name)
        _pdf_row(pdf, "Decision", decision.human_decision)
        if decision.ai_recommendation:
            _pdf_row(pdf, "AI recommendation was", decision.ai_recommendation.replace("_", " "))
        if decision.override_reason:
            _pdf_row(pdf, "Override reason", decision.override_reason)
        if decision.notes:
            _pdf_row(pdf, "Notes", decision.notes)
        _pdf_row(pdf, "Decided at", decision.decided_at.strftime("%d %b %Y %H:%M UTC"))
    else:
        pdf.cell(0, 6, "  No human review decision recorded yet.", ln=True)

    # ---- Audit trail ----
    _pdf_section(pdf, "8. Audit Trail")
    if audit_logs:
        for entry in audit_logs:
            ts = entry.timestamp.strftime("%d %b %Y %H:%M")
            details = str(entry.details) if entry.details else ""
            pdf.set_x(20)
            pdf.multi_cell(170, 6, _safe(f"  {ts}  [{entry.actor}]  {entry.action}  {details}"))
    else:
        pdf.cell(0, 6, "  No audit entries recorded.", ln=True)

    # ---- Footer ----
    pdf.ln(6)
    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(130, 130, 130)
    pdf.set_x(20)
    pdf.multi_cell(170, 5, _safe(
        f"Generated: {datetime.utcnow().strftime('%d %b %Y %H:%M UTC')}  |  "
        "This report is for reviewer reference only. "
        "AI scores and recommendations are advisory - final determination is made by the assigned human reviewer."
    ))

    pdf_bytes = bytes(pdf.output())
    filename = f"{application.reference_code}_review_report.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )
