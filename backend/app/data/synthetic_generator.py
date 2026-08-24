"""
Synthetic dataset generator.

Produces labeled applications across the categories required by the
solution brief: complete, incomplete, contradictory, low-quality,
duplicate, suspicious, and borderline — plus a few normal ones. Every
application is tagged `sensitivity=SYNTHETIC` and `synthetic_category`
so the evaluation rubric can filter on it later (see
docs/evaluation-rubric.md).

Run inside the backend container:
    docker compose exec backend python -m app.data.synthetic_generator
"""
from __future__ import annotations

import random

from app.database import SessionLocal, init_db
from app.models import Application, Document
from app.models.enums import DataSensitivity
from app.services import extraction_service, pipeline_service
from app.services.extraction_service import content_hash

APPLICANTS = [
    "Meera Chatterjee", "Rohan Das", "Fatima Sheikh", "Arjun Nair", "Priya Ghosh",
    "Sandeep Rao", "Ananya Bose", "Vikram Mehta", "Kavita Reddy", "Imran Ali",
    "Sneha Kulkarni", "Devraj Singh", "Lakshmi Pillai", "Tanvir Ahmed", "Ritu Verma",
]

SCHEMES = ["Environmental Scheme", "Climate Resilience Grant"]

PROPOSAL_TEXT = (
    "This project proposes to install a decentralized wastewater treatment and "
    "rainwater harvesting system covering 4 wards, reducing groundwater extraction "
    "by an estimated 30 percent over 18 months. Total project cost is estimated at "
    "₹{amount}. The implementation plan includes community training, quarterly "
    "monitoring, and a maintenance fund covering the following 3 years."
)
BUDGET_TEXT = (
    "Budget breakdown: Equipment ₹{equip}, Civil works ₹{civil}, Training ₹{train}, "
    "Contingency ₹{contingency}. Total budget ₹{amount}."
)
CERTIFICATE_TEXT = "This certifies registration as an environmental implementation partner, issued {date}."
FORM_TEXT = "Application form for {scheme}. Applicant: {name}. Requested amount ₹{amount}. Duration 18 months."
LOW_QUALITY_TEXT = "prjct enviromnt schme app.. amt ~ rs {amount} (scan unclear) sig illegible"


def _mk_doc(application_id: str, doc_type: str, filename: str, text: str, ocr_used=False, ocr_conf=None):
    return Document(
        application_id=application_id,
        filename=filename,
        doc_type=doc_type,
        content_hash=content_hash(text.encode()),
        raw_text=text,
        ocr_used=ocr_used,
        ocr_confidence=ocr_conf,
        detected_language="en",
    )


def _base_application(name: str, scheme: str, amount: float, category: str) -> Application:
    from app.api.applications import _generate_reference_code

    return Application(
        reference_code=_generate_reference_code(),
        applicant_name=name,
        scheme_name=scheme,
        applicant_bank_ref=f"BANK{random.randint(10000, 99999)}",
        requested_amount=amount,
        sensitivity=DataSensitivity.SYNTHETIC.value,
        synthetic_category=category,
    )


def generate(db, n_normal: int = 6):
    created: list[Application] = []

    def add(app: Application, docs: list[Document]):
        db.add(app)
        db.flush()
        for d in docs:
            d.application_id = app.id
            db.add(d)
        db.commit()
        db.refresh(app)
        created.append(app)
        return app

    # 1. COMPLETE
    for i in range(2):
        name = random.choice(APPLICANTS)
        scheme = random.choice(SCHEMES)
        amount = random.randint(150000, 900000)
        app = _base_application(name, scheme, amount, "complete")
        docs = [
            _mk_doc(None, "APPLICATION_FORM", "form.pdf", FORM_TEXT.format(scheme=scheme, name=name, amount=amount)),
            _mk_doc(None, "PROPOSAL", "proposal.pdf", PROPOSAL_TEXT.format(amount=amount)),
            _mk_doc(None, "BUDGET", "budget.xlsx", BUDGET_TEXT.format(
                equip=int(amount * 0.4), civil=int(amount * 0.35), train=int(amount * 0.1),
                contingency=int(amount * 0.15), amount=amount)),
            _mk_doc(None, "CERTIFICATE", "certificate.pdf", CERTIFICATE_TEXT.format(date="2024-03-15")),
        ]
        add(app, docs)

    # 2. INCOMPLETE — missing certificate
    for i in range(2):
        name = random.choice(APPLICANTS)
        scheme = random.choice(SCHEMES)
        amount = random.randint(150000, 900000)
        app = _base_application(name, scheme, amount, "incomplete")
        docs = [
            _mk_doc(None, "APPLICATION_FORM", "form.pdf", FORM_TEXT.format(scheme=scheme, name=name, amount=amount)),
            _mk_doc(None, "PROPOSAL", "proposal.pdf", PROPOSAL_TEXT.format(amount=amount)),
        ]
        add(app, docs)

    # 3. CONTRADICTORY — proposal vs budget mismatch
    for i in range(2):
        name = random.choice(APPLICANTS)
        scheme = random.choice(SCHEMES)
        proposal_amount = random.randint(800000, 1200000)
        budget_amount = int(proposal_amount * 0.6)
        app = _base_application(name, scheme, proposal_amount, "contradictory")
        docs = [
            _mk_doc(None, "APPLICATION_FORM", "form.pdf", FORM_TEXT.format(scheme=scheme, name=name, amount=proposal_amount)),
            _mk_doc(None, "PROPOSAL", "proposal.pdf", PROPOSAL_TEXT.format(amount=proposal_amount)),
            _mk_doc(None, "BUDGET", "budget.xlsx", BUDGET_TEXT.format(
                equip=int(budget_amount * 0.4), civil=int(budget_amount * 0.35), train=int(budget_amount * 0.1),
                contingency=int(budget_amount * 0.15), amount=budget_amount)),
            _mk_doc(None, "CERTIFICATE", "certificate.pdf", CERTIFICATE_TEXT.format(date="2023-11-01")),
        ]
        add(app, docs)

    # 4. LOW QUALITY — poor OCR scans
    for i in range(2):
        name = random.choice(APPLICANTS)
        scheme = random.choice(SCHEMES)
        amount = random.randint(150000, 900000)
        app = _base_application(name, scheme, amount, "low_quality")
        docs = [
            _mk_doc(None, "APPLICATION_FORM", "form_scan.jpg", LOW_QUALITY_TEXT.format(amount=amount), ocr_used=True, ocr_conf=0.31),
            _mk_doc(None, "PROPOSAL", "proposal_scan.jpg", LOW_QUALITY_TEXT.format(amount=amount), ocr_used=True, ocr_conf=0.28),
            _mk_doc(None, "BUDGET", "budget.xlsx", BUDGET_TEXT.format(
                equip=int(amount * 0.4), civil=int(amount * 0.35), train=int(amount * 0.1),
                contingency=int(amount * 0.15), amount=amount)),
            _mk_doc(None, "CERTIFICATE", "certificate.pdf", CERTIFICATE_TEXT.format(date="2024-01-10")),
        ]
        add(app, docs)

    # 5. DUPLICATE — same applicant + bank ref submitted twice
    name = random.choice(APPLICANTS)
    scheme = random.choice(SCHEMES)
    amount = random.randint(150000, 900000)
    bank_ref = f"BANK{random.randint(10000, 99999)}"
    for i in range(2):
        app = _base_application(name, scheme, amount, "duplicate")
        app.applicant_bank_ref = bank_ref
        docs = [
            _mk_doc(None, "APPLICATION_FORM", "form.pdf", FORM_TEXT.format(scheme=scheme, name=name, amount=amount)),
            _mk_doc(None, "PROPOSAL", "proposal.pdf", PROPOSAL_TEXT.format(amount=amount)),
            _mk_doc(None, "BUDGET", "budget.xlsx", BUDGET_TEXT.format(
                equip=int(amount * 0.4), civil=int(amount * 0.35), train=int(amount * 0.1),
                contingency=int(amount * 0.15), amount=amount)),
            _mk_doc(None, "CERTIFICATE", "certificate.pdf", CERTIFICATE_TEXT.format(date="2024-02-20")),
        ]
        add(app, docs)

    # 6. SUSPICIOUS — future-dated certificate + reused document text
    name = random.choice(APPLICANTS)
    scheme = random.choice(SCHEMES)
    amount = random.randint(150000, 900000)
    reused_proposal_text = PROPOSAL_TEXT.format(amount=amount)
    for i in range(2):
        app = _base_application(name if i == 0 else random.choice(APPLICANTS), scheme, amount, "suspicious")
        docs = [
            _mk_doc(None, "APPLICATION_FORM", "form.pdf", FORM_TEXT.format(scheme=scheme, name=name, amount=amount)),
            _mk_doc(None, "PROPOSAL", "proposal.pdf", reused_proposal_text),  # identical across both -> DOCUMENT_REUSE
            _mk_doc(None, "BUDGET", "budget.xlsx", BUDGET_TEXT.format(
                equip=int(amount * 0.4), civil=int(amount * 0.35), train=int(amount * 0.1),
                contingency=int(amount * 0.15), amount=amount)),
            _mk_doc(None, "CERTIFICATE", "certificate.pdf", CERTIFICATE_TEXT.format(date="2027-06-01")),  # future date
        ]
        add(app, docs)

    # 7. BORDERLINE — score should land right around the review threshold
    for i in range(2):
        name = random.choice(APPLICANTS)
        scheme = random.choice(SCHEMES)
        amount = random.randint(150000, 900000)
        app = _base_application(name, scheme, amount, "borderline")
        docs = [
            _mk_doc(None, "APPLICATION_FORM", "form.pdf", FORM_TEXT.format(scheme=scheme, name=name, amount=amount)),
            _mk_doc(None, "PROPOSAL", "proposal.pdf", "Brief proposal. " + PROPOSAL_TEXT.format(amount=amount)[:120]),
            _mk_doc(None, "BUDGET", "budget.xlsx", BUDGET_TEXT.format(
                equip=int(amount * 0.4), civil=int(amount * 0.35), train=int(amount * 0.1),
                contingency=int(amount * 0.15), amount=amount)),
        ]
        add(app, docs)

    # 8. NORMAL — everyday complete applications, for volume
    for i in range(n_normal):
        name = random.choice(APPLICANTS)
        scheme = random.choice(SCHEMES)
        amount = random.randint(150000, 900000)
        app = _base_application(name, scheme, amount, "normal")
        docs = [
            _mk_doc(None, "APPLICATION_FORM", "form.pdf", FORM_TEXT.format(scheme=scheme, name=name, amount=amount)),
            _mk_doc(None, "PROPOSAL", "proposal.pdf", PROPOSAL_TEXT.format(amount=amount)),
            _mk_doc(None, "BUDGET", "budget.xlsx", BUDGET_TEXT.format(
                equip=int(amount * 0.4), civil=int(amount * 0.35), train=int(amount * 0.1),
                contingency=int(amount * 0.15), amount=amount)),
            _mk_doc(None, "CERTIFICATE", "certificate.pdf", CERTIFICATE_TEXT.format(date="2024-05-05")),
        ]
        add(app, docs)

    # Run the full pipeline on every seeded application so scores/validation/
    # fraud signals/audit trail are populated and ready to demo immediately.
    for app in created:
        try:
            pipeline_service.run_pipeline(db, app)
        except Exception as exc:  # keep seeding even if one record fails
            print(f"  ! pipeline failed for {app.reference_code}: {exc}")

    return created


if __name__ == "__main__":
    init_db()
    session = SessionLocal()
    try:
        apps = generate(session)
        print(f"Seeded {len(apps)} synthetic applications:")
        for a in apps:
            latest = sorted(a.scores, key=lambda s: s.created_at)[-1] if a.scores else None
            score_txt = f"{latest.total_score}/100 ({latest.risk_level})" if latest else "no score"
            print(f"  {a.reference_code:10s} [{a.synthetic_category:12s}] {a.applicant_name:20s} -> {score_txt}")

        print("\nTraining the explainable ML scoring model on the seeded data...")
        from app.ml.train import train_model

        model, metadata, error = train_model(session)
        if error:
            print(f"  ML training skipped: {error}")
        else:
            print(f"  Trained {metadata.version} on {metadata.n_samples} samples "
                  f"({metadata.n_positive} positive / {metadata.n_negative} negative).")
            print("  Re-scoring seeded applications with the new model...")
            from app.ml import ml_scoring_service

            ml_scoring_service.invalidate_cache()
            for a in apps:
                try:
                    pipeline_service.run_pipeline(session, a)
                except Exception as exc:
                    print(f"  ! re-scoring failed for {a.reference_code}: {exc}")
    finally:
        session.close()
