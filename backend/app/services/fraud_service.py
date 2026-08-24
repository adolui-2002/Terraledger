"""
Fraud / suspicious-application signals.

Deliberately signal-based, not a black-box "fraud score" — every signal
here is explainable in one sentence, matching the brief's guidance to
flag rather than declare fraud confirmed. A human reviewer always makes
the final call.
"""
from __future__ import annotations

import hashlib
from datetime import datetime

from sqlalchemy.orm import Session

from app.models import Application, Document, FraudSignal
from app.models.enums import FraudSeverity
from app.services.extraction_service import extract_dates
from app.services.validation_service import rules_for_scheme


def _applicant_fingerprint(application: Application) -> str:
    raw = f"{application.applicant_name.strip().lower()}|{(application.applicant_bank_ref or '').strip().lower()}"
    return hashlib.sha256(raw.encode()).hexdigest()


def detect_duplicates(db: Session, application: Application) -> list[FraudSignal]:
    signals = []
    fingerprint = _applicant_fingerprint(application)
    others = (
        db.query(Application)
        .filter(Application.id != application.id)
        .all()
    )
    for other in others:
        if _applicant_fingerprint(other) == fingerprint:
            signals.append(FraudSignal(
                application_id=application.id,
                signal_type="DUPLICATE",
                description=(
                    f"Same applicant name and bank reference also appear on application "
                    f"{other.reference_code}."
                ),
                severity=FraudSeverity.HIGH,
                related_application_id=other.id,
            ))
    return signals


def detect_document_reuse(db: Session, application: Application) -> list[FraudSignal]:
    signals = []
    for doc in application.documents:
        if not doc.content_hash:
            continue
        reused = (
            db.query(Document)
            .filter(Document.content_hash == doc.content_hash, Document.application_id != application.id)
            .first()
        )
        if reused:
            signals.append(FraudSignal(
                application_id=application.id,
                signal_type="DOCUMENT_REUSE",
                description=(
                    f"Document '{doc.filename}' is byte-identical to a document submitted under "
                    f"application {reused.application_id}."
                ),
                severity=FraudSeverity.MEDIUM,
                related_application_id=reused.application_id,
            ))
    return signals


def detect_date_anomalies(db: Session, application: Application) -> list[FraudSignal]:
    signals = []
    rules = rules_for_scheme(application.scheme_name)
    max_age_years = rules.get("max_certificate_age_years", 5)

    for doc in application.documents:
        if doc.doc_type != "CERTIFICATE" or not doc.raw_text:
            continue
        dates = extract_dates(doc.raw_text)
        if not dates:
            continue
        try:
            cert_date = datetime.strptime(dates[0], "%Y-%m-%d")
        except ValueError:
            continue
        age_years = (datetime.utcnow() - cert_date).days / 365.25
        if age_years > max_age_years:
            signals.append(FraudSignal(
                application_id=application.id,
                signal_type="DATE_ANOMALY",
                description=(
                    f"Certificate '{doc.filename}' is dated {dates[0]}, which is "
                    f"{age_years:.1f} years old (maximum allowed is {max_age_years})."
                ),
                severity=FraudSeverity.MEDIUM,
            ))
        elif cert_date > datetime.utcnow():
            signals.append(FraudSignal(
                application_id=application.id,
                signal_type="DATE_ANOMALY",
                description=f"Certificate '{doc.filename}' has a future date ({dates[0]}).",
                severity=FraudSeverity.HIGH,
            ))
    return signals


def run_fraud_checks(db: Session, application: Application) -> list[FraudSignal]:
    db.query(FraudSignal).filter(FraudSignal.application_id == application.id).delete()
    signals = (
        detect_duplicates(db, application)
        + detect_document_reuse(db, application)
        + detect_date_anomalies(db, application)
    )
    for s in signals:
        db.add(s)
    return signals
