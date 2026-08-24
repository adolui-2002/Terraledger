from datetime import datetime, timedelta

from app.models import Application, Document
from app.services import fraud_service
from app.services.extraction_service import content_hash


def _make_application(db, **kwargs):
    defaults = dict(
        reference_code=f"APP-{kwargs.get('_suffix', '1')}",
        applicant_name="Same Applicant",
        applicant_bank_ref="BANK123",
        scheme_name="Environmental Scheme",
        requested_amount=500000,
    )
    kwargs.pop("_suffix", None)
    defaults.update(kwargs)
    app = Application(**defaults)
    db.add(app)
    db.flush()
    return app


def test_duplicate_applicant_detected(db_session):
    app1 = _make_application(db_session, reference_code="APP-A")
    app2 = _make_application(db_session, reference_code="APP-B")
    db_session.flush()

    signals = fraud_service.run_fraud_checks(db_session, app2)
    assert any(s.signal_type == "DUPLICATE" for s in signals)


def test_no_duplicate_when_bank_ref_differs(db_session):
    app1 = _make_application(db_session, reference_code="APP-A", applicant_bank_ref="BANK111")
    app2 = _make_application(db_session, reference_code="APP-B", applicant_bank_ref="BANK222")
    db_session.flush()

    signals = fraud_service.run_fraud_checks(db_session, app2)
    assert not any(s.signal_type == "DUPLICATE" for s in signals)


def test_reused_document_detected(db_session):
    text = "Identical proposal text used twice."
    app1 = _make_application(db_session, reference_code="APP-A", applicant_bank_ref="BANK111")
    app2 = _make_application(db_session, reference_code="APP-B", applicant_bank_ref="BANK222")
    db_session.add(Document(application_id=app1.id, filename="proposal.pdf", doc_type="PROPOSAL",
                             raw_text=text, content_hash=content_hash(text.encode())))
    db_session.add(Document(application_id=app2.id, filename="proposal.pdf", doc_type="PROPOSAL",
                             raw_text=text, content_hash=content_hash(text.encode())))
    db_session.flush()

    signals = fraud_service.run_fraud_checks(db_session, app2)
    assert any(s.signal_type == "DOCUMENT_REUSE" for s in signals)


def test_future_dated_certificate_flagged(db_session):
    app = _make_application(db_session, reference_code="APP-C", applicant_bank_ref="BANK999")
    future_date = (datetime.utcnow() + timedelta(days=400)).strftime("%Y-%m-%d")
    db_session.add(Document(application_id=app.id, filename="cert.pdf", doc_type="CERTIFICATE",
                             raw_text=f"Certificate issued {future_date}."))
    db_session.flush()

    signals = fraud_service.run_fraud_checks(db_session, app)
    assert any(s.signal_type == "DATE_ANOMALY" and s.severity == "HIGH" for s in signals)
