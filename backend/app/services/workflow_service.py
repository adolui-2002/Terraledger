"""
Workflow state machine. `ApplicationStatus.allowed_transitions()` is the
single source of truth for what moves are legal — this function is the
only place in the codebase allowed to change `application.status`.
"""
from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.models import Application
from app.models.enums import ApplicationStatus
from app.services import audit_service

logger = logging.getLogger(__name__)


class IllegalTransitionError(Exception):
    pass


def transition(db: Session, application: Application, new_status: ApplicationStatus, actor: str = "system",
                details: dict | None = None, force: bool = False) -> Application:
    """Moves `application` to `new_status`.

    By default this is validated against `ApplicationStatus.allowed_transitions()`
    — the right behaviour for an external actor (a reviewer's decision, an
    assignment) trying to move the workflow forward.

    `force=True` bypasses that check. It exists for exactly one caller:
    `pipeline_service.run_pipeline`, which is allowed to re-walk
    SUBMITTED -> ... -> REVIEW_PENDING even when the application has
    already been through it once (the "re-run pipeline" action) — the
    pipeline itself is the authority on what state it produces next, so
    validating it against the same map that constrains human actions is
    the bug, not a safety feature. The audit trail still records exactly
    what happened either way.
    """
    current = ApplicationStatus(application.status)
    if not force:
        allowed = ApplicationStatus.allowed_transitions().get(current, [])
        if new_status not in allowed and new_status != current:
            raise IllegalTransitionError(
                f"Cannot move application from {current.value} to {new_status.value}."
            )
    previous = application.status
    application.status = new_status.value
    audit_service.log(
        db, application.id, actor, "STATUS_CHANGE",
        {"from": previous, "to": new_status.value, **(details or {})},
    )
    logger.info(
        "Status transition",
        extra={"application_id": application.id, "from": previous,
               "to": new_status.value, "actor": actor, "forced": force},
    )
    return application


def assign_reviewer(db: Session, application: Application, reviewer_name: str, actor: str = "system") -> Application:
    application.assigned_reviewer = reviewer_name
    audit_service.log(db, application.id, actor, "REVIEWER_ASSIGNED", {"reviewer": reviewer_name})
    logger.info("Reviewer assigned", extra={"application_id": application.id, "reviewer": reviewer_name})
    return application
