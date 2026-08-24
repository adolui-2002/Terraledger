import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class AuditLog(Base):
    """Append-only audit trail. Every state-changing action in the system
    writes exactly one row here — this is the source of truth for the
    reviewer-facing timeline and for compliance/audit exports.
    """

    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    application_id: Mapped[str] = mapped_column(ForeignKey("applications.id"), index=True)

    actor: Mapped[str] = mapped_column(String)      # "system" | "ai" | reviewer name
    action: Mapped[str] = mapped_column(String)      # e.g. "STATUS_CHANGE", "SCORE_OVERRIDE"
    details: Mapped[dict] = mapped_column(JSON, default=dict)

    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    application = relationship("Application", back_populates="audit_logs")
