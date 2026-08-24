import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class Reviewer(Base):
    __tablename__ = "reviewers"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String, unique=True)
    role: Mapped[str] = mapped_column(String, default="Reviewer")
    active_caseload: Mapped[int] = mapped_column(Integer, default=0)


class ReviewDecision(Base):
    __tablename__ = "review_decisions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    application_id: Mapped[str] = mapped_column(ForeignKey("applications.id"), index=True)

    reviewer_name: Mapped[str] = mapped_column(String)
    ai_recommendation: Mapped[str] = mapped_column(String, nullable=True)
    human_decision: Mapped[str] = mapped_column(String)  # APPROVED | REJECTED | NEEDS_INFO
    score_override: Mapped[float | None] = mapped_column(nullable=True)
    override_reason: Mapped[str] = mapped_column(Text, nullable=True)
    notes: Mapped[str] = mapped_column(Text, nullable=True)

    decided_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    application = relationship("Application", back_populates="review_decisions")
