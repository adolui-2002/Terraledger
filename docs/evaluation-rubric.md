# Evaluation Rubric

This document defines how to measure the platform against the synthetic
dataset produced by `app/data/synthetic_generator.py`, so grading /
self-evaluation is reproducible rather than anecdotal.

## 1. Synthetic dataset categories

| Category | Count (default seed) | What it stresses |
|---|---|---|
| `complete` | 2 | Baseline: full document set, consistent figures |
| `incomplete` | 2 | Missing required documents (`required_documents` check) |
| `contradictory` | 2 | Proposal vs. budget amount mismatch beyond tolerance |
| `low_quality` | 2 | Poor OCR confidence (<0.5), degraded extraction |
| `duplicate` | 2 (1 pair) | Same applicant name + bank reference |
| `suspicious` | 2 | Future-dated certificate + reused proposal document (byte-identical) |
| `borderline` | 2 | Deliberately near the approve/reject score threshold |
| `normal` | 6 (configurable) | Volume filler, same shape as `complete` |

Regenerate with a different mix by editing the counts in
`generate()` or calling it with a different `n_normal`.

## 2. Extraction evaluation

Run:
```
docker compose exec backend python -m app.data.synthetic_generator
```
Then, for each seeded application, compare `ExtractedField` rows against
the known-injected values in the generator's template strings (amounts,
dates, durations). Because the synthetic generator embeds the ground
truth directly in the text it writes, extraction accuracy = (fields
correctly recovered) / (fields injected) — no separate labeling pass
needed.

## 3. Validation accuracy

Expected outcome per category (what a correct system should flag):

| Category | `required_documents` | `budget_range` | `budget_proposal_consistency` |
|---|---|---|---|
| complete | PASS | PASS | PASS |
| incomplete | **FAIL** | — | — |
| contradictory | PASS | PASS | **FAIL** |
| duplicate | PASS | PASS | PASS |
| suspicious | PASS | PASS | PASS |
| borderline | **FAIL** (budget doc omitted) | PASS | — |

Compare `GET /api/v1/applications/{id}` → `validation_results` against
this table after seeding to confirm the validation engine's accuracy on
the labeled set.

## 4. Fraud/duplicate detection accuracy

| Category | Expected signal |
|---|---|
| duplicate | `DUPLICATE` (HIGH) on the second submission |
| suspicious | `DOCUMENT_REUSE` (MEDIUM) and/or `DATE_ANOMALY` (HIGH, future-dated certificate) |
| all others | no fraud signals |

False positive rate = signals raised on `complete`/`normal`/`incomplete`
applications (should be ~0). False negative rate = missing signals on
`duplicate`/`suspicious` applications (should be ~0 given the generator's
deliberately unambiguous construction).

## 5. Scoring agreement

Two independent numbers are produced per application:

1. **Rule-based score** (`Score.total_score`, 0–100, deterministic).
2. **ML approval probability** (`Score.ml_approval_probability`, once
   `POST /api/v1/ml/train` has run) — a `GradientBoostingClassifier`
   trained on the same labeled categories, evaluated on a held-out split
   (`train_accuracy` in `GET /api/v1/ml/status`).

`Score.model_agreement` (`AGREE`/`DISAGREE`) is the operational metric:
track what fraction of applications show disagreement over time as a
signal that either the rule weights or the ML feature set need revisiting.

## 6. Negative tests (see `app/tests/`)

| Test file | Failure mode covered |
|---|---|
| `test_extraction_service.py` | Corrupt PDF/image/xlsx never raises; extraction degrades to empty text + OCR flag instead |
| `test_api_workflow.py::test_processing_without_documents_returns_400` | Pipeline refuses to run with no input, doesn't silently score nothing |
| `test_api_workflow.py::test_corrupt_upload_does_not_crash_pipeline` | End-to-end: a malformed upload still reaches `REVIEW_PENDING` |
| `test_api_workflow.py::test_override_requires_reason` | AI unavailable / disagreement path: reviewer cannot silently diverge from the AI recommendation without justification |
| `test_api_workflow.py::test_override_with_reason_is_recorded_in_audit_trail` | Every override is durably auditable |
| `test_api_workflow.py::test_assistant_never_declares_final_decision` | Guardrail: the conversational assistant cannot state a final determination |
| `test_ml_scoring.py::test_train_model_below_minimum_samples_returns_error` | ML training fails safe rather than fitting on too little data |

## 7. Bias / uncertainty handling

- **Uncertainty**: every `Score` carries a `confidence` value, reduced by
  the number of fraud signals and validation warnings present — a
  reviewer sees explicitly when the AI is less sure, not just a number.
- **Bias check (manual, POC-scope)**: because `applicant_name` and
  `applicant_bank_ref` are *not* included in `FEATURE_NAMES`
  (`app/ml/feature_engineering.py`), the ML model structurally cannot
  learn a direct name-based bias. For a production rollout, this should
  be extended with a fairness audit across the `APPLICANTS` name pool
  (which intentionally spans several naming conventions) comparing score
  distributions by name origin.
