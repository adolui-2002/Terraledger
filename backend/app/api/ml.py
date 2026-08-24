from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import schemas
from app.database import get_db
from app.ml import ml_scoring_service
from app.ml.train import train_model

router = APIRouter(prefix="/api/v1/ml", tags=["ml"])


@router.get("/status", response_model=schemas.MLModelStatus)
def status():
    return ml_scoring_service.model_status()


@router.post("/train", response_model=schemas.MLTrainResponse)
def train(db: Session = Depends(get_db)):
    model, metadata, error = train_model(db)
    if error:
        return schemas.MLTrainResponse(success=False, message=error, status=ml_scoring_service.model_status())

    ml_scoring_service.invalidate_cache()
    return schemas.MLTrainResponse(
        success=True,
        message=f"Trained {metadata.version} on {metadata.n_samples} labeled samples.",
        status=ml_scoring_service.model_status(),
    )
