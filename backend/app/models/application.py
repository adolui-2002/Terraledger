import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import ApplicationStatus, DataSensitivity


def _uuid() -> str:
    return str(uuid.uuid4())


class Application(Base):
    __tablename__ = "applications"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    reference_code: Mapped[str] = mapped_column(String, unique=True, index=True)

    scheme_name: Mapped[str] = mapped_column(String, default="Environmental Scheme")
    applicant_name: Mapped[str] = mapped_column(String)
    applicant_bank_ref: Mapped[str] = mapped_column(String, nullable=True)

    status: Mapped[str] = mapped_column(String, default=ApplicationStatus.SUBMITTED.value, index=True)
    language: Mapped[str] = mapped_column(String, default="en")

    requested_amount: Mapped[float] = mapped_column(Float, nullable=True)

    sensitivity: Mapped[str] = mapped_column(String, default=DataSensitivity.RESTRICTED.value)
    synthetic_category: Mapped[str] = mapped_column(String, nullable=True)  # for demo dataset labeling

    assigned_reviewer: Mapped[str] = mapped_column(String, nullable=True)

    submitted_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    documents = relationship("Document", back_populates="application", cascade="all, delete-orphan")
    extracted_fields = relationship("ExtractedField", back_populates="application", cascade="all, delete-orphan")
    validation_results = relationship("ValidationResult", back_populates="application", cascade="all, delete-orphan")
    scores = relationship("Score", back_populates="application", cascade="all, delete-orphan")
    fraud_signals = relationship("FraudSignal", back_populates="application", cascade="all, delete-orphan")
    review_decisions = relationship("ReviewDecision", back_populates="application", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="application", cascade="all, delete-orphan")
    ai_feedback = relationship("AIFeedback", back_populates="application", cascade="all, delete-orphan")
