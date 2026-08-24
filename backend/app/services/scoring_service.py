"""
Scoring engine. The score itself is fully deterministic and rule-based
(never an opaque LLM opinion) — the AI provider is only used afterwards to
turn the breakdown into a readable explanation. This split is deliberate:
it keeps the number reproducible and auditable while still giving
reviewers a plain-English narrative.
"""
from __future__ import annotations

from pathlib import Path

import yaml
from sqlalchemy.orm import Session

from app.config import get_settings
from app.ml import ml_scoring_service
from app.models import Application, FraudSignal, Score, ValidationResult
from app.models.enums import RiskLevel, ValidationStatus
from app.services.ai_provider import get_ai_provider

settings = get_settings()

_WEIGHTS_CACHE: dict | None = None


def load_weights() -> dict:
    global _WEIGHTS_CACHE
    if _WEIGHTS_CACHE is None:
        path = Path(settings.rules_dir) / "scoring_weights.yaml"
        with open(path) as f:
            _WEIGHTS_CACHE = yaml.safe_load(f)
    return _WEIGHTS_CACHE


CATEGORY_KEYS = [
    "eligibility",
    "completeness",
    "technical_feasibility",
    "environmental_impact",
    "budget_quality",
    "implementation_plan",
]


def _score_eligibility(validations: list[ValidationResult], max_points: float) -> tuple[float, str | None]:
    elig = [v for v in validations if v.category == "eligibility"]
    if any(v.status == ValidationStatus.FAIL for v in elig):
        return 0.0, "Eligibility criteria not met (budget out of permitted range)."
    if any(v.status == ValidationStatus.WARNING for v in elig):
        return max_points * 0.6, "Eligibility could not be fully confirmed (missing requested amount)."
    return max_points, None


def _score_completeness(validations: list[ValidationResult], max_points: float) -> tuple[float, str | None]:
    comp = [v for v in validations if v.category == "completeness"]
    if not comp:
        return max_points, None
    fails = sum(1 for v in comp if v.status == ValidationStatus.FAIL)
    warns = sum(1 for v in comp if v.status == ValidationStatus.WARNING)
    penalty = fails * 0.6 + warns * 0.2
    points = max(0.0, max_points * (1 - min(penalty, 1.0)))
    concern = None
    if fails:
        concern = next((v.message for v in comp if v.status == ValidationStatus.FAIL), None)
    return points, concern


def _score_contradiction_adjusted(base_points: float, validations: list[ValidationResult]) -> tuple[float, str | None]:
    contradictions = [v for v in validations if v.category == "contradiction" and v.status == ValidationStatus.FAIL]
    if contradictions:
        return base_points * 0.5, contradictions[0].message
    return base_points, None


def compute_score(db: Session, application: Application) -> Score:
    weights = load_weights()
    validations = list(application.validation_results)
    fraud_signals = list(application.fraud_signals)

    breakdown: dict[str, float] = {}
    max_breakdown: dict[str, float] = {k: weights[k] for k in CATEGORY_KEYS}
    positives: list[str] = []
    concerns: list[str] = []

    elig_points, elig_concern = _score_eligibility(validations, weights["eligibility"])
    breakdown["eligibility"] = round(elig_points, 1)
    (concerns if elig_concern else positives).append(
        elig_concern or "Eligibility requirements are met."
    )

    comp_points, comp_concern = _score_completeness(validations, weights["completeness"])
    breakdown["completeness"] = round(comp_points, 1)
    (concerns if comp_concern else positives).append(
        comp_concern or "All required documents were submitted."
    )

    # Budget quality: penalized directly by contradiction checks
    budget_points, budget_concern = _score_contradiction_adjusted(weights["budget_quality"], validations)
    breakdown["budget_quality"] = round(budget_points, 1)
    (concerns if budget_concern else positives).append(
        budget_concern or "Budget figures are consistent across documents."
    )

    # Technical feasibility / environmental impact / implementation plan:
    # for the POC these use a content-richness heuristic (extracted-field
    # coverage) as a stand-in for a full NLP quality model — a clearly
    # labelled extension point for a real scoring model.
    field_count = len(application.extracted_fields)
    richness = min(1.0, field_count / 4.0) if field_count else 0.4
    for cat, label in [
        ("technical_feasibility", "technical feasibility"),
        ("environmental_impact", "environmental impact"),
        ("implementation_plan", "implementation plan"),
    ]:
        pts = weights[cat] * (0.5 + 0.5 * richness)
        breakdown[cat] = round(pts, 1)
        if richness >= 0.75:
            positives.append(f"Proposal documentation supports strong {label}.")
        elif richness < 0.4:
            concerns.append(f"Limited documentation to assess {label}.")

    # Fraud signal penalty on top of category scores
    high_signals = [s for s in fraud_signals if s.severity == "HIGH"]
    med_signals = [s for s in fraud_signals if s.severity == "MEDIUM"]
    fraud_penalty = len(high_signals) * 15 + len(med_signals) * 7

    raw_total = sum(breakdown.values())
    total = max(0.0, min(100.0, raw_total - fraud_penalty))

    for s in high_signals:
        concerns.append(s.description)
    for s in med_signals:
        concerns.append(s.description)

    thresholds = weights["risk_thresholds"]
    if len(high_signals) >= thresholds.get("fraud_high_signal_escalation", 2):
        risk = RiskLevel.HIGH
    elif total <= thresholds["high_risk_max_score"]:
        risk = RiskLevel.HIGH
    elif total <= thresholds["medium_risk_max_score"]:
        risk = RiskLevel.MEDIUM
    else:
        risk = RiskLevel.LOW

    rec_thresholds = weights["recommendation_thresholds"]
    if high_signals or risk == RiskLevel.HIGH:
        recommendation = "ESCALATE"
    elif total >= rec_thresholds["approve_min_score"]:
        recommendation = "APPROVE"
    elif total <= rec_thresholds["reject_max_score"]:
        recommendation = "REJECT_RECOMMENDATION"
    else:
        recommendation = "REQUEST_INFO"

    confidence = round(max(0.3, 1.0 - (0.1 * len(fraud_signals)) - (0.05 * sum(
        1 for v in validations if v.status == ValidationStatus.WARNING
    ))), 2)

    # --- Explainable ML second opinion ---
    # Deliberately computed AFTER the deterministic recommendation above,
    # and never allowed to silently change it -- disagreement is surfaced
    # to the reviewer as an extra concern instead, per the brief's
    # "deterministic rules + ML side by side" scoring design.
    ml_result = ml_scoring_service.score_application(application)
    model_agreement = None
    if ml_result.available:
        rule_leans_approve = recommendation == "APPROVE"
        ml_leans_approve = ml_result.probability >= 0.5
        model_agreement = "AGREE" if rule_leans_approve == ml_leans_approve else "DISAGREE"
        if model_agreement == "DISAGREE":
            concerns.append(
                f"ML model disagrees with the rule-based recommendation (predicted approval "
                f"likelihood: {ml_result.probability * 100:.0f}%) — recommend manual review."
            )
            if risk == RiskLevel.LOW:
                risk = RiskLevel.MEDIUM

    ai = get_ai_provider()
    explanation = ai.explain_score(breakdown, positives, concerns)
    if ml_result.available:
        top_factor = ml_result.shap_features[0] if ml_result.shap_features else None
        explanation += (
            f"\n\nML model second opinion ({ml_result.model_version}): "
            f"{ml_result.probability * 100:.0f}% predicted approval likelihood."
        )
        if top_factor:
            explanation += (
                f" Largest driver: {top_factor['feature']} "
                f"({top_factor['direction']} the likelihood, value={top_factor['value']})."
            )

    score = Score(
        application_id=application.id,
        total_score=round(total, 1),
        breakdown=breakdown,
        max_breakdown=max_breakdown,
        confidence=confidence,
        risk_level=risk.value if hasattr(risk, "value") else risk,
        ai_recommendation=recommendation,
        explanation=explanation,
        reasons_positive=positives,
        reasons_concern=concerns,
        ml_approval_probability=ml_result.probability,
        ml_model_version=ml_result.model_version,
        shap_explanation=ml_result.shap_features,
        model_agreement=model_agreement,
    )
    return score
