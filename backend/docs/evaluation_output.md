# Evaluation Report
Generated: 2026-08-26 02:30:56 UTC
Dataset: 20 synthetic applications

---

## 1. Extraction Accuracy

**Overall accuracy: 95.0%** (38/40 expected fields recovered)

| Category      | Apps | Fields Expected | Fields Recovered | Accuracy |
|---------------|------|-----------------|------------------|----------|
| borderline    | 2    | 4               | 4                | 100.0%   |
| complete      | 2    | 4               | 4                | 100.0%   |
| contradictory | 2    | 4               | 4                | 100.0%   |
| duplicate     | 2    | 4               | 4                | 100.0%   |
| incomplete    | 2    | 4               | 4                | 100.0%   |
| low_quality   | 2    | 4               | 2                | 50.0%    |
| normal        | 6    | 12              | 12               | 100.0%   |
| suspicious    | 2    | 4               | 4                | 100.0%   |

---

## 2. Validation Accuracy

**Overall accuracy: 82.1%** (23/28 checks matched expected outcome)

**Mismatches:**

| Reference | Category | Check              | Expected | Actual |
|-----------|----------|--------------------|----------|--------|
| APP-79434 | complete | required_documents | PASS     | FAIL   |
| APP-14357 | normal   | required_documents | PASS     | FAIL   |
| APP-00360 | normal   | required_documents | PASS     | FAIL   |
| APP-80710 | normal   | required_documents | PASS     | FAIL   |
| APP-88668 | normal   | required_documents | PASS     | FAIL   |

---

## 3. Fraud Detection

**Precision: 33.3%  |  Recall: 100.0%  |  F1: 0.5**

| Metric                                | Value |
|---------------------------------------|-------|
| True Positives (correctly flagged)    | 4     |
| False Positives (incorrectly flagged) | 8     |
| True Negatives (correctly clean)      | 2     |
| False Negatives (missed fraud)        | 0     |

| Reference | Category   | Has Signals | Signal Types                                                                 | Result |
|-----------|------------|-------------|------------------------------------------------------------------------------|--------|
| APP-79434 | complete   | True        | DOCUMENT_REUSE                                                               | FP     |
| APP-25231 | complete   | True        | DOCUMENT_REUSE                                                               | FP     |
| APP-99184 | incomplete | False       | —                                                                            | TN     |
| APP-72433 | incomplete | False       | —                                                                            | TN     |
| APP-06890 | duplicate  | True        | DUPLICATE, DOCUMENT_REUSE, DOCUMENT_REUSE, DOCUMENT_REUSE, DOCUMENT_REUSE    | TP     |
| APP-08251 | duplicate  | True        | DUPLICATE, DOCUMENT_REUSE, DOCUMENT_REUSE, DOCUMENT_REUSE, DOCUMENT_REUSE    | TP     |
| APP-61497 | suspicious | True        | DOCUMENT_REUSE, DOCUMENT_REUSE, DOCUMENT_REUSE, DOCUMENT_REUSE, DATE_ANOMALY | TP     |
| APP-16636 | suspicious | True        | DOCUMENT_REUSE, DOCUMENT_REUSE, DOCUMENT_REUSE, DOCUMENT_REUSE, DATE_ANOMALY | TP     |
| APP-14357 | normal     | True        | DOCUMENT_REUSE                                                               | FP     |
| APP-09708 | normal     | True        | DOCUMENT_REUSE                                                               | FP     |
| APP-00360 | normal     | True        | DOCUMENT_REUSE                                                               | FP     |
| APP-40877 | normal     | True        | DOCUMENT_REUSE                                                               | FP     |
| APP-80710 | normal     | True        | DOCUMENT_REUSE                                                               | FP     |
| APP-88668 | normal     | True        | DOCUMENT_REUSE                                                               | FP     |

---

## 4. Scoring & ML Evaluation

**Score direction accuracy: 66.7%** (approve-worthy categories score ≥70, reject-worthy <70)

**ML accuracy: 100.0%**
**Rule/ML agreement rate: 75.0%**

**Score distribution per category:**

| Category      | Apps | Mean Score | Min  | Max  |
|---------------|------|------------|------|------|
| borderline    | 2    | 60.1       | 60.1 | 60.1 |
| complete      | 2    | 90.0       | 87.0 | 93.0 |
| contradictory | 2    | 79.5       | 79.5 | 79.5 |
| duplicate     | 2    | 57.0       | 57.0 | 57.0 |
| incomplete    | 2    | 84.0       | 74.0 | 94.0 |
| low_quality   | 2    | 95.0       | 92.0 | 98.0 |
| normal        | 6    | 89.0       | 87.0 | 93.0 |
| suspicious    | 2    | 57.0       | 57.0 | 57.0 |

**AI recommendation distribution:**

| Recommendation | Count |
|----------------|-------|
| APPROVE        | 13    |
| ESCALATE       | 4     |
| REQUEST_INFO   | 3     |

---

## 5. Summary

| Dimension | Result |
|---|---|
| Extraction accuracy | 95.0% |
| Validation accuracy | 82.1% |
| Fraud precision | 33.3% |
| Fraud recall | 100.0% |
| Fraud F1 | 0.5 |
| Score direction accuracy | 66.7% |
| ML accuracy (labeled set) | 100.0% |
| Rule/ML agreement rate | 75.0% |

> AI scores and recommendations are advisory. Final determinations are made by human reviewers.
