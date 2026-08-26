"""
Reviewer feedback on AI scoring quality.

Reviewers can rate each AI scoring result on two dimensions:
  - rating: HELPFUL | PARTIALLY_HELPFUL | NOT_HELPFUL
  - score_accuracy: ACCURATE | PARTIALLY_ACCURATE | INACCURATE
  - comment: optional free-text explanation

This data is:
  1. Shown in the application detail view alongside the score
  2. Aggregated in the feedback analytics endpoint
  3. Available as a signal for future model improvement cycles
     (not fed back automatically — a human must review and trigger
     retraining, per the brief's human-oversight requirement)
"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class AIFeedback(Base):
    __tablename__ = "ai_feedback"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    application_id: Mapped[str] = mapped_column(ForeignKey("applications.id"), index=True)
    score_id: Mapped[str] = mapped_column(ForeignKey("scores.id"), nullable=True)

    reviewer_name: Mapped[str] = mapped_column(String)

    # Was the AI recommendation useful to the reviewer?
    rating: Mapped[str] = mapped_column(String)          # HELPFUL | PARTIALLY_HELPFUL | NOT_HELPFUL

    # Did the score reflect the actual quality of the application?
    score_accuracy: Mapped[str] = mapped_column(String)  # ACCURATE | PARTIALLY_ACCURATE | INACCURATE

    comment: Mapped[str] = mapped_column(Text, nullable=True)

    submitted_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    application = relationship("Application", back_populates="ai_feedback")
