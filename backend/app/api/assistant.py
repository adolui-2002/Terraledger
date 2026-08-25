from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import schemas
from app.database import get_db
from app.models import Application
from app.services import assistant_service, summarization_service

router = APIRouter(prefix="/api/v1/assistant", tags=["assistant"])


@router.post("/ask", response_model=schemas.AssistantAnswer)
def ask(payload: schemas.AssistantQuery, db: Session = Depends(get_db)):
    application = db.get(Application, payload.application_id) if payload.application_id else None
    text, sources = assistant_service.answer(db, application, payload.question)
    return schemas.AssistantAnswer(answer=text, sources=sources)


@router.get("/applications/{application_id}/summary", response_model=schemas.ApplicationSummaryOut)
def get_summary(application_id: str, db: Session = Depends(get_db)):
    """Generate an AI-assisted structured summary of the application.

    Uses only structured fields (no raw document text) so it is safe for
    both RESTRICTED and SYNTHETIC applications regardless of AI_PROVIDER.
    """
    application = db.get(Application, application_id)
    if not application:
        raise HTTPException(404, "Application not found")
    if not application.documents:
        raise HTTPException(400, "No documents have been uploaded yet.")
    result = summarization_service.summarize_application(application)
    return schemas.ApplicationSummaryOut(**result)
