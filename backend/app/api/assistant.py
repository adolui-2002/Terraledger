from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import schemas
from app.database import get_db
from app.models import Application
from app.services import assistant_service

router = APIRouter(prefix="/api/v1/assistant", tags=["assistant"])


@router.post("/ask", response_model=schemas.AssistantAnswer)
def ask(payload: schemas.AssistantQuery, db: Session = Depends(get_db)):
    application = db.get(Application, payload.application_id) if payload.application_id else None
    text, sources = assistant_service.answer(db, application, payload.question)
    return schemas.AssistantAnswer(answer=text, sources=sources)
