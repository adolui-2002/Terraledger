"""
Validation engine. Every rule comes from app/rules/eligibility_rules.yaml —
adding a new scheme or changing a threshold never requires touching this
file (see solution brief: "configurable business rules").
"""
from __future__ import annotations

from pathlib import Path

import yaml
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Application, Document, ValidationResult
from app.models.enums import ValidationStatus

settings = get_settings()

_RULES_CACHE: dict | None = None


def load_rules() -> dict:
    global _RULES_CACHE
    if _RULES_CACHE is None:
        path = Path(settings.rules_dir) / "eligibility_rules.yaml"
        with open(path) as f:
            _RULES_CACHE = yaml.safe_load(f)
    return _RULES_CACHE


def rules_for_scheme(scheme_name: str) -> dict:
    rules = load_rules()
    return rules.get(scheme_name, rules["default"])


def _add_result(db: Session, application_id: str, check_name: str, category: str, status: str, message: str):
    result = ValidationResult(
        application_id=application_id,
        check_name=check_name,
        category=category,
        status=status,
        message=message,
    )
    db.add(result)
    return result


def run_validation(db: Session, application: Application) -> list[ValidationResult]:
    """Runs completeness, eligibility, and contradiction checks. Returns
    the list of ValidationResult rows created (also persisted to `db`,
    caller is responsible for commit).
    """
    # Clear previous results for idempotent re-validation
    db.query(ValidationResult).filter(ValidationResult.application_id == application.id).delete()

    rules = rules_for_scheme(application.scheme_name)
    results: list[ValidationResult] = []

    # --- Completeness ---
    documents: list[Document] = list(application.documents)
    present_types = {d.doc_type for d in documents}
    required = set(rules.get("required_documents", []))
    missing = required - present_types

    if not documents:
        results.append(_add_result(
            db, application.id, "documents_present", "completeness", ValidationStatus.FAIL,
            "No documents were uploaded with this application.",
        ))
    elif missing:
        results.append(_add_result(
            db, application.id, "required_documents", "completeness", ValidationStatus.FAIL,
            f"Missing required document(s): {', '.join(sorted(missing))}.",
        ))
    else:
        results.append(_add_result(
            db, application.id, "required_documents", "completeness", ValidationStatus.PASS,
            f"All {len(required)} required document types are present.",
        ))

    low_conf_docs = [d for d in documents if d.ocr_confidence is not None and d.ocr_confidence < 0.5]
    if low_conf_docs:
        results.append(_add_result(
            db, application.id, "ocr_quality", "completeness", ValidationStatus.WARNING,
            f"{len(low_conf_docs)} document(s) had low OCR confidence and may need manual verification: "
            + ", ".join(d.filename for d in low_conf_docs),
        ))

    # --- Eligibility ---
    min_budget = rules.get("minimum_project_budget", 0)
    max_budget = rules.get("maximum_project_budget", float("inf"))
    amount = application.requested_amount
    if amount is None:
        results.append(_add_result(
            db, application.id, "budget_range", "eligibility", ValidationStatus.WARNING,
            "No requested amount was captured for this application.",
        ))
    elif not (min_budget <= amount <= max_budget):
        results.append(_add_result(
            db, application.id, "budget_range", "eligibility", ValidationStatus.FAIL,
            f"Requested amount {amount:,.0f} is outside the permitted range "
            f"({min_budget:,.0f} - {max_budget:,.0f}) for {application.scheme_name}.",
        ))
    else:
        results.append(_add_result(
            db, application.id, "budget_range", "eligibility", ValidationStatus.PASS,
            f"Requested amount {amount:,.0f} is within the permitted range.",
        ))

    # --- Contradictions: compare amounts mentioned across documents ---
    from app.services.extraction_service import extract_amounts

    doc_amounts: dict[str, list[float]] = {}
    for d in documents:
        amts = extract_amounts(d.raw_text or "")
        if amts:
            doc_amounts[d.doc_type] = amts

    tolerance = rules.get("contradiction_tolerance_pct", 10) / 100.0
    proposal_amt = max(doc_amounts.get("PROPOSAL", []), default=None)
    budget_amt = max(doc_amounts.get("BUDGET", []), default=None)
    if proposal_amt and budget_amt:
        diff_pct = abs(proposal_amt - budget_amt) / max(proposal_amt, budget_amt)
        if diff_pct > tolerance:
            results.append(_add_result(
                db, application.id, "budget_proposal_consistency", "contradiction", ValidationStatus.FAIL,
                f"Proposal states {proposal_amt:,.0f} but budget document states {budget_amt:,.0f} "
                f"({diff_pct * 100:.1f}% discrepancy, tolerance is {tolerance * 100:.0f}%).",
            ))
        else:
            results.append(_add_result(
                db, application.id, "budget_proposal_consistency", "contradiction", ValidationStatus.PASS,
                "Proposal and budget amounts are consistent.",
            ))

    return results


def validation_summary(results: list[ValidationResult]) -> dict:
    return {
        "pass": sum(1 for r in results if r.status == ValidationStatus.PASS),
        "warning": sum(1 for r in results if r.status == ValidationStatus.WARNING),
        "fail": sum(1 for r in results if r.status == ValidationStatus.FAIL),
    }
