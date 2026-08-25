"""
Schemes Portal integration adapter.

Abstracts all communication with the external schemes portal behind a
single interface. The default (and only required) implementation is
MockPortalAdapter — fully deterministic, makes zero network calls, and
is safe to use with RESTRICTED data because nothing leaves the deployment.

A live adapter (e.g. REST calls to the portal's API) can be swapped in
by setting PORTAL_ADAPTER=live in the environment and implementing
LivePortalAdapter below. The rest of the codebase never imports a
specific adapter directly — it always calls get_portal_adapter().

Capabilities provided:
  sync_application_status   Push a status update to the portal so the
                            applicant's portal dashboard reflects the
                            current processing state.
  fetch_scheme_metadata     Pull scheme eligibility parameters from the
                            portal (budget ranges, required docs, etc.)
                            so the rules engine stays in sync without a
                            manual YAML edit.
  submit_portal_application Ingest an application that originated on the
                            external portal (mock returns synthetic data).
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from datetime import datetime

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


# ---------------------------------------------------------------------------
# Base interface
# ---------------------------------------------------------------------------

class BasePortalAdapter(ABC):
    name: str = "base"

    @abstractmethod
    def sync_application_status(
        self,
        application_id: str,
        reference_code: str,
        status: str,
        scheme_name: str,
    ) -> dict: ...

    @abstractmethod
    def fetch_scheme_metadata(self, scheme_name: str) -> dict: ...

    @abstractmethod
    def submit_portal_application(self, portal_payload: dict) -> dict: ...


# ---------------------------------------------------------------------------
# Mock adapter — default, safe for RESTRICTED data, no network calls
# ---------------------------------------------------------------------------

class MockPortalAdapter(BasePortalAdapter):
    """Deterministic mock that logs every call and returns plausible
    synthetic responses. No network calls ever made.

    This is the correct adapter for on-prem / air-gapped deployments and
    for any environment processing RESTRICTED citizen data.
    """

    name = "mock-portal"

    def sync_application_status(
        self,
        application_id: str,
        reference_code: str,
        status: str,
        scheme_name: str,
    ) -> dict:
        logger.info(
            "[Portal mock] sync_application_status called",
            extra={
                "adapter": self.name,
                "application_id": application_id,
                "reference_code": reference_code,
                "status": status,
                "scheme_name": scheme_name,
            },
        )
        return {
            "adapter": self.name,
            "synced": True,
            "portal_reference": f"PORTAL-{reference_code}",
            "status_pushed": status,
            "timestamp": datetime.utcnow().isoformat(),
            "note": "Mock adapter — no real portal call made.",
        }

    def fetch_scheme_metadata(self, scheme_name: str) -> dict:
        logger.info(
            "[Portal mock] fetch_scheme_metadata called",
            extra={"adapter": self.name, "scheme_name": scheme_name},
        )
        # Return a synthetic metadata structure matching eligibility_rules.yaml
        return {
            "adapter": self.name,
            "scheme_name": scheme_name,
            "minimum_project_budget": 100000,
            "maximum_project_budget": 1000000,
            "required_documents": [
                "APPLICATION_FORM", "PROPOSAL", "BUDGET", "CERTIFICATE",
            ],
            "contradiction_tolerance_pct": 10,
            "max_certificate_age_years": 5,
            "source": "mock — would be fetched from portal API in production",
        }

    def submit_portal_application(self, portal_payload: dict) -> dict:
        logger.info(
            "[Portal mock] submit_portal_application called",
            extra={"adapter": self.name, "applicant": portal_payload.get("applicant_name"),
                   "scheme": portal_payload.get("scheme_name")},
        )
        return {
            "adapter": self.name,
            "accepted": True,
            "internal_reference": f"APP-PORTAL-{datetime.utcnow().strftime('%H%M%S')}",
            "note": "Mock adapter — application would be forwarded to portal in production.",
        }


# ---------------------------------------------------------------------------
# Live adapter stub — implement when a real portal API is available
# ---------------------------------------------------------------------------

class LivePortalAdapter(BasePortalAdapter):
    """Replace method bodies with real HTTP calls to the portal API.

    Configure via environment:
      PORTAL_ADAPTER=live
      PORTAL_BASE_URL=https://schemes.gov.in/api
      PORTAL_API_KEY=<secret>
    """

    name = "live-portal"

    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url
        self.api_key = api_key

    def sync_application_status(self, application_id, reference_code, status, scheme_name):
        # TODO: implement real portal call
        # import requests
        # requests.post(f"{self.base_url}/applications/{reference_code}/status",
        #               headers={"X-API-Key": self.api_key},
        #               json={"status": status}, timeout=10)
        logger.warning("[Portal live] sync_application_status not yet implemented — falling back to mock")
        return MockPortalAdapter().sync_application_status(application_id, reference_code, status, scheme_name)

    def fetch_scheme_metadata(self, scheme_name):
        logger.warning("[Portal live] fetch_scheme_metadata not yet implemented — falling back to mock")
        return MockPortalAdapter().fetch_scheme_metadata(scheme_name)

    def submit_portal_application(self, portal_payload):
        logger.warning("[Portal live] submit_portal_application not yet implemented — falling back to mock")
        return MockPortalAdapter().submit_portal_application(portal_payload)


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def get_portal_adapter() -> BasePortalAdapter:
    adapter_type = getattr(settings, "portal_adapter", "mock")
    if adapter_type == "live":
        base_url = getattr(settings, "portal_base_url", "")
        api_key = getattr(settings, "portal_api_key", "")
        return LivePortalAdapter(base_url=base_url, api_key=api_key)
    return MockPortalAdapter()
