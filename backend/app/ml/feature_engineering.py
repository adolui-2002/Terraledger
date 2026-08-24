"""
Feature engineering for the ML scoring model.

Every feature is derived from records that already exist by the time
scoring runs (documents, validation results, fraud signals, extracted
fields) -- no feature requires a network call or external data source,
so both training and inference run entirely on-prem, same as the rest
of the pipeline.
"""
from __future__ import annotations

import numpy as np

from app.models import Application
from app.models.enums import ValidationStatus
from app.services.validation_service import rules_for_scheme

FEATURE_NAMES = [
    "completeness_ratio",
    "num_validation_fail",
    "num_validation_warning",
    "num_fraud_high",
    "num_fraud_medium",
    "has_contradiction",
    "extracted_field_count",
    "low_ocr_confidence_count",
    "amount_ratio_of_max",
    "document_count",
]

# Applications tagged with these synthetic categories are used as labeled
# training examples. "borderline" is intentionally excluded -- it exists to
# stress-test the deterministic engine's threshold, not to teach the model
# a clean decision boundary.
APPROVE_WORTHY_CATEGORIES = {"complete", "normal"}
REJECT_WORTHY_CATEGORIES = {"incomplete", "contradictory", "duplicate", "suspicious", "low_quality"}


def extract_features(application: Application) -> np.ndarray:
    validations = list(application.validation_results)
    fraud_signals = list(application.fraud_signals)
    documents = list(application.documents)
    fields = list(application.extracted_fields)

    rules = rules_for_scheme(application.scheme_name)
    required = set(rules.get("required_documents", []))
    present = {d.doc_type for d in documents}
    completeness_ratio = len(present & required) / len(required) if required else 1.0

    num_fail = sum(1 for v in validations if v.status == ValidationStatus.FAIL)
    num_warn = sum(1 for v in validations if v.status == ValidationStatus.WARNING)
    has_contradiction = 1.0 if any(
        v.category == "contradiction" and v.status == ValidationStatus.FAIL for v in validations
    ) else 0.0

    num_fraud_high = sum(1 for s in fraud_signals if s.severity == "HIGH")
    num_fraud_medium = sum(1 for s in fraud_signals if s.severity == "MEDIUM")

    low_ocr = sum(1 for d in documents if d.ocr_confidence is not None and d.ocr_confidence < 0.5)

    max_budget = rules.get("maximum_project_budget", 1) or 1
    amount_ratio = (application.requested_amount or 0) / max_budget

    return np.array([
        completeness_ratio,
        float(num_fail),
        float(num_warn),
        float(num_fraud_high),
        float(num_fraud_medium),
        has_contradiction,
        float(len(fields)),
        float(low_ocr),
        float(amount_ratio),
        float(len(documents)),
    ], dtype=float)


def training_label(application: Application) -> int | None:
    """Ground-truth label derived from the synthetic dataset's category tag.

    Only synthetic, labeled applications are ever used for training. Real
    RESTRICTED applications are scored by the trained model but are never
    fed back into training automatically -- that would let an unreviewed
    AI recommendation silently become tomorrow's training signal.
    """
    category = application.synthetic_category
    if category in APPROVE_WORTHY_CATEGORIES:
        return 1
    if category in REJECT_WORTHY_CATEGORIES:
        return 0
    return None
