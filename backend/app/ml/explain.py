"""
SHAP-based explanation for the ML scoring model.

Kept in its own module (rather than inline in ml_scoring_service) because
the `shap` import is comparatively heavy -- it's only paid for on the code
path that actually needs an explanation.
"""
from __future__ import annotations

import numpy as np

from app.ml.feature_engineering import FEATURE_NAMES

FEATURE_LABELS = {
    "completeness_ratio": "Required-document completeness",
    "num_validation_fail": "Validation failures",
    "num_validation_warning": "Validation warnings",
    "num_fraud_high": "High-severity fraud signals",
    "num_fraud_medium": "Medium-severity fraud signals",
    "has_contradiction": "Budget/proposal contradiction",
    "extracted_field_count": "Extracted field coverage",
    "low_ocr_confidence_count": "Low-confidence OCR documents",
    "amount_ratio_of_max": "Requested amount vs. scheme ceiling",
    "document_count": "Documents submitted",
}

_explainer_cache: dict[str, object] = {}


def _get_explainer(model, cache_key: str):
    import shap  # imported lazily -- see module docstring

    if cache_key not in _explainer_cache:
        _explainer_cache[cache_key] = shap.TreeExplainer(model)
    return _explainer_cache[cache_key]


def explain(model, model_version: str, features: np.ndarray, top_n: int = 5) -> list[dict]:
    """Returns the top_n features driving this single prediction, ranked
    by |SHAP value|, each with its direction (increases/decreases the
    predicted approval probability) and raw contribution."""
    explainer = _get_explainer(model, model_version)
    shap_values = explainer.shap_values(features.reshape(1, -1))

    # GradientBoostingClassifier -> a single (1, n_features) array from
    # TreeExplainer. Some sklearn/shap version pairings wrap it in a list
    # (one entry per class) -- handle both defensively.
    raw = shap_values[-1] if isinstance(shap_values, list) else shap_values
    values = np.array(raw).reshape(-1)

    contributions = sorted(
        zip(FEATURE_NAMES, values, features.tolist()),
        key=lambda item: abs(item[1]),
        reverse=True,
    )[:top_n]

    return [
        {
            "feature": FEATURE_LABELS.get(name, name),
            "value": round(float(val), 3),
            "contribution": round(float(contrib), 4),
            "direction": "increases" if contrib > 0 else "decreases",
        }
        for name, contrib, val in contributions
    ]
