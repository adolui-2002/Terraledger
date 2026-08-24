import io


def _create_application(client, **overrides):
    payload = {
        "applicant_name": "API Test Applicant",
        "scheme_name": "Environmental Scheme",
        "applicant_bank_ref": "BANKAPI1",
        "requested_amount": 400000,
        "language": "en",
    }
    payload.update(overrides)
    resp = client.post("/api/v1/applications", json=payload)
    assert resp.status_code == 201
    return resp.json()


def test_health_endpoint(client):
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_create_application_and_upload_documents(client):
    app = _create_application(client)
    app_id = app["id"]

    for doc_type, filename, content in [
        ("APPLICATION_FORM", "form.txt", b"Application form. Requested amount Rs. 400,000."),
        ("PROPOSAL", "proposal.txt", b"Proposal. Total project cost Rs. 400,000."),
        ("BUDGET", "budget.txt", b"Budget. Total budget Rs. 400,000."),
        ("CERTIFICATE", "cert.txt", b"Certificate issued 2024-01-01."),
    ]:
        resp = client.post(
            f"/api/v1/applications/{app_id}/documents",
            data={"doc_type": doc_type},
            files={"file": (filename, io.BytesIO(content), "text/plain")},
        )
        assert resp.status_code == 201, resp.text

    resp = client.post(f"/api/v1/applications/{app_id}/process")
    assert resp.status_code == 200
    detail = resp.json()
    assert detail["status"] == "REVIEW_PENDING"
    assert len(detail["scores"]) == 1
    assert detail["scores"][0]["total_score"] > 0


def test_processing_without_documents_returns_400(client):
    app = _create_application(client)
    resp = client.post(f"/api/v1/applications/{app['id']}/process")
    assert resp.status_code == 400


def test_corrupt_upload_does_not_crash_pipeline(client):
    app = _create_application(client)
    app_id = app["id"]
    resp = client.post(
        f"/api/v1/applications/{app_id}/documents",
        data={"doc_type": "PROPOSAL"},
        files={"file": ("broken.pdf", io.BytesIO(b"%PDF-not-a-real-file\x00\x01\x02"), "application/pdf")},
    )
    assert resp.status_code == 201  # upload itself always succeeds
    resp = client.post(f"/api/v1/applications/{app_id}/process")
    assert resp.status_code == 200  # pipeline degrades gracefully, never 500s


def test_override_requires_reason(client):
    app = _create_application(client, requested_amount=50)  # deliberately fails eligibility
    app_id = app["id"]
    client.post(
        f"/api/v1/applications/{app_id}/documents",
        data={"doc_type": "APPLICATION_FORM"},
        files={"file": ("form.txt", io.BytesIO(b"form"), "text/plain")},
    )
    client.post(f"/api/v1/applications/{app_id}/process")

    resp = client.post(
        f"/api/v1/applications/{app_id}/decisions",
        json={"reviewer_name": "A. Sharma", "human_decision": "APPROVED"},
    )
    # AI will have recommended REJECT/ESCALATE for a budget-ineligible case,
    # so an APPROVED decision without a reason must be rejected.
    assert resp.status_code == 400


def test_override_with_reason_is_recorded_in_audit_trail(client):
    app = _create_application(client, requested_amount=50)
    app_id = app["id"]
    client.post(
        f"/api/v1/applications/{app_id}/documents",
        data={"doc_type": "APPLICATION_FORM"},
        files={"file": ("form.txt", io.BytesIO(b"form"), "text/plain")},
    )
    client.post(f"/api/v1/applications/{app_id}/process")

    resp = client.post(
        f"/api/v1/applications/{app_id}/decisions",
        json={
            "reviewer_name": "A. Sharma",
            "human_decision": "APPROVED",
            "override_reason": "Manual verification confirmed eligibility despite the flag.",
        },
    )
    assert resp.status_code == 201

    audit = client.get(f"/api/v1/applications/{app_id}/audit").json()
    override_entries = [a for a in audit if a["action"] == "REVIEW_DECISION" and a["details"].get("override")]
    assert len(override_entries) == 1


def test_assistant_never_declares_final_decision(client):
    app = _create_application(client)
    app_id = app["id"]
    resp = client.post("/api/v1/assistant/ask", json={"application_id": app_id, "question": "Why this score?"})
    assert resp.status_code == 200
    body = resp.json()
    assert "human reviewer" in body["guardrail_note"].lower()
