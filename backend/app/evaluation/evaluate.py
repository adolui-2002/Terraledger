"""
End-to-end evaluation script.

Measures the platform's accuracy against the synthetic dataset on four
dimensions defined in docs/evaluation-rubric.md:

  1. Extraction accuracy   — did we recover the amounts/dates/durations
                             that the generator injected into each document?
  2. Validation accuracy   — does each application's validation results
                             match the expected outcome for its category?
  3. Fraud detection       — precision/recall on the labeled categories
                             that should (and should not) trigger signals.
  4. Scoring agreement     — rule-based score distributions per category,
                             ML accuracy, and model agreement rate.

Run:
    docker compose exec backend python -m app.evaluation.evaluate
    # or locally (with the venv active):
    python -m app.evaluation.evaluate

Output is written to:
    docs/evaluation_output.md   Human-readable Markdown report
    docs/evaluation_output.json Machine-readable JSON (for CI assertions)
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Bootstrap — must happen before any app imports so settings are loaded
# ---------------------------------------------------------------------------
import os
os.environ.setdefault("DATABASE_URL", "sqlite:///./eco_review_dev.db")

from app.database import SessionLocal, init_db  # noqa: E402
from app.ml.feature_engineering import APPROVE_WORTHY_CATEGORIES, REJECT_WORTHY_CATEGORIES  # noqa: E402
from app.models import Application  # noqa: E402
from app.models.enums import ValidationStatus  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _latest_score(app: Application):
    if not app.scores:
        return None
    return sorted(app.scores, key=lambda s: s.created_at)[-1]


def _pct(n: int, d: int) -> str:
    if d == 0:
        return "n/a"
    return f"{n / d * 100:.1f}%"


def _pass_fail(ok: bool) -> str:
    return "PASS" if ok else "FAIL"


# ---------------------------------------------------------------------------
# 1. Extraction evaluation
# ---------------------------------------------------------------------------

# Ground-truth field names injected by the synthetic generator
EXPECTED_FIELDS = {"extracted_amount", "project_duration"}
# extracted_date is only present in docs with a certificate text

def evaluate_extraction(apps: list[Application]) -> dict:
    total_expected = 0
    total_recovered = 0
    per_category: dict[str, dict] = defaultdict(lambda: {"expected": 0, "recovered": 0, "apps": 0})

    for app in apps:
        cat = app.synthetic_category or "unknown"
        extracted = {f.field_name for f in app.extracted_fields}
        # Each app should have at least extracted_amount and project_duration
        expected_count = len(EXPECTED_FIELDS)
        recovered_count = len(EXPECTED_FIELDS & extracted)
        total_expected += expected_count
        total_recovered += recovered_count
        per_category[cat]["expected"] += expected_count
        per_category[cat]["recovered"] += recovered_count
        per_category[cat]["apps"] += 1

    overall_accuracy = total_recovered / total_expected if total_expected else 0.0
    return {
        "total_apps": len(apps),
        "total_fields_expected": total_expected,
        "total_fields_recovered": total_recovered,
        "overall_accuracy": round(overall_accuracy, 4),
        "overall_accuracy_pct": _pct(total_recovered, total_expected),
        "per_category": {
            cat: {
                "apps": v["apps"],
                "accuracy": _pct(v["recovered"], v["expected"]),
                "recovered": v["recovered"],
                "expected": v["expected"],
            }
            for cat, v in sorted(per_category.items())
        },
    }


# ---------------------------------------------------------------------------
# 2. Validation accuracy
# ---------------------------------------------------------------------------

# Expected validation outcomes per category
# Keys are (category, check_name) -> expected status
VALIDATION_EXPECTATIONS: dict[str, dict[str, str]] = {
    "complete":      {"required_documents": "PASS", "budget_range": "PASS", "budget_proposal_consistency": "PASS"},
    "incomplete":    {"required_documents": "FAIL"},
    "contradictory": {"budget_proposal_consistency": "FAIL"},
    "low_quality":   {},   # no specific validation failure expected (OCR quality is a warning, not fail)
    "duplicate":     {"required_documents": "PASS"},
    "suspicious":    {"required_documents": "PASS"},
    "borderline":    {"required_documents": "FAIL"},   # missing CERTIFICATE in borderline
    "normal":        {"required_documents": "PASS", "budget_range": "PASS"},
}


def evaluate_validation(apps: list[Application]) -> dict:
    total_checks = 0
    correct_checks = 0
    mismatches: list[dict] = []

    for app in apps:
        cat = app.synthetic_category or "unknown"
        expectations = VALIDATION_EXPECTATIONS.get(cat, {})
        validation_map = {v.check_name: v.status for v in app.validation_results}

        for check_name, expected_status in expectations.items():
            actual = validation_map.get(check_name, "MISSING")
            total_checks += 1
            if actual == expected_status:
                correct_checks += 1
            else:
                mismatches.append({
                    "reference": app.reference_code,
                    "category": cat,
                    "check": check_name,
                    "expected": expected_status,
                    "actual": actual,
                })

    accuracy = correct_checks / total_checks if total_checks else 0.0
    return {
        "total_checks": total_checks,
        "correct_checks": correct_checks,
        "accuracy": round(accuracy, 4),
        "accuracy_pct": _pct(correct_checks, total_checks),
        "mismatches": mismatches,
    }


# ---------------------------------------------------------------------------
# 3. Fraud detection
# ---------------------------------------------------------------------------

# Categories that SHOULD have fraud signals
FRAUD_EXPECTED_CATEGORIES = {"duplicate", "suspicious"}
# Categories that should NOT have fraud signals (false positive check)
FRAUD_CLEAN_CATEGORIES = {"complete", "normal", "incomplete"}


def evaluate_fraud(apps: list[Application]) -> dict:
    true_positives = 0
    false_negatives = 0
    false_positives = 0
    true_negatives = 0

    per_app: list[dict] = []

    for app in apps:
        cat = app.synthetic_category or "unknown"
        has_signals = len(app.fraud_signals) > 0
        signal_types = [s.signal_type for s in app.fraud_signals]

        if cat in FRAUD_EXPECTED_CATEGORIES:
            if has_signals:
                true_positives += 1
                result = "TP"
            else:
                false_negatives += 1
                result = "FN"
        elif cat in FRAUD_CLEAN_CATEGORIES:
            if not has_signals:
                true_negatives += 1
                result = "TN"
            else:
                false_positives += 1
                result = "FP"
        else:
            result = "SKIP"

        per_app.append({
            "reference": app.reference_code,
            "category": cat,
            "has_signals": has_signals,
            "signal_types": signal_types,
            "result": result,
        })

    precision_denom = true_positives + false_positives
    recall_denom = true_positives + false_negatives

    precision = true_positives / precision_denom if precision_denom else 0.0
    recall = true_positives / recall_denom if recall_denom else 0.0
    f1_denom = precision + recall
    f1 = 2 * precision * recall / f1_denom if f1_denom else 0.0

    return {
        "true_positives": true_positives,
        "false_positives": false_positives,
        "true_negatives": true_negatives,
        "false_negatives": false_negatives,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1_score": round(f1, 4),
        "precision_pct": _pct(true_positives, precision_denom),
        "recall_pct": _pct(true_positives, recall_denom),
        "per_app": per_app,
    }


# ---------------------------------------------------------------------------
# 4. Scoring evaluation
# ---------------------------------------------------------------------------

APPROVE_CATEGORIES = APPROVE_WORTHY_CATEGORIES  # complete, normal
REJECT_CATEGORIES = REJECT_WORTHY_CATEGORIES    # incomplete, contradictory, duplicate, suspicious, low_quality


def evaluate_scoring(apps: list[Application]) -> dict:
    per_category: dict[str, list[float]] = defaultdict(list)
    ml_correct = 0
    ml_total = 0
    agreement_count = 0
    agreement_total = 0
    recommendation_counts: dict[str, int] = defaultdict(int)
    score_direction_correct = 0
    score_direction_total = 0

    for app in apps:
        cat = app.synthetic_category or "unknown"
        score = _latest_score(app)
        if not score:
            continue

        per_category[cat].append(score.total_score)
        recommendation_counts[score.ai_recommendation] += 1

        # Score direction: approve-worthy cats should score >= 70, reject-worthy < 70
        if cat in APPROVE_CATEGORIES:
            score_direction_total += 1
            if score.total_score >= 70:
                score_direction_correct += 1
        elif cat in REJECT_CATEGORIES:
            score_direction_total += 1
            if score.total_score < 70:
                score_direction_correct += 1

        # ML accuracy (compare ml prediction to ground truth label)
        if score.ml_approval_probability is not None:
            ml_pred = 1 if score.ml_approval_probability >= 0.5 else 0
            if cat in APPROVE_CATEGORIES:
                ml_total += 1
                if ml_pred == 1:
                    ml_correct += 1
            elif cat in REJECT_CATEGORIES:
                ml_total += 1
                if ml_pred == 0:
                    ml_correct += 1

        # Model agreement
        if score.model_agreement:
            agreement_total += 1
            if score.model_agreement == "AGREE":
                agreement_count += 1

    category_stats = {}
    for cat, scores in sorted(per_category.items()):
        category_stats[cat] = {
            "count": len(scores),
            "mean_score": round(sum(scores) / len(scores), 1),
            "min_score": round(min(scores), 1),
            "max_score": round(max(scores), 1),
        }

    return {
        "score_direction_accuracy": round(score_direction_correct / score_direction_total, 4)
            if score_direction_total else 0.0,
        "score_direction_accuracy_pct": _pct(score_direction_correct, score_direction_total),
        "ml_accuracy": round(ml_correct / ml_total, 4) if ml_total else None,
        "ml_accuracy_pct": _pct(ml_correct, ml_total) if ml_total else "n/a (model not trained)",
        "model_agreement_rate": round(agreement_count / agreement_total, 4) if agreement_total else None,
        "model_agreement_pct": _pct(agreement_count, agreement_total),
        "recommendation_distribution": dict(recommendation_counts),
        "per_category": category_stats,
    }


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

def _md_table(headers: list[str], rows: list[list[str]]) -> str:
    col_widths = [max(len(h), max((len(str(r[i])) for r in rows), default=0))
                  for i, h in enumerate(headers)]
    fmt = "| " + " | ".join(f"{{:<{w}}}" for w in col_widths) + " |"
    sep = "|-" + "-|-".join("-" * w for w in col_widths) + "-|"
    lines = [fmt.format(*headers), sep]
    for row in rows:
        lines.append(fmt.format(*[str(c) for c in row]))
    return "\n".join(lines)


def build_markdown_report(results: dict) -> str:
    ts = results["generated_at"]
    ext = results["extraction"]
    val = results["validation"]
    fraud = results["fraud"]
    scoring = results["scoring"]

    lines = [
        "# Evaluation Report",
        f"Generated: {ts}",
        f"Dataset: {ext['total_apps']} synthetic applications",
        "",
        "---",
        "",
        "## 1. Extraction Accuracy",
        "",
        f"**Overall accuracy: {ext['overall_accuracy_pct']}** "
        f"({ext['total_fields_recovered']}/{ext['total_fields_expected']} expected fields recovered)",
        "",
        _md_table(
            ["Category", "Apps", "Fields Expected", "Fields Recovered", "Accuracy"],
            [[c, v["apps"], v["expected"], v["recovered"], v["accuracy"]]
             for c, v in ext["per_category"].items()],
        ),
        "",
        "---",
        "",
        "## 2. Validation Accuracy",
        "",
        f"**Overall accuracy: {val['accuracy_pct']}** "
        f"({val['correct_checks']}/{val['total_checks']} checks matched expected outcome)",
        "",
    ]

    if val["mismatches"]:
        lines += [
            "**Mismatches:**",
            "",
            _md_table(
                ["Reference", "Category", "Check", "Expected", "Actual"],
                [[m["reference"], m["category"], m["check"], m["expected"], m["actual"]]
                 for m in val["mismatches"]],
            ),
            "",
        ]
    else:
        lines += ["All validation checks matched expected outcomes.", ""]

    lines += [
        "---",
        "",
        "## 3. Fraud Detection",
        "",
        f"**Precision: {fraud['precision_pct']}  |  Recall: {fraud['recall_pct']}  |  F1: {fraud['f1_score']}**",
        "",
        _md_table(
            ["Metric", "Value"],
            [
                ["True Positives (correctly flagged)", fraud["true_positives"]],
                ["False Positives (incorrectly flagged)", fraud["false_positives"]],
                ["True Negatives (correctly clean)", fraud["true_negatives"]],
                ["False Negatives (missed fraud)", fraud["false_negatives"]],
            ],
        ),
        "",
        _md_table(
            ["Reference", "Category", "Has Signals", "Signal Types", "Result"],
            [[p["reference"], p["category"], p["has_signals"],
              ", ".join(p["signal_types"]) or "—", p["result"]]
             for p in fraud["per_app"] if p["result"] != "SKIP"],
        ),
        "",
        "---",
        "",
        "## 4. Scoring & ML Evaluation",
        "",
        f"**Score direction accuracy: {scoring['score_direction_accuracy_pct']}** "
        "(approve-worthy categories score ≥70, reject-worthy <70)",
        "",
        f"**ML accuracy: {scoring['ml_accuracy_pct']}**",
        f"**Rule/ML agreement rate: {scoring['model_agreement_pct']}**",
        "",
        "**Score distribution per category:**",
        "",
        _md_table(
            ["Category", "Apps", "Mean Score", "Min", "Max"],
            [[c, v["count"], v["mean_score"], v["min_score"], v["max_score"]]
             for c, v in scoring["per_category"].items()],
        ),
        "",
        "**AI recommendation distribution:**",
        "",
        _md_table(
            ["Recommendation", "Count"],
            [[k, v] for k, v in sorted(scoring["recommendation_distribution"].items())],
        ),
        "",
        "---",
        "",
        "## 5. Summary",
        "",
        "| Dimension | Result |",
        "|---|---|",
        f"| Extraction accuracy | {ext['overall_accuracy_pct']} |",
        f"| Validation accuracy | {val['accuracy_pct']} |",
        f"| Fraud precision | {fraud['precision_pct']} |",
        f"| Fraud recall | {fraud['recall_pct']} |",
        f"| Fraud F1 | {fraud['f1_score']} |",
        f"| Score direction accuracy | {scoring['score_direction_accuracy_pct']} |",
        f"| ML accuracy (labeled set) | {scoring['ml_accuracy_pct']} |",
        f"| Rule/ML agreement rate | {scoring['model_agreement_pct']} |",
        "",
        "> AI scores and recommendations are advisory. Final determinations are made by human reviewers.",
        "",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def run_evaluation(output_dir: str = "docs") -> dict:
    init_db()
    db = SessionLocal()
    try:
        apps = db.query(Application).filter(
            Application.synthetic_category.isnot(None)
        ).all()

        if not apps:
            print("ERROR: No synthetic applications found in the database.")
            print("Seed the dataset first: python -m app.data.synthetic_generator")
            sys.exit(1)

        print(f"Evaluating {len(apps)} synthetic applications...")

        results = {
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
            "total_apps": len(apps),
            "extraction": evaluate_extraction(apps),
            "validation": evaluate_validation(apps),
            "fraud": evaluate_fraud(apps),
            "scoring": evaluate_scoring(apps),
        }

        # Write outputs
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)

        md_path = out / "evaluation_output.md"
        json_path = out / "evaluation_output.json"

        md_path.write_text(build_markdown_report(results), encoding="utf-8")
        json_path.write_text(json.dumps(results, indent=2), encoding="utf-8")

        # Print summary to stdout
        print("\n" + "=" * 60)
        print("EVALUATION RESULTS")
        print("=" * 60)
        print(f"  Extraction accuracy    : {results['extraction']['overall_accuracy_pct']}")
        print(f"  Validation accuracy    : {results['validation']['accuracy_pct']}")
        print(f"  Fraud precision        : {results['fraud']['precision_pct']}")
        print(f"  Fraud recall           : {results['fraud']['recall_pct']}")
        print(f"  Fraud F1               : {results['fraud']['f1_score']}")
        print(f"  Score direction acc.   : {results['scoring']['score_direction_accuracy_pct']}")
        print(f"  ML accuracy            : {results['scoring']['ml_accuracy_pct']}")
        print(f"  Rule/ML agreement      : {results['scoring']['model_agreement_pct']}")
        print("=" * 60)
        print(f"\nFull report written to:")
        print(f"  {md_path.resolve()}")
        print(f"  {json_path.resolve()}")

        if results["validation"]["mismatches"]:
            print(f"\nWARNING: {len(results['validation']['mismatches'])} validation mismatches found.")
        if results["fraud"]["false_positives"] > 0:
            print(f"WARNING: {results['fraud']['false_positives']} false positive fraud signal(s).")
        if results["fraud"]["false_negatives"] > 0:
            print(f"WARNING: {results['fraud']['false_negatives']} false negative fraud signal(s).")

        return results
    finally:
        db.close()


if __name__ == "__main__":
    # Write to project-level docs/ if running from backend/, otherwise local docs/
    import os
    script_dir = Path(__file__).resolve().parent
    project_root = script_dir.parent.parent.parent  # backend/app/evaluation -> project root
    docs_dir = project_root / "docs" if (project_root / "docs").exists() else Path("docs")
    run_evaluation(output_dir=str(docs_dir))
