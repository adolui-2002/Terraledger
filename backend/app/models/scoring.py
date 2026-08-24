import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class Score(Base):
    __tablename__ = "scores"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    application_id: Mapped[str] = mapped_column(ForeignKey("applications.id"), index=True)

    total_score: Mapped[float] = mapped_column(Float)
    breakdown: Mapped[dict] = mapped_column(JSON)          # {category: points}
    max_breakdown: Mapped[dict] = mapped_column(JSON)      # {category: max points}
    confidence: Mapped[float] = mapped_column(Float)
    risk_level: Mapped[str] = mapped_column(String)        # RiskLevel
    ai_recommendation: Mapped[str] = mapped_column(String) # APPROVE | ESCALATE | REQUEST_INFO | REJECT_RECOMMENDATION
    explanation: Mapped[str] = mapped_column(Text)
    reasons_positive: Mapped[list] = mapped_column(JSON, default=list)
    reasons_concern: Mapped[list] = mapped_column(JSON, default=list)

    # --- Explainable ML second opinion (GradientBoostingClassifier + SHAP) ---
    # Populated only once a model has been trained (see app/ml/train.py);
    # left null otherwise so the deterministic score above always stands
    # on its own.
    ml_approval_probability: Mapped[float] = mapped_column(Float, nullable=True)
    ml_model_version: Mapped[str] = mapped_column(String, nullable=True)
    shap_explanation: Mapped[list] = mapped_column(JSON, default=list)
    model_agreement: Mapped[str] = mapped_column(String, nullable=True)  # AGREE | DISAGREE | null

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    application = relationship("Application", back_populates="scores")


class FraudSignal(Base):
    __tablename__ = "fraud_signals"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    application_id: Mapped[str] = mapped_column(ForeignKey("applications.id"), index=True)

    signal_type: Mapped[str] = mapped_column(String)   # DUPLICATE | CONTRADICTION | DOCUMENT_REUSE | DATE_ANOMALY
    description: Mapped[str] = mapped_column(Text)
    severity: Mapped[str] = mapped_column(String)       # FraudSeverity
    related_application_id: Mapped[str] = mapped_column(String, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    application = relationship("Application", back_populates="fraud_signals")
