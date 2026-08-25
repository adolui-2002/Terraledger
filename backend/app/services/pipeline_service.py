"""
Orchestrates the end-to-end pipeline described in the solution brief:

    SUBMITTED -> PROCESSING -> VALIDATED -> AI_ANALYZED -> REVIEW_PENDING

Each stage writes its own records (documents/fields already exist by the
time this runs) and an audit log entry, so the full history is
reconstructable from AuditLog alone even if this function is re-run.

Re-running is explicitly supported (the UI's "re-run pipeline" action,
and re-scoring after (re)training the ML model) — the internal
transitions below use `force=True` so re-entering the pipeline from
REVIEW_PENDING or any earlier stage is never blocked by the same state
machine that constrains human reviewer actions. What IS blocked: running
this once a human has started acting on the application (see
NON_REPROCESSABLE_STATUSES) — silently re-scoring out from under a
reviewer's in-progress or completed decision would be far worse than an
error message.
"""
from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.models import Application, ExtractedField
from app.models.enums import ApplicationStatus
from app.services import audit_service, fraud_service, scoring_service, validation_service, workflow_service
from app.services.extraction_service import extract_structured_fields
from app.services.messaging_adapter import get_messaging_adapter
from app.services.portal_adapter import get_portal_adapter

logger = logging.getLogger(__name__)

NON_REPROCESSABLE_STATUSES = {
    ApplicationStatus.UNDER_REVIEW.value,
    ApplicationStatus.NEEDS_INFO.value,
    ApplicationStatus.APPROVED.value,
    ApplicationStatus.REJECTED.value,
    ApplicationStatus.CLOSED.value,
}


class PipelineNotReprocessableError(Exception):
    pass


def run_pipeline(db: Session, application: Application) -> Application:
    if application.status in NON_REPROCESSABLE_STATUSES:
        raise PipelineNotReprocessableError(
            f"Cannot re-run the pipeline: this application is already at '{application.status}' "
            "and a reviewer has acted on it. Re-processing would overwrite that decision's context."
        )

    is_rerun = application.status != ApplicationStatus.SUBMITTED.value
    logger.info(
        "Pipeline started",
        extra={"application_id": application.id, "reference": application.reference_code,
               "is_rerun": is_rerun, "current_status": application.status},
    )

    workflow_service.transition(db, application, ApplicationStatus.PROCESSING, actor="system", force=True)
    if is_rerun:
        audit_service.log(db, application.id, "system", "PIPELINE_RERUN", {})

    # Re-derive structured fields from all document text (idempotent)
    db.query(ExtractedField).filter(ExtractedField.application_id == application.id).delete()
    for doc in application.documents:
        for name, value in extract_structured_fields(doc.raw_text or "").items():
            db.add(ExtractedField(
                application_id=application.id,
                source_document_id=doc.id,
                field_name=name,
                field_value=value,
                confidence=0.75 if doc.ocr_used else 0.95,
            ))
    doc_count = len(application.documents)
    audit_service.log(db, application.id, "system", "EXTRACTION_COMPLETE",
                       {"documents_processed": doc_count})
    logger.info("Extraction complete", extra={"application_id": application.id, "documents_processed": doc_count})

    validation_results = validation_service.run_validation(db, application)
    summary = validation_service.validation_summary(validation_results)
    workflow_service.transition(db, application, ApplicationStatus.VALIDATED, actor="system", details=summary,
                                 force=True)
    logger.info(
        "Validation complete",
        extra={"application_id": application.id, **summary},
    )

    fraud_signals = fraud_service.run_fraud_checks(db, application)
    if fraud_signals:
        audit_service.log(db, application.id, "system", "FRAUD_SIGNALS_DETECTED",
                           {"count": len(fraud_signals), "types": [s.signal_type for s in fraud_signals]})
        logger.warning(
            "Fraud signals detected",
            extra={"application_id": application.id, "count": len(fraud_signals),
                   "types": [s.signal_type for s in fraud_signals]},
        )

    db.flush()
    score = scoring_service.compute_score(db, application)
    db.add(score)
    workflow_service.transition(
        db, application, ApplicationStatus.AI_ANALYZED, actor="ai",
        details={"score": score.total_score, "risk": score.risk_level, "recommendation": score.ai_recommendation},
        force=True,
    )
    logger.info(
        "Scoring complete",
        extra={"application_id": application.id, "score": score.total_score,
               "risk": score.risk_level, "recommendation": score.ai_recommendation},
    )

    workflow_service.transition(db, application, ApplicationStatus.REVIEW_PENDING, actor="system", force=True)

    db.commit()
    db.refresh(application)

    # Notify applicant that processing is complete and under review
    try:
        messaging = get_messaging_adapter()
        messaging.notify_applicant(
            application_id=application.id,
            reference_code=application.reference_code,
            applicant_name=application.applicant_name,
            event="APPLICATION_PROCESSING",
            message=(
                f"Dear {application.applicant_name}, your application "
                f"{application.reference_code} has been processed and is now "
                "pending human review. You will be notified once a decision is made."
            ),
        )
        # Sync status back to portal
        portal = get_portal_adapter()
        portal.sync_application_status(
            application_id=application.id,
            reference_code=application.reference_code,
            status=application.status,
            scheme_name=application.scheme_name,
        )
    except Exception as exc:
        # Adapter failures must never block the pipeline
        logger.warning("Adapter call failed after pipeline", extra={"error": str(exc),
                       "application_id": application.id})

    logger.info(
        "Pipeline complete — application routed to review",
        extra={"application_id": application.id, "reference": application.reference_code},
    )
    return application
