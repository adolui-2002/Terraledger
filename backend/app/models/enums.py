import enum


class ApplicationStatus(str, enum.Enum):
    SUBMITTED = "SUBMITTED"
    PROCESSING = "PROCESSING"
    VALIDATED = "VALIDATED"
    AI_ANALYZED = "AI_ANALYZED"
    REVIEW_PENDING = "REVIEW_PENDING"
    UNDER_REVIEW = "UNDER_REVIEW"
    NEEDS_INFO = "NEEDS_INFO"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CLOSED = "CLOSED"

    @classmethod
    def allowed_transitions(cls) -> dict[str, list[str]]:
        return {
            cls.SUBMITTED: [cls.PROCESSING],
            cls.PROCESSING: [cls.VALIDATED],
            cls.VALIDATED: [cls.AI_ANALYZED],
            cls.AI_ANALYZED: [cls.REVIEW_PENDING],
            cls.REVIEW_PENDING: [cls.UNDER_REVIEW],
            cls.UNDER_REVIEW: [cls.NEEDS_INFO, cls.APPROVED, cls.REJECTED],
            cls.NEEDS_INFO: [cls.UNDER_REVIEW],
            cls.APPROVED: [cls.CLOSED],
            cls.REJECTED: [cls.CLOSED],
            cls.CLOSED: [],
        }


class DocumentType(str, enum.Enum):
    APPLICATION_FORM = "APPLICATION_FORM"
    PROPOSAL = "PROPOSAL"
    BUDGET = "BUDGET"
    CERTIFICATE = "CERTIFICATE"
    PREVIOUS_REPORT = "PREVIOUS_REPORT"
    PHOTO = "PHOTO"
    OTHER = "OTHER"


class ValidationStatus(str, enum.Enum):
    PASS = "PASS"
    WARNING = "WARNING"
    FAIL = "FAIL"


class RiskLevel(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class FraudSeverity(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class DataSensitivity(str, enum.Enum):
    """Every stored record is tagged for its trust boundary.

    RESTRICTED records (default for anything containing applicant/citizen
    data) must never be sent to an external AI provider. Only SYNTHETIC
    demo data or fully redacted text may cross that boundary, and only
    when AI_PROVIDER is explicitly set to a cloud provider.
    """

    RESTRICTED = "RESTRICTED"
    SYNTHETIC = "SYNTHETIC"
