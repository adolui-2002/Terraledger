from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import schemas
from app.database import get_db
from app.models import Application, FraudSignal, ReviewDecision, Score, ValidationResult
from app.models.enums import ValidationStatus

router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])


@router.get("/summary", response_model=schemas.AnalyticsSummary)
def summary(db: Session = Depends(get_db)):
    applications = db.query(Application).all()
    total = len(applications)

    by_status: dict[str, int] = {}
    by_risk: dict[str, int] = {}
    scores: list[float] = []
    processing_hours: list[float] = []

    for a in applications:
        by_status[a.status] = by_status.get(a.status, 0) + 1
        if a.scores:
            latest = sorted(a.scores, key=lambda s: s.created_at)[-1]
            by_risk[latest.risk_level] = by_risk.get(latest.risk_level, 0) + 1
            scores.append(latest.total_score)
            processing_hours.append((latest.created_at - a.submitted_at).total_seconds() / 3600.0)

    duplicates = db.query(FraudSignal).filter(FraudSignal.signal_type == "DUPLICATE").count()
    missing_docs = (
        db.query(ValidationResult)
        .filter(ValidationResult.check_name == "required_documents", ValidationResult.status == ValidationStatus.FAIL)
        .count()
    )

    decisions = db.query(ReviewDecision).all()
    overrides = sum(1 for d in decisions if d.override_reason)
    override_rate = round(overrides / len(decisions), 3) if decisions else 0.0

    return schemas.AnalyticsSummary(
        total_applications=total,
        by_status=by_status,
        by_risk=by_risk,
        duplicates_flagged=duplicates,
        missing_documents_flagged=missing_docs,
        average_score=round(sum(scores) / len(scores), 1) if scores else 0.0,
        average_processing_hours=round(sum(processing_hours) / len(processing_hours), 2) if processing_hours else None,
        override_rate=override_rate,
    )


@router.get("/timeline")
def processing_timeline(db: Session = Depends(get_db)):
    """Applications submitted per day, for a simple trend chart."""
    applications = db.query(Application).all()
    buckets: dict[str, int] = {}
    for a in applications:
        key = a.submitted_at.strftime("%Y-%m-%d")
        buckets[key] = buckets.get(key, 0) + 1
    return dict(sorted(buckets.items()))
