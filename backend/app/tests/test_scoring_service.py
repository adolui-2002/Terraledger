from app.models import Application, Document
from app.services import fraud_service, scoring_service, validation_service


def _complete_application(db):
    app = Application(
        reference_code="APP-SCORE1",
        applicant_name="Complete Applicant",
        applicant_bank_ref="BANKZZZ",
        scheme_name="Environmental Scheme",
        requested_amount=500000,
    )
    db.add(app)
    db.flush()
    texts = {
        "APPLICATION_FORM": "Application form. Requested amount ₹500,000. Duration 18 months.",
        "PROPOSAL": "Detailed proposal. Total project cost ₹500,000. Strong environmental impact expected.",
        "BUDGET": "Budget breakdown. Total budget ₹500,000.",
        "CERTIFICATE": "Certificate issued 2024-01-01.",
    }
    for doc_type, text in texts.items():
        db.add(Document(application_id=app.id, filename=f"{doc_type}.pdf", doc_type=doc_type, raw_text=text))
    db.flush()
    return app


def test_complete_application_scores_reasonably_high(db_session):
    app = _complete_application(db_session)
    validation_service.run_validation(db_session, app)
    fraud_service.run_fraud_checks(db_session, app)
    db_session.flush()

    score = scoring_service.compute_score(db_session, app)
    assert score.total_score >= 60
    assert score.risk_level in ("LOW", "MEDIUM")
    assert score.ai_recommendation in ("APPROVE", "REQUEST_INFO")


def test_incomplete_application_scores_lower_than_complete(db_session):
    complete_app = _complete_application(db_session)
    validation_service.run_validation(db_session, complete_app)
    fraud_service.run_fraud_checks(db_session, complete_app)
    db_session.flush()
    complete_score = scoring_service.compute_score(db_session, complete_app)

    incomplete_app = Application(
        reference_code="APP-SCORE2",
        applicant_name="Incomplete Applicant",
        applicant_bank_ref="BANKYYY",
        scheme_name="Environmental Scheme",
        requested_amount=500000,
    )
    db_session.add(incomplete_app)
    db_session.flush()
    db_session.add(Document(application_id=incomplete_app.id, filename="form.pdf",
                             doc_type="APPLICATION_FORM", raw_text=""))
    db_session.flush()
    validation_service.run_validation(db_session, incomplete_app)
    fraud_service.run_fraud_checks(db_session, incomplete_app)
    db_session.flush()
    incomplete_score = scoring_service.compute_score(db_session, incomplete_app)

    assert incomplete_score.total_score < complete_score.total_score


def test_duplicate_signal_forces_escalation(db_session):
    app1 = _complete_application(db_session)
    validation_service.run_validation(db_session, app1)
    fraud_service.run_fraud_checks(db_session, app1)
    db_session.flush()

    app2 = Application(
        reference_code="APP-SCORE3",
        applicant_name=app1.applicant_name,
        applicant_bank_ref=app1.applicant_bank_ref,
        scheme_name="Environmental Scheme",
        requested_amount=500000,
    )
    db_session.add(app2)
    db_session.flush()
    for doc_type, text in {
        "APPLICATION_FORM": "form", "PROPOSAL": "proposal ₹500,000",
        "BUDGET": "budget ₹500,000", "CERTIFICATE": "Certificate issued 2024-01-01.",
    }.items():
        db_session.add(Document(application_id=app2.id, filename=doc_type, doc_type=doc_type, raw_text=text))
    db_session.flush()
    validation_service.run_validation(db_session, app2)
    fraud_service.run_fraud_checks(db_session, app2)
    db_session.flush()

    score = scoring_service.compute_score(db_session, app2)
    # A HIGH-severity fraud signal (duplicate applicant) always forces an
    # escalation recommendation, regardless of the underlying score.
    assert score.ai_recommendation == "ESCALATE"
    assert any("BANK" in c or "also appear" in c for c in score.reasons_concern)
