"""
Trains the ML scoring model on labeled synthetic applications currently in
the database, and saves it as the active model artifact.

Run inside the backend container:
    docker compose exec backend python -m app.ml.train

Or trigger it via the API once synthetic data is seeded:
    POST /api/v1/ml/train

A Gradient Boosted Tree is used deliberately over a black-box model: it is
exactly explainable by SHAP's TreeExplainer (fast, exact, no sampling),
which matters for a government reviewer-facing explanation, not just an
internal metric.
"""
from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.metrics import accuracy_score
from sklearn.model_selection import train_test_split

from app.database import SessionLocal, init_db
from app.ml.feature_engineering import FEATURE_NAMES, extract_features, training_label
from app.ml.model_store import ModelMetadata, save
from app.models import Application

MIN_TRAINING_SAMPLES = 10
MODEL_VERSION_PREFIX = "gbm-shap-v"


def build_training_set(db) -> tuple[np.ndarray, np.ndarray]:
    applications = db.query(Application).all()
    X, y = [], []
    for app in applications:
        label = training_label(app)
        if label is None:
            continue
        if not app.validation_results and not app.fraud_signals:
            continue  # hasn't been through the processing pipeline yet
        X.append(extract_features(app))
        y.append(label)
    return (np.array(X), np.array(y)) if X else (np.empty((0, len(FEATURE_NAMES))), np.empty((0,)))


def train_model(db) -> tuple[object | None, ModelMetadata | None, str | None]:
    """Returns (model, metadata, error_message). Exactly one of
    (model, metadata) or error_message is populated."""
    X, y = build_training_set(db)

    if len(X) < MIN_TRAINING_SAMPLES:
        return None, None, (
            f"Only {len(X)} labeled synthetic applications available "
            f"(minimum {MIN_TRAINING_SAMPLES} required). Seed synthetic data first: "
            f"docker compose exec backend python -m app.data.synthetic_generator"
        )
    if len(set(y.tolist())) < 2:
        return None, None, "Training data contains only one class -- cannot train a classifier."

    stratify = y if min(np.bincount(y.astype(int))) >= 2 else None
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.25, random_state=42, stratify=stratify,
    )

    model = GradientBoostingClassifier(
        n_estimators=80, max_depth=2, learning_rate=0.1, random_state=42,
    )
    model.fit(X_train, y_train)

    if len(X_test):
        accuracy = float(accuracy_score(y_test, model.predict(X_test)))
    else:
        accuracy = -1.0  # not enough data for a held-out split

    metadata = ModelMetadata(
        version=MODEL_VERSION_PREFIX + datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S"),
        trained_at=datetime.now(timezone.utc).isoformat(),
        n_samples=len(X),
        n_positive=int(y.sum()),
        n_negative=int(len(y) - y.sum()),
        train_accuracy=accuracy,
        feature_names=FEATURE_NAMES,
    )
    save(model, metadata)
    return model, metadata, None


if __name__ == "__main__":
    init_db()
    session = SessionLocal()
    try:
        model, metadata, error = train_model(session)
        if error:
            print(f"Training skipped: {error}")
        else:
            acc_txt = f"{metadata.train_accuracy:.2f}" if metadata.train_accuracy >= 0 else "n/a (too few samples to hold out)"
            print(
                f"Trained model {metadata.version} on {metadata.n_samples} samples "
                f"({metadata.n_positive} positive / {metadata.n_negative} negative). "
                f"Held-out accuracy: {acc_txt}"
            )
    finally:
        session.close()
