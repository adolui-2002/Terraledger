from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ApplicationCreate(BaseModel):
    applicant_name: str
    scheme_name: str = "Environmental Scheme"
    applicant_bank_ref: str | None = None
    requested_amount: float | None = None
    language: str = "en"


class ExtractedFieldOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    field_name: str
    field_value: str
    confidence: float


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    filename: str
    doc_type: str
    ocr_used: bool
    ocr_confidence: float | None
    detected_language: str | None
    uploaded_at: datetime


class ValidationResultOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    check_name: str
    category: str
    status: str
    message: str


class FraudSignalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    signal_type: str
    description: str
    severity: str
    related_application_id: str | None


class ScoreOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    total_score: float
    breakdown: dict
    max_breakdown: dict
    confidence: float
    risk_level: str
    ai_recommendation: str
    explanation: str
    reasons_positive: list
    reasons_concern: list
    ml_approval_probability: float | None = None
    ml_model_version: str | None = None
    shap_explanation: list = []
    model_agreement: str | None = None
    created_at: datetime


class ReviewDecisionIn(BaseModel):
    reviewer_name: str
    human_decision: str  # APPROVED | REJECTED | NEEDS_INFO
    score_override: float | None = None
    override_reason: str | None = None
    notes: str | None = None


class ReviewDecisionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    reviewer_name: str
    ai_recommendation: str | None
    human_decision: str
    score_override: float | None
    override_reason: str | None
    notes: str | None
    decided_at: datetime


class AuditLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    actor: str
    action: str
    details: dict
    timestamp: datetime


class ApplicationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    reference_code: str
    scheme_name: str
    applicant_name: str
    status: str
    language: str
    requested_amount: float | None
    sensitivity: str
    synthetic_category: str | None
    assigned_reviewer: str | None
    submitted_at: datetime
    updated_at: datetime


class ApplicationDetailOut(ApplicationOut):
    documents: list[DocumentOut] = []
    extracted_fields: list[ExtractedFieldOut] = []
    validation_results: list[ValidationResultOut] = []
    fraud_signals: list[FraudSignalOut] = []
    scores: list[ScoreOut] = []
    review_decisions: list[ReviewDecisionOut] = []


class AssistantQuery(BaseModel):
    application_id: str | None = None
    question: str


class AssistantAnswer(BaseModel):
    answer: str
    guardrail_note: str = (
        "This assistant provides recommendations and explanations only. "
        "Final determinations are made by a human reviewer."
    )
    sources: list[str] = []


class ApplicationSummaryOut(BaseModel):
    summary: str
    structured_digest: str
    document_count: int
    has_fraud_signals: bool
    has_validation_failures: bool
    ai_recommendation: str | None
    risk_level: str | None
    total_score: float | None


class AnalyticsSummary(BaseModel):
    total_applications: int
    by_status: dict[str, int]
    by_risk: dict[str, int]
    duplicates_flagged: int
    missing_documents_flagged: int
    average_score: float
    average_processing_hours: float | None
    override_rate: float


class MLModelStatus(BaseModel):
    trained: bool
    version: str | None = None
    trained_at: str | None = None
    n_samples: int | None = None
    n_positive: int | None = None
    n_negative: int | None = None
    train_accuracy: float | None = None


class MLTrainResponse(BaseModel):
    success: bool
    message: str
    status: MLModelStatus
