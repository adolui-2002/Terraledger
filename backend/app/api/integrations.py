"""
Integration adapter status and management endpoints.

  GET  /api/v1/integrations/status
       Returns the configured adapter names and a health snapshot.

  GET  /api/v1/integrations/notifications
       Returns the in-memory log of mock notifications sent during this
       session (mock adapter only — useful for demos and testing).

  POST /api/v1/integrations/portal/sync/{application_id}
       Manually trigger a portal status sync for a specific application.

  POST /api/v1/integrations/portal/fetch-scheme
       Pull scheme metadata from the portal adapter.

  POST /api/v1/integrations/portal/ingest
       Simulate an application arriving from the external schemes portal.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import Application
from app.services.messaging_adapter import MockMessagingAdapter, get_messaging_adapter
from app.services.portal_adapter import get_portal_adapter

router = APIRouter(prefix="/api/v1/integrations", tags=["integrations"])
settings = get_settings()
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Status / health
# ---------------------------------------------------------------------------

@router.get("/status")
def integration_status():
    """Returns which adapters are configured and their type (mock/live)."""
    portal = get_portal_adapter()
    messaging = get_messaging_adapter()
    return {
        "portal_adapter": {
            "name": portal.name,
            "type": settings.portal_adapter,
            "base_url": settings.portal_base_url or "(not configured)",
            "status": "ok",
        },
        "messaging_adapter": {
            "name": messaging.name,
            "type": settings.messaging_adapter,
            "smtp_host": settings.smtp_host or "(not configured)",
            "status": "ok",
        },
        "note": (
            "Both adapters are running in mock mode. No real portal or "
            "messaging calls are made. Set PORTAL_ADAPTER=live and "
            "MESSAGING_ADAPTER=live with provider credentials to enable "
            "real integration."
        ) if settings.portal_adapter == "mock" and settings.messaging_adapter == "mock" else "Live adapters active.",
    }


# ---------------------------------------------------------------------------
# Notification log (mock only)
# ---------------------------------------------------------------------------

@router.get("/notifications")
def list_notifications():
    """Return all mock notifications sent during this session.
    Useful for demoing the messaging flow without a real email server.
    """
    return {
        "adapter": settings.messaging_adapter,
        "count": len(MockMessagingAdapter.get_sent()),
        "notifications": MockMessagingAdapter.get_sent(),
    }


# ---------------------------------------------------------------------------
# Portal: manual status sync
# ---------------------------------------------------------------------------

@router.post("/portal/sync/{application_id}")
def portal_sync(application_id: str, db: Session = Depends(get_db)):
    """Push the current application status to the schemes portal."""
    application = db.get(Application, application_id)
    if not application:
        raise HTTPException(404, "Application not found")
    portal = get_portal_adapter()
    result = portal.sync_application_status(
        application_id=application.id,
        reference_code=application.reference_code,
        status=application.status,
        scheme_name=application.scheme_name,
    )
    logger.info(
        "Manual portal sync triggered",
        extra={"application_id": application_id, "status": application.status,
               "adapter": portal.name},
    )
    return result


# ---------------------------------------------------------------------------
# Portal: fetch scheme metadata
# ---------------------------------------------------------------------------

class FetchSchemeRequest(BaseModel):
    scheme_name: str


@router.post("/portal/fetch-scheme")
def portal_fetch_scheme(payload: FetchSchemeRequest):
    """Pull scheme eligibility metadata from the portal adapter."""
    portal = get_portal_adapter()
    result = portal.fetch_scheme_metadata(payload.scheme_name)
    logger.info(
        "Portal scheme metadata fetched",
        extra={"scheme_name": payload.scheme_name, "adapter": portal.name},
    )
    return result


# ---------------------------------------------------------------------------
# Portal: ingest application from portal
# ---------------------------------------------------------------------------

class PortalApplicationPayload(BaseModel):
    applicant_name: str
    scheme_name: str = "Environmental Scheme"
    requested_amount: float | None = None
    applicant_bank_ref: str | None = None
    language: str = "en"
    portal_reference: str | None = None


@router.post("/portal/ingest", status_code=201)
def portal_ingest(payload: PortalApplicationPayload, db: Session = Depends(get_db)):
    """Simulate receiving an application submitted through the external
    schemes portal. Creates the application record and triggers a portal
    acknowledgement via the portal adapter.
    """
    from app.api.applications import _generate_reference_code
    from app.models import Application
    from app.models.enums import DataSensitivity
    from app.services import audit_service

    application = Application(
        reference_code=_generate_reference_code(),
        applicant_name=payload.applicant_name,
        scheme_name=payload.scheme_name,
        applicant_bank_ref=payload.applicant_bank_ref,
        requested_amount=payload.requested_amount,
        language=payload.language,
        sensitivity=DataSensitivity.RESTRICTED.value,
    )
    db.add(application)
    db.flush()
    audit_service.log(
        db, application.id, "portal", "APPLICATION_SUBMITTED",
        {"reference_code": application.reference_code,
         "portal_reference": payload.portal_reference or "n/a",
         "source": "portal_ingest"},
    )
    db.commit()
    db.refresh(application)

    # Acknowledge back to portal
    portal = get_portal_adapter()
    portal_result = portal.sync_application_status(
        application_id=application.id,
        reference_code=application.reference_code,
        status=application.status,
        scheme_name=application.scheme_name,
    )

    # Notify applicant
    messaging = get_messaging_adapter()
    messaging.notify_applicant(
        application_id=application.id,
        reference_code=application.reference_code,
        applicant_name=application.applicant_name,
        event="APPLICATION_RECEIVED",
        message=(
            f"Dear {application.applicant_name}, your application "
            f"{application.reference_code} for '{application.scheme_name}' "
            "has been received and is being reviewed."
        ),
    )

    logger.info(
        "Application ingested from portal",
        extra={"application_id": application.id,
               "reference": application.reference_code,
               "portal_reference": payload.portal_reference},
    )

    return {
        "application_id": application.id,
        "reference_code": application.reference_code,
        "status": application.status,
        "portal_sync": portal_result,
    }
