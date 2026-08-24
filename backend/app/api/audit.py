from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import schemas
from app.database import get_db
from app.models import AuditLog

router = APIRouter(prefix="/api/v1/applications", tags=["audit"])


@router.get("/{application_id}/audit", response_model=list[schemas.AuditLogOut])
def get_audit_trail(application_id: str, db: Session = Depends(get_db)):
    return (
        db.query(AuditLog)
        .filter(AuditLog.application_id == application_id)
        .order_by(AuditLog.timestamp.asc())
        .all()
    )
