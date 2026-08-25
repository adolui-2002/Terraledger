"""
Application summarization service.

Produces a structured, human-readable summary of a submitted application
for use by reviewers. The summary covers:
  - What was submitted (document types, languages, OCR quality)
  - Key extracted fields (amounts, dates, durations)
  - Validation and fraud signal highlights
  - Score and AI recommendation

The AI provider is only ever called with structured field values — never
with raw document text — so RESTRICTED applications are safe to summarize
even when AI_PROVIDER=openai is configured.
"""
from __future__ import annotations

from app.models import Application
from app.services.ai_provider import get_ai_provider


def _build_structured_text(application: Application) -> str:
    """Build a plain-text structured digest from DB records.

    This is the input to the AI provider's summarize() call. It contains
    only structured data (field names, amounts, validation statuses) —
    never raw uploaded document content — so it is safe to pass to any
    provider including cloud ones.
    """
    lines: list[str] = []

    lines.append(f"Application reference: {application.reference_code}")
    lines.append(f"Applicant: {application.applicant_name}")
    lines.append(f"Scheme: {application.scheme_name}")
    lines.append(f"Status: {application.status}")
    if application.requested_amount:
        lines.append(f"Requested amount: Rs. {application.requested_amount:,.0f}")

    # Documents overview
    docs = list(application.documents)
    if docs:
        doc_types = ", ".join(sorted({d.doc_type for d in docs}))
        langs = ", ".join(sorted({d.detected_language for d in docs if d.detected_language}))
        low_ocr = [d for d in docs if d.ocr_used and d.ocr_confidence is not None and d.ocr_confidence < 0.5]
        lines.append(f"Submitted documents ({len(docs)}): {doc_types}.")
        if langs:
            lines.append(f"Detected languages: {langs}.")
        if low_ocr:
            lines.append(
                f"Warning: {len(low_ocr)} document(s) have low OCR confidence "
                f"({', '.join(d.filename for d in low_ocr)}) and may require manual review."
            )

    # Extracted fields
    fields = list(application.extracted_fields)
    if fields:
        field_lines = [f"{f.field_name}: {f.field_value}" for f in fields[:8]]
        lines.append("Extracted fields: " + "; ".join(field_lines) + ".")

    # Validation highlights
    validations = list(application.validation_results)
    fails = [v for v in validations if v.status == "FAIL"]
    warns = [v for v in validations if v.status == "WARNING"]
    passes = [v for v in validations if v.status == "PASS"]
    if passes:
        lines.append(f"Validation passed ({len(passes)} checks).")
    if warns:
        lines.append("Validation warnings: " + "; ".join(v.message for v in warns[:3]) + ".")
    if fails:
        lines.append("Validation failures: " + "; ".join(v.message for v in fails[:3]) + ".")

    # Fraud signals
    fraud = list(application.fraud_signals)
    if fraud:
        high = [f for f in fraud if f.severity == "HIGH"]
        med = [f for f in fraud if f.severity == "MEDIUM"]
        if high:
            lines.append("HIGH fraud signals: " + "; ".join(f.description for f in high) + ".")
        if med:
            lines.append("Medium fraud signals: " + "; ".join(f.description for f in med) + ".")
    else:
        lines.append("No fraud signals detected.")

    # Score and recommendation
    if application.scores:
        latest = sorted(application.scores, key=lambda s: s.created_at)[-1]
        lines.append(
            f"AI score: {latest.total_score}/100. "
            f"Risk level: {latest.risk_level}. "
            f"AI recommendation: {latest.ai_recommendation.replace('_', ' ')}."
        )
        if latest.ml_approval_probability is not None:
            lines.append(
                f"ML model predicted approval likelihood: "
                f"{latest.ml_approval_probability * 100:.0f}% "
                f"(model agreement: {latest.model_agreement})."
            )

    return "\n".join(lines)


def summarize_application(application: Application) -> dict:
    """Return a structured summary dict for the given application.

    Returns:
        {
          "summary": str,          # AI-generated prose summary
          "structured_digest": str, # raw structured text used as AI input
          "document_count": int,
          "has_fraud_signals": bool,
          "has_validation_failures": bool,
          "ai_recommendation": str | None,
          "risk_level": str | None,
          "total_score": float | None,
        }
    """
    structured = _build_structured_text(application)
    ai = get_ai_provider()
    summary_text = ai.summarize(structured, max_sentences=5)

    latest_score = None
    if application.scores:
        latest_score = sorted(application.scores, key=lambda s: s.created_at)[-1]

    return {
        "summary": summary_text,
        "structured_digest": structured,
        "document_count": len(list(application.documents)),
        "has_fraud_signals": len(list(application.fraud_signals)) > 0,
        "has_validation_failures": any(
            v.status == "FAIL" for v in application.validation_results
        ),
        "ai_recommendation": latest_score.ai_recommendation if latest_score else None,
        "risk_level": latest_score.risk_level if latest_score else None,
        "total_score": latest_score.total_score if latest_score else None,
    }
