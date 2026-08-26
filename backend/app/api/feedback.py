"""
Reviewer feedback on AI scoring quality.

  POST /api/v1/applications/{id}/feedback
       Submit feedback on the AI score for this application.

  GET  /api/v1/applications/{id}/feedback
       List all feedback submitted for this application.

  GET  /api/v1/feedback/summary
       Aggregate feedback statistics across all applications.
       Useful for tracking whether AI quality is improving over time.
"""
from __future__ import annotations

import logging
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import schemas
from app.database import get_db
from app.models import AIFeedback, Application
from app.services import audit_service

router = APIRouter(prefix="/api/v1", tags=["feedback"])
logger = logging.getLogger(__name__)

VALID_RATINGS = {"HELPFUL", "PARTIALLY_HELPFUL", "NOT_HELPFUL"}
VALID_ACCURACIES = {"ACCURATE", "PARTIALLY_ACCURATE", "INACCURATE"}


@router.post(
    "/applications/{application_id}/feedback",
    response_model=schemas.AIFeedbackOut,
    status_code=201,
)
def submit_feedback(
    application_id: str,
    payload: schemas.AIFeedbackIn,
    db: Session = Depends(get_db),
):
    """Submit feedback on the AI scoring recommendation for an application.
    Feedback is stored durably and surfaced in the analytics dashboard.
    It is NOT automatically fed back into model training — a human must
    review aggregate feedback and trigger retraining explicitly.
    """
    application = db.get(Application, application_id)
    if not application:
        raise HTTPException(404, "Application not found")

    if payload.rating not in VALID_RATINGS:
        raise HTTPException(400, f"rating must be one of {sorted(VALID_RATINGS)}")
    if payload.score_accuracy not in VALID_ACCURACIES:
        raise HTTPException(400, f"score_accuracy must be one of {sorted(VALID_ACCURACIES)}")
    if not payload.reviewer_name or not payload.reviewer_name.strip():
        raise HTTPException(400, "reviewer_name is required")

    feedback = AIFeedback(
        application_id=application_id,
        score_id=payload.score_id,
        reviewer_name=payload.reviewer_name,
        rating=payload.rating,
        score_accuracy=payload.score_accuracy,
        comment=payload.comment,
    )
    db.add(feedback)
    audit_service.log(
        db, application_id, payload.reviewer_name, "AI_FEEDBACK_SUBMITTED",
        {
            "rating": payload.rating,
            "score_accuracy": payload.score_accuracy,
            "has_comment": bool(payload.comment),
        },
    )
    db.commit()
    db.refresh(feedback)

    logger.info(
        "AI feedback submitted",
        extra={
            "application_id": application_id,
            "reviewer": payload.reviewer_name,
            "rating": payload.rating,
            "score_accuracy": payload.score_accuracy,
        },
    )
    return feedback


@router.get(
    "/applications/{application_id}/feedback",
    response_model=list[schemas.AIFeedbackOut],
)
def list_feedback(application_id: str, db: Session = Depends(get_db)):
    """Return all feedback submitted for a specific application."""
    application = db.get(Application, application_id)
    if not application:
        raise HTTPException(404, "Application not found")
    return (
        db.query(AIFeedback)
        .filter(AIFeedback.application_id == application_id)
        .order_by(AIFeedback.submitted_at.desc())
        .all()
    )


@router.get("/feedback/summary", response_model=schemas.FeedbackSummary)
def feedback_summary(db: Session = Depends(get_db)):
    """Aggregate feedback statistics across all applications.
    Used to track whether AI scoring quality is improving over time.
    """
    all_feedback = db.query(AIFeedback).all()
    total = len(all_feedback)

    rating_dist: dict[str, int] = defaultdict(int)
    accuracy_dist: dict[str, int] = defaultdict(int)

    for f in all_feedback:
        rating_dist[f.rating] += 1
        accuracy_dist[f.score_accuracy] += 1

    helpful_count = rating_dist.get("HELPFUL", 0)
    accurate_count = accuracy_dist.get("ACCURATE", 0)

    return schemas.FeedbackSummary(
        total_feedback=total,
        rating_distribution=dict(rating_dist),
        accuracy_distribution=dict(accuracy_dist),
        helpful_rate=round(helpful_count / total, 3) if total else 0.0,
        accurate_rate=round(accurate_count / total, 3) if total else 0.0,
    )
