"""
These tests exercise the real scikit-learn / SHAP path, so they need
those packages installed (they're in requirements.txt but not available
in every dev shell) -- run them inside the backend container:

    docker compose exec backend pytest app/tests/test_ml_scoring.py -v
"""
import pytest

from app.ml import model_store
from app.ml.feature_engineering import extract_features, training_label
from app.ml.train import MIN_TRAINING_SAMPLES, train_model
from app.models import Application, Document
from app.services import fraud_service, validation_service

pytest.importorskip("sklearn")
pytest.importorskip("shap")


def _seed_labeled_applications(db):
    """Creates enough labeled synthetic applications to clear
    MIN_TRAINING_SAMPLES, split roughly evenly between approve-worthy and
    reject-worthy categories."""
    specs = [
        ("complete", True), ("complete", True), ("normal", True), ("normal", True),
        ("normal", True), ("normal", True),
        ("incomplete", False), ("incomplete", False), ("contradictory", False),
        ("contradictory", False), ("duplicate", False), ("suspicious", False),
    ]
    assert len(specs) >= MIN_TRAINING_SAMPLES

    apps = []
    for i, (category, complete) in enumerate(specs):
        app = Application(
            reference_code=f"APP-ML{i}",
            applicant_name=f"Applicant {i}",
            applicant_bank_ref=f"BANK{i}",
            scheme_name="Environmental Scheme",
            requested_amount=400000,
            synthetic_category=category,
        )
        db.add(app)
        db.flush()
        doc_types = ["APPLICATION_FORM", "PROPOSAL", "BUDGET", "CERTIFICATE"] if complete else ["APPLICATION_FORM"]
        for doc_type in doc_types:
            db.add(Document(application_id=app.id, filename=f"{doc_type}.pdf", doc_type=doc_type,
                             raw_text=f"Total ₹400,000 {doc_type}"))
        db.flush()
        validation_service.run_validation(db, app)
        fraud_service.run_fraud_checks(db, app)
        db.flush()
        apps.append(app)
    db.commit()
    return apps


def test_training_label_maps_categories_correctly(db_session):
    approve = Application(reference_code="A1", applicant_name="x", scheme_name="Environmental Scheme",
                           synthetic_category="complete")
    reject = Application(reference_code="A2", applicant_name="y", scheme_name="Environmental Scheme",
                          synthetic_category="suspicious")
    borderline = Application(reference_code="A3", applicant_name="z", scheme_name="Environmental Scheme",
                              synthetic_category="borderline")
    assert training_label(approve) == 1
    assert training_label(reject) == 0
    assert training_label(borderline) is None


def test_feature_extraction_returns_expected_shape(db_session):
    app = Application(reference_code="A4", applicant_name="x", scheme_name="Environmental Scheme",
                       requested_amount=400000)
    db_session.add(app)
    db_session.flush()
    features = extract_features(app)
    assert features.shape == (10,)


def test_train_model_below_minimum_samples_returns_error(db_session):
    model, metadata, error = train_model(db_session)
    assert model is None
    assert error is not None
    assert "labeled synthetic applications" in error


def test_train_model_succeeds_and_saves_artifact(db_session, tmp_path, monkeypatch):
    monkeypatch.setattr(model_store, "ARTIFACT_DIR", tmp_path)
    monkeypatch.setattr(model_store, "MODEL_FILE", tmp_path / "scoring_model.joblib")
    monkeypatch.setattr(model_store, "METADATA_FILE", tmp_path / "scoring_model_metadata.json")

    _seed_labeled_applications(db_session)
    model, metadata, error = train_model(db_session)

    assert error is None
    assert model is not None
    assert metadata.n_samples >= MIN_TRAINING_SAMPLES
    assert model_store.MODEL_FILE.exists()
    assert model_store.METADATA_FILE.exists()


def test_ml_scoring_service_returns_shap_explanation(db_session, tmp_path, monkeypatch):
    monkeypatch.setattr(model_store, "ARTIFACT_DIR", tmp_path)
    monkeypatch.setattr(model_store, "MODEL_FILE", tmp_path / "scoring_model.joblib")
    monkeypatch.setattr(model_store, "METADATA_FILE", tmp_path / "scoring_model_metadata.json")

    apps = _seed_labeled_applications(db_session)
    train_model(db_session)

    from app.ml import ml_scoring_service
    ml_scoring_service.invalidate_cache()

    result = ml_scoring_service.score_application(apps[0])
    assert result.available
    assert 0.0 <= result.probability <= 1.0
    assert len(result.shap_features) > 0
    for feat in result.shap_features:
        assert set(feat.keys()) == {"feature", "value", "contribution", "direction"}
        assert feat["direction"] in ("increases", "decreases")
