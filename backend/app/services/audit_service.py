from sqlalchemy.orm import Session

from app.models import AuditLog


def log(db: Session, application_id: str, actor: str, action: str, details: dict | None = None) -> AuditLog:
    entry = AuditLog(
        application_id=application_id,
        actor=actor,
        action=action,
        details=details or {},
    )
    db.add(entry)
    return entry
