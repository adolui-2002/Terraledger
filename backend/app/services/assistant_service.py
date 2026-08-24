"""
Reviewer assistant ("conversational AI" capability).

This is intentionally retrieval-first: we build a small, structured
context block from the application's own scoring, validation and audit
records (a lightweight RAG pattern) and only then hand it to the AI
provider. The system prompt / mock-provider logic never allows the
assistant to state a final approve/reject determination — see
GUARDRAIL_PREFIX and MockAIProvider.answer_question.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import Application
from app.services.ai_provider import get_ai_provider

GUARDRAIL_PREFIX = (
    "You may explain scores, summarize documents, and recommend next steps. "
    "You must never declare a final approval or rejection — only a human "
    "reviewer can do that."
)


def build_context(application: Application) -> tuple[str, list[str]]:
    lines: list[str] = []
    sources: list[str] = []

    lines.append(f"Application {application.reference_code} — status: {application.status}")
    lines.append(f"Applicant: {application.applicant_name}, Scheme: {application.scheme_name}")
    if application.requested_amount:
        lines.append(f"Requested amount: {application.requested_amount:,.0f}")

    if application.scores:
        latest = sorted(application.scores, key=lambda s: s.created_at)[-1]
        lines.append(f"Latest AI score: {latest.total_score}/100 (confidence {latest.confidence})")
        lines.append(f"Risk level: {latest.risk_level}, AI recommendation: {latest.ai_recommendation}")
        for cat, pts in latest.breakdown.items():
            lines.append(f"  score - {cat}: {pts}/{latest.max_breakdown.get(cat)}")
        for p in latest.reasons_positive:
            lines.append(f"  positive: {p}")
        for c in latest.reasons_concern:
            lines.append(f"  concern: {c}")
        if latest.ml_approval_probability is not None:
            lines.append(
                f"ML model ({latest.ml_model_version}) predicted approval likelihood: "
                f"{latest.ml_approval_probability * 100:.0f}% (agreement with rule engine: "
                f"{latest.model_agreement})"
            )
            for feat in latest.shap_explanation:
                lines.append(
                    f"  SHAP factor: {feat['feature']} {feat['direction']} the likelihood "
                    f"(contribution {feat['contribution']}, value {feat['value']})"
                )
        sources.append(f"score:{latest.id}")

    for v in application.validation_results:
        lines.append(f"validation [{v.category}] {v.check_name}: {v.status} - {v.message}")
        sources.append(f"validation:{v.id}")

    for f in application.fraud_signals:
        lines.append(f"fraud flag [{f.severity}] {f.signal_type}: {f.description}")
        sources.append(f"fraud:{f.id}")

    for a in sorted(application.audit_logs, key=lambda a: a.timestamp)[-10:]:
        lines.append(f"audit: {a.timestamp.isoformat()} {a.actor} -> {a.action} {a.details}")
        sources.append(f"audit:{a.id}")

    return "\n".join(lines), sources


def answer(db: Session, application: Application | None, question: str) -> tuple[str, list[str]]:
    ai = get_ai_provider()
    if application is None:
        return (
            "Select an application to ask about specific scores, validation results, "
            "or audit history. I can also answer general questions about how scoring "
            "and review works.",
            [],
        )
    context, sources = build_context(application)
    raw_answer = ai.answer_question(question, context)
    return raw_answer, sources
