import random
import string

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import schemas
from app.database import get_db
from app.models import Application
from app.models.enums import DataSensitivity
from app.services import audit_service, pipeline_service
from app.services.pipeline_service import PipelineNotReprocessableError

router = APIRouter(prefix="/api/v1/applications", tags=["applications"])


def _generate_reference_code() -> str:
    suffix = "".join(random.choices(string.digits, k=5))
    return f"APP-{suffix}"


@router.post("", response_model=schemas.ApplicationOut, status_code=201)
def create_application(payload: schemas.ApplicationCreate, db: Session = Depends(get_db)):
    application = Application(
        reference_code=_generate_reference_code(),
        applicant_name=payload.applicant_name,
        scheme_name=payload.scheme_name,
        applicant_bank_ref=payload.applicant_bank_ref,
        requested_amount=payload.requested_amount,
        language=payload.language,
        sensitivity=DataSensitivity.RESTRICTED.value,
    )
    db.add(application)
    db.flush()
    audit_service.log(db, application.id, "system", "APPLICATION_SUBMITTED",
                       {"reference_code": application.reference_code})
    db.commit()
    db.refresh(application)
    return application


@router.get("", response_model=list[schemas.ApplicationDetailOut])
def list_applications(
    status: str | None = None,
    risk: str | None = None,
    reviewer: str | None = None,
    q: str | None = None,
    db: Session = Depends(get_db),
):
    query = db.query(Application)
    if status:
        query = query.filter(Application.status == status)
    if reviewer:
        query = query.filter(Application.assigned_reviewer == reviewer)
    if q:
        like = f"%{q}%"
        query = query.filter(
            (Application.applicant_name.ilike(like)) | (Application.reference_code.ilike(like))
        )
    applications = query.order_by(Application.submitted_at.desc()).all()

    if risk:
        applications = [
            a for a in applications
            if a.scores and sorted(a.scores, key=lambda s: s.created_at)[-1].risk_level == risk
        ]
    return applications


@router.get("/{application_id}", response_model=schemas.ApplicationDetailOut)
def get_application(application_id: str, db: Session = Depends(get_db)):
    application = db.get(Application, application_id)
    if not application:
        raise HTTPException(404, "Application not found")
    return application


@router.post("/{application_id}/process", response_model=schemas.ApplicationDetailOut)
def process_application(application_id: str, db: Session = Depends(get_db)):
    """Runs the extraction -> validation -> fraud -> scoring -> routing
    pipeline. Safe to call multiple times (idempotent per stage)."""
    application = db.get(Application, application_id)
    if not application:
        raise HTTPException(404, "Application not found")
    if not application.documents:
        raise HTTPException(400, "Cannot process an application with no uploaded documents.")
    try:
        pipeline_service.run_pipeline(db, application)
    except PipelineNotReprocessableError as exc:
        db.rollback()
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:
        db.rollback()
        raise HTTPException(500, f"Pipeline failed: {exc}") from exc
    return application


@router.delete("/{application_id}", status_code=204)
def delete_application(application_id: str, db: Session = Depends(get_db)):
    application = db.get(Application, application_id)
    if not application:
        raise HTTPException(404, "Application not found")
    db.delete(application)
    db.commit()
