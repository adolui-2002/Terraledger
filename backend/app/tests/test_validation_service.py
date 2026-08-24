from app.models import Application, Document
from app.models.enums import ValidationStatus
from app.services import validation_service


def _make_application(db, **kwargs):
    defaults = dict(
        reference_code="APP-TEST1",
        applicant_name="Test Applicant",
        scheme_name="Environmental Scheme",
        requested_amount=500000,
    )
    defaults.update(kwargs)
    app = Application(**defaults)
    db.add(app)
    db.flush()
    return app


def test_missing_required_documents_flagged_as_fail(db_session):
    app = _make_application(db_session)
    db_session.add(Document(application_id=app.id, filename="form.pdf", doc_type="APPLICATION_FORM", raw_text=""))
    db_session.flush()

    results = validation_service.run_validation(db_session, app)
    completeness_fail = [r for r in results if r.check_name == "required_documents"]
    assert completeness_fail[0].status == ValidationStatus.FAIL
    assert "Missing required document" in completeness_fail[0].message


def test_complete_documents_pass(db_session):
    app = _make_application(db_session)
    for doc_type in ["APPLICATION_FORM", "PROPOSAL", "BUDGET", "CERTIFICATE"]:
        db_session.add(Document(application_id=app.id, filename=f"{doc_type}.pdf", doc_type=doc_type, raw_text=""))
    db_session.flush()

    results = validation_service.run_validation(db_session, app)
    completeness = [r for r in results if r.check_name == "required_documents"][0]
    assert completeness.status == ValidationStatus.PASS


def test_budget_out_of_range_fails_eligibility(db_session):
    app = _make_application(db_session, requested_amount=50)  # below minimum
    results = validation_service.run_validation(db_session, app)
    eligibility = [r for r in results if r.check_name == "budget_range"][0]
    assert eligibility.status == ValidationStatus.FAIL


def test_contradictory_amounts_detected(db_session):
    app = _make_application(db_session)
    db_session.add(Document(
        application_id=app.id, filename="proposal.pdf", doc_type="PROPOSAL",
        raw_text="Total project cost is ₹1,000,000.",
    ))
    db_session.add(Document(
        application_id=app.id, filename="budget.pdf", doc_type="BUDGET",
        raw_text="Total budget ₹600,000.",
    ))
    db_session.flush()

    results = validation_service.run_validation(db_session, app)
    contradiction = [r for r in results if r.category == "contradiction"][0]
    assert contradiction.status == ValidationStatus.FAIL


def test_no_documents_at_all_does_not_crash(db_session):
    app = _make_application(db_session)
    results = validation_service.run_validation(db_session, app)
    assert any(r.status == ValidationStatus.FAIL for r in results)
