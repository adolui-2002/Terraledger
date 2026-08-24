"""
High-level entry point scoring_service uses to get an ML-based second
opinion alongside the deterministic rule engine, with a SHAP explanation
attached to every prediction.

Fails safe by design: if no model has been trained yet, or shap/sklearn
are unavailable for any reason, this returns an "unavailable" result
rather than raising -- the deterministic rule engine is always sufficient
on its own, the ML model only ever adds a second signal on top of it.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.ml import model_store
from app.ml.feature_engineering import extract_features
from app.models import Application


@dataclass
class MLScoringResult:
    probability: float | None = None
    model_version: str | None = None
    shap_features: list[dict] = field(default_factory=list)

    @property
    def available(self) -> bool:
        return self.probability is not None


_model_cache: dict = {"model": None, "metadata": None, "loaded": False}


def _get_model():
    if not _model_cache["loaded"]:
        model, metadata = model_store.load()
        _model_cache.update(model=model, metadata=metadata, loaded=True)
    return _model_cache["model"], _model_cache["metadata"]


def invalidate_cache() -> None:
    """Called after (re)training so the next scoring call picks up the
    new model instead of a stale in-memory one."""
    _model_cache.update(model=None, metadata=None, loaded=False)


def model_status() -> dict:
    model, metadata = _get_model()
    if model is None:
        return {"trained": False}
    return {
        "trained": True,
        "version": metadata.version,
        "trained_at": metadata.trained_at,
        "n_samples": metadata.n_samples,
        "n_positive": metadata.n_positive,
        "n_negative": metadata.n_negative,
        "train_accuracy": metadata.train_accuracy,
    }


def score_application(application: Application) -> MLScoringResult:
    model, metadata = _get_model()
    if model is None:
        return MLScoringResult()

    features = extract_features(application)
    try:
        probability = float(model.predict_proba(features.reshape(1, -1))[0][1])
    except Exception:
        return MLScoringResult()

    try:
        from app.ml.explain import explain
        shap_features = explain(model, metadata.version, features)
    except Exception:
        shap_features = []

    return MLScoringResult(probability=probability, model_version=metadata.version, shap_features=shap_features)
