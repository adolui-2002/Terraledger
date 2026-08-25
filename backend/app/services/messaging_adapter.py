"""
Messaging / notification adapter.

Abstracts email, SMS, and webhook notifications behind a single interface.
The default MockMessagingAdapter logs every notification and stores it
in-memory for inspection via the /api/v1/integrations/notifications
endpoint. No real messages are ever sent by the mock.

A live adapter can be wired in via MESSAGING_ADAPTER=live plus provider
credentials. The rest of the codebase always calls get_messaging_adapter()
and never imports a specific implementation directly.

Notification events used by the pipeline:
  APPLICATION_RECEIVED    Sent to applicant on submission
  APPLICATION_PROCESSING  Sent to applicant when pipeline starts
  REVIEW_ASSIGNED         Sent to reviewer on case assignment
  DECISION_MADE           Sent to applicant on approve/reject/needs-info
  FRAUD_ALERT             Sent to senior reviewer on HIGH fraud signal
  NEEDS_INFO              Sent to applicant requesting missing documents
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import ClassVar

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


# ---------------------------------------------------------------------------
# Base interface
# ---------------------------------------------------------------------------

class BaseMessagingAdapter(ABC):
    name: str = "base"

    @abstractmethod
    def notify_applicant(
        self,
        application_id: str,
        reference_code: str,
        applicant_name: str,
        event: str,
        message: str,
    ) -> dict: ...

    @abstractmethod
    def notify_reviewer(
        self,
        application_id: str,
        reference_code: str,
        reviewer_name: str,
        event: str,
        message: str,
    ) -> dict: ...


# ---------------------------------------------------------------------------
# Mock adapter
# ---------------------------------------------------------------------------

class MockMessagingAdapter(BaseMessagingAdapter):
    """Logs notifications and stores them in a class-level list so they
    can be retrieved via the integrations API endpoint for demo purposes.
    Zero network calls. Safe for RESTRICTED data.
    """

    name = "mock-messaging"
    _sent: ClassVar[list[dict]] = []  # in-memory store for demo retrieval

    @classmethod
    def get_sent(cls) -> list[dict]:
        return list(cls._sent)

    @classmethod
    def clear_sent(cls) -> None:
        cls._sent.clear()

    def _record(self, notification: dict) -> dict:
        notification["adapter"] = self.name
        notification["sent_at"] = datetime.utcnow().isoformat()
        notification["delivered"] = True
        notification["note"] = "Mock adapter — no real message sent."
        MockMessagingAdapter._sent.append(notification)
        return notification

    def notify_applicant(
        self,
        application_id: str,
        reference_code: str,
        applicant_name: str,
        event: str,
        message: str,
    ) -> dict:
        notification = {
            "type": "applicant",
            "application_id": application_id,
            "reference_code": reference_code,
            "recipient": applicant_name,
            "event": event,
            "message": message,
            "channel": "email",  # would be email/SMS in live adapter
        }
        logger.info(
            "[Messaging mock] notify_applicant",
            extra={"application_id": application_id, "event": event,
                   "recipient": applicant_name},
        )
        return self._record(notification)

    def notify_reviewer(
        self,
        application_id: str,
        reference_code: str,
        reviewer_name: str,
        event: str,
        message: str,
    ) -> dict:
        notification = {
            "type": "reviewer",
            "application_id": application_id,
            "reference_code": reference_code,
            "recipient": reviewer_name,
            "event": event,
            "message": message,
            "channel": "email",
        }
        logger.info(
            "[Messaging mock] notify_reviewer",
            extra={"application_id": application_id, "event": event,
                   "recipient": reviewer_name},
        )
        return self._record(notification)


# ---------------------------------------------------------------------------
# Live adapter stub
# ---------------------------------------------------------------------------

class LiveMessagingAdapter(BaseMessagingAdapter):
    """Replace method bodies with real provider calls (SMTP, Twilio, etc.).

    Configure via environment:
      MESSAGING_ADAPTER=live
      SMTP_HOST=smtp.gov.in
      SMTP_PORT=587
      SMTP_USER=noreply@gov.in
      SMTP_PASSWORD=<secret>
    """

    name = "live-messaging"

    def __init__(self, smtp_host: str, smtp_port: int, smtp_user: str, smtp_password: str):
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.smtp_user = smtp_user
        self.smtp_password = smtp_password

    def notify_applicant(self, application_id, reference_code, applicant_name, event, message):
        # TODO: implement real SMTP/SMS send
        # import smtplib
        # ...
        logger.warning("[Messaging live] notify_applicant not yet implemented — falling back to mock")
        return MockMessagingAdapter().notify_applicant(
            application_id, reference_code, applicant_name, event, message
        )

    def notify_reviewer(self, application_id, reference_code, reviewer_name, event, message):
        logger.warning("[Messaging live] notify_reviewer not yet implemented — falling back to mock")
        return MockMessagingAdapter().notify_reviewer(
            application_id, reference_code, reviewer_name, event, message
        )


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def get_messaging_adapter() -> BaseMessagingAdapter:
    adapter_type = getattr(settings, "messaging_adapter", "mock")
    if adapter_type == "live":
        return LiveMessagingAdapter(
            smtp_host=getattr(settings, "smtp_host", ""),
            smtp_port=int(getattr(settings, "smtp_port", 587)),
            smtp_user=getattr(settings, "smtp_user", ""),
            smtp_password=getattr(settings, "smtp_password", ""),
        )
    return MockMessagingAdapter()
