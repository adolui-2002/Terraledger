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

import io
import logging
import random
from pathlib import Path

from app.config import get_settings
from app.database import SessionLocal, init_db
from app.models import Application, Document
from app.models.enums import DataSensitivity
from app.services import extraction_service, pipeline_service
from app.services.extraction_service import content_hash

logger = logging.getLogger(__name__)

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

# Multilingual templates — used to generate non-English synthetic applications
# that stress-test language detection, transliteration-tolerant extraction,
# and the multilingual pipeline flag in the reviewer UI.
PROPOSAL_TEXT_HI = (
    "यह परियोजना 4 वार्डों में विकेंद्रीकृत अपशिष्ट जल उपचार और वर्षा जल संचयन प्रणाली स्थापित करने का प्रस्ताव करती है। "
    "कुल परियोजना लागत Rs.{amount} अनुमानित है। कार्यान्वयन योजना में सामुदायिक प्रशिक्षण, त्रैमासिक निगरानी शामिल है।"
)
FORM_TEXT_HI = "आवेदन पत्र: {scheme}। आवेदक: {name}। अनुरोधित राशि Rs.{amount}। अवधि 18 माह।"
BUDGET_TEXT_HI = (
    "बजट विवरण: उपकरण Rs.{equip}, निर्माण कार्य Rs.{civil}, प्रशिक्षण Rs.{train}, "
    "आकस्मिक Rs.{contingency}. कुल बजट Rs.{amount}."
)
CERTIFICATE_TEXT_HI = "यह पर्यावरण कार्यान्वयन भागीदार के रूप में पंजीकरण प्रमाणित करता है, जारी {date}।"

PROPOSAL_TEXT_TA = (
    "இந்த திட்டம் 4 வார்டுகளில் பரவலாக்கப்பட்ட கழிவுநீர் சுத்திகரிப்பு மற்றும் "
    "மழைநீர் சேகரிப்பு அமைப்பை நிறுவ முன்மொழிகிறது. மொத்த திட்ட செலவு Rs.{amount} ஆக மதிப்பிடப்படுகிறது।"
)
FORM_TEXT_TA = "விண்ணப்பப் படிவம்: {scheme}. விண்ணப்பதாரர்: {name}. கோரிய தொகை Rs.{amount}. காலம் 18 மாதங்கள்."


def _make_pdf_bytes(text: str) -> bytes:
    """Render text as a real, openable PDF using fpdf2."""
    from fpdf import FPDF
    # Replace ₹ with Rs. — built-in PDF fonts are latin-1 only
    safe_text = text.replace("₹", "Rs.")
    pdf = FPDF()
    pdf.set_margins(20, 20, 20)
    pdf.add_page()
    pdf.set_font("Helvetica", size=11)
    pdf.multi_cell(0, 7, safe_text)
    return pdf.output()


def _make_xlsx_bytes(text: str) -> bytes:
    """Render budget text as a real XLSX workbook using openpyxl."""
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Budget"
    # Split on commas/periods to put each item on its own row
    for i, line in enumerate(text.replace(". ", "\n").replace(", ", "\n").splitlines(), start=1):
        ws.cell(row=i, column=1, value=line.strip())
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _file_bytes(filename: str, text: str) -> bytes:
    """Return properly formatted bytes for the given filename extension."""
    suffix = Path(filename).suffix.lower()
    if suffix == ".pdf":
        return _make_pdf_bytes(text)
    if suffix in (".xlsx", ".xlsm"):
        return _make_xlsx_bytes(text)
    # .txt, .jpg placeholders, etc. — plain UTF-8
    return text.encode("utf-8")


def _mk_doc(application_id: str, doc_type: str, filename: str, text: str, ocr_used=False, ocr_conf=None):
    data = _file_bytes(filename, text)
    hash_ = content_hash(data)

    settings = get_settings()
    # application_id is None at call time (flushed later); we write the file
    # in a staging dir keyed by hash and move it once the id is known.
    # Simpler: write into a temp dir named by hash and rename on add().
    staging_path = Path(settings.document_storage_path) / "_staging" / f"{hash_[:12]}_{filename}"
    staging_path.parent.mkdir(parents=True, exist_ok=True)
    staging_path.write_bytes(data)

    return Document(
        application_id=application_id,
        filename=filename,
        doc_type=doc_type,
        content_hash=hash_,
        storage_path=str(staging_path),  # updated in add() once app id is known
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
        db.flush()  # app.id is now assigned

        settings = get_settings()
        app_dir = Path(settings.document_storage_path) / app.id
        app_dir.mkdir(parents=True, exist_ok=True)

        for d in docs:
            d.application_id = app.id
            # Move the staged file into the per-application directory
            if d.storage_path:
                staging = Path(d.storage_path)
                dest = app_dir / staging.name
                if staging.exists():
                    staging.rename(dest)
                d.storage_path = str(dest)
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

    # 9. MULTILINGUAL — Hindi application (stress-tests language detection pipeline)
    for lang_code, form_tmpl, proposal_tmpl, budget_tmpl, cert_tmpl in [
        ("hi", FORM_TEXT_HI, PROPOSAL_TEXT_HI, BUDGET_TEXT_HI, CERTIFICATE_TEXT_HI),
        ("ta", FORM_TEXT_TA, PROPOSAL_TEXT_TA, BUDGET_TEXT, CERTIFICATE_TEXT),
    ]:
        name = random.choice(APPLICANTS)
        scheme = random.choice(SCHEMES)
        amount = random.randint(150000, 900000)
        app = _base_application(name, scheme, amount, "normal")
        app.language = lang_code
        docs = [
            _mk_doc(None, "APPLICATION_FORM", "form.pdf",
                    form_tmpl.format(scheme=scheme, name=name, amount=amount)),
            _mk_doc(None, "PROPOSAL", "proposal.pdf",
                    proposal_tmpl.format(amount=amount)),
            _mk_doc(None, "BUDGET", "budget.xlsx",
                    budget_tmpl.format(
                        equip=int(amount * 0.4), civil=int(amount * 0.35),
                        train=int(amount * 0.1), contingency=int(amount * 0.15),
                        amount=amount)),
            _mk_doc(None, "CERTIFICATE", "certificate.pdf",
                    cert_tmpl.format(date="2024-05-05") if "{date}" in cert_tmpl else cert_tmpl),
        ]
        add(app, docs)

    # Run the full pipeline on every seeded application so scores/validation/
    # fraud signals/audit trail are populated and ready to demo immediately.
    for app in created:
        try:
            pipeline_service.run_pipeline(db, app)
        except Exception as exc:  # keep seeding even if one record fails
            logger.error("Pipeline failed during seeding",
                         extra={"reference": app.reference_code, "error": str(exc)})

    return created


if __name__ == "__main__":
    from app.logging_config import configure_logging
    configure_logging()

    init_db()
    session = SessionLocal()
    try:
        apps = generate(session)
        logger.info("Seeding complete", extra={"count": len(apps)})
        for a in apps:
            latest = sorted(a.scores, key=lambda s: s.created_at)[-1] if a.scores else None
            score_txt = f"{latest.total_score}/100 ({latest.risk_level})" if latest else "no score"
            logger.info(
                "Seeded application",
                extra={"reference": a.reference_code, "category": a.synthetic_category,
                       "applicant": a.applicant_name, "score": score_txt},
            )

        logger.info("Training ML model on seeded data...")
        from app.ml.train import train_model

        model, metadata, error = train_model(session)
        if error:
            logger.warning("ML training skipped", extra={"reason": error})
        else:
            logger.info(
                "ML model trained",
                extra={"version": metadata.version, "n_samples": metadata.n_samples,
                       "n_positive": metadata.n_positive, "n_negative": metadata.n_negative},
            )
            logger.info("Re-scoring seeded applications with new model...")
            from app.ml import ml_scoring_service

            ml_scoring_service.invalidate_cache()
            for a in apps:
                try:
                    pipeline_service.run_pipeline(session, a)
                except Exception as exc:
                    logger.error("Re-scoring failed",
                                 extra={"reference": a.reference_code, "error": str(exc)})
    finally:
        session.close()
