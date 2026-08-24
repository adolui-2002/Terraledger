from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app import schemas
from app.database import get_db
from app.models import Application, ReviewDecision, Reviewer
from app.models.enums import ApplicationStatus
from app.services import audit_service, workflow_service

router = APIRouter(prefix="/api/v1", tags=["review"])

DECISION_TO_STATUS = {
    "APPROVED": ApplicationStatus.APPROVED,
    "REJECTED": ApplicationStatus.REJECTED,
    "NEEDS_INFO": ApplicationStatus.NEEDS_INFO,
}


class ReviewerCreate(BaseModel):
    name: str
    role: str = "Reviewer"


@router.get("/reviewers")
def list_reviewers(db: Session = Depends(get_db)):
    reviewers = db.query(Reviewer).all()
    return [{"name": r.name, "role": r.role, "active_caseload": r.active_caseload} for r in reviewers]


@router.post("/reviewers", status_code=201)
def create_reviewer(payload: ReviewerCreate, db: Session = Depends(get_db)):
    if db.query(Reviewer).filter(Reviewer.name == payload.name).first():
        raise HTTPException(409, "Reviewer already exists.")
    reviewer = Reviewer(name=payload.name, role=payload.role)
    db.add(reviewer)
    db.commit()
    return {"name": reviewer.name, "role": reviewer.role}


@router.post("/applications/{application_id}/assign")
def assign_application(application_id: str, reviewer_name: str, db: Session = Depends(get_db)):
    application = db.get(Application, application_id)
    if not application:
        raise HTTPException(404, "Application not found")
    try:
        workflow_service.assign_reviewer(db, application, reviewer_name, actor="system")
        if application.status == ApplicationStatus.REVIEW_PENDING.value:
            workflow_service.transition(db, application, ApplicationStatus.UNDER_REVIEW, actor=reviewer_name,
                                         force=True)
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(500, f"Could not assign reviewer: {exc}") from exc
    return {"application_id": application_id, "assigned_reviewer": reviewer_name}


@router.get("/applications/{application_id}/decisions", response_model=list[schemas.ReviewDecisionOut])
def list_decisions(application_id: str, db: Session = Depends(get_db)):
    return (
        db.query(ReviewDecision)
        .filter(ReviewDecision.application_id == application_id)
        .order_by(ReviewDecision.decided_at.desc())
        .all()
    )


@router.post("/applications/{application_id}/decisions", response_model=schemas.ReviewDecisionOut, status_code=201)
def submit_decision(application_id: str, payload: schemas.ReviewDecisionIn, db: Session = Depends(get_db)):
    application = db.get(Application, application_id)
    if not application:
        raise HTTPException(404, "Application not found")
    if payload.human_decision not in DECISION_TO_STATUS:
        raise HTTPException(400, f"human_decision must be one of {list(DECISION_TO_STATUS)}")
    if not payload.reviewer_name or not payload.reviewer_name.strip():
        raise HTTPException(400, "reviewer_name is required.")

    latest_score = sorted(application.scores, key=lambda s: s.created_at)[-1] if application.scores else None
    ai_recommendation = latest_score.ai_recommendation if latest_score else None

    is_override = bool(
        latest_score
        and (
            (payload.human_decision == "APPROVED" and ai_recommendation not in ("APPROVE",))
            or (payload.human_decision == "REJECTED" and ai_recommendation not in ("REJECT_RECOMMENDATION", "ESCALATE"))
        )
    )
    if is_override and not payload.override_reason:
        raise HTTPException(400, "override_reason is required when the decision differs from the AI recommendation.")

    try:
        decision = ReviewDecision(
            application_id=application_id,
            reviewer_name=payload.reviewer_name,
            ai_recommendation=ai_recommendation,
            human_decision=payload.human_decision,
            score_override=payload.score_override,
            override_reason=payload.override_reason,
            notes=payload.notes,
        )
        db.add(decision)

        # A submitted human decision is the authoritative action in this
        # system — it uses force=True so it's never blocked by an
        # intermediate status technicality (e.g. an application still
        # sitting at REVIEW_PENDING rather than UNDER_REVIEW). The prior
        # status is still captured in the audit trail either way.
        new_status = DECISION_TO_STATUS[payload.human_decision]
        if new_status == ApplicationStatus.NEEDS_INFO:
            workflow_service.transition(db, application, ApplicationStatus.NEEDS_INFO, actor=payload.reviewer_name,
                                         details={"reason": payload.override_reason or payload.notes}, force=True)
        else:
            current = ApplicationStatus(application.status)
            if current != ApplicationStatus.UNDER_REVIEW:
                workflow_service.transition(db, application, ApplicationStatus.UNDER_REVIEW,
                                             actor=payload.reviewer_name, force=True)
            workflow_service.transition(db, application, new_status, actor=payload.reviewer_name, force=True)

        audit_service.log(
            db, application_id, payload.reviewer_name, "REVIEW_DECISION",
            {
                "decision": payload.human_decision,
                "ai_recommendation": ai_recommendation,
                "override": is_override,
                "reason": payload.override_reason,
            },
        )
        db.commit()
        db.refresh(decision)
        return decision
    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(500, f"Could not record decision: {exc}") from exc
