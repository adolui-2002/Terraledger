"""
Persistence for the trained ML scoring model. Stored as a single joblib
artifact under app/ml/artifacts/ -- gitignored by default so a real
trained model (fit on an on-prem deployment's own data) is never
accidentally committed to source control.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

import joblib

from app.config import get_settings

settings = get_settings()

ARTIFACT_DIR = Path(settings.ml_model_path)
MODEL_FILE = ARTIFACT_DIR / "scoring_model.joblib"
METADATA_FILE = ARTIFACT_DIR / "scoring_model_metadata.json"


@dataclass
class ModelMetadata:
    version: str
    trained_at: str
    n_samples: int
    n_positive: int
    n_negative: int
    train_accuracy: float
    feature_names: list[str] = field(default_factory=list)


def save(model, metadata: ModelMetadata) -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, MODEL_FILE)
    METADATA_FILE.write_text(json.dumps(asdict(metadata), indent=2))


def load() -> tuple[object | None, ModelMetadata | None]:
    if not MODEL_FILE.exists() or not METADATA_FILE.exists():
        return None, None
    model = joblib.load(MODEL_FILE)
    metadata = ModelMetadata(**json.loads(METADATA_FILE.read_text()))
    return model, metadata


def exists() -> bool:
    return MODEL_FILE.exists() and METADATA_FILE.exists()
