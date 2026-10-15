"""Evaluation Benchmark Runner for Munshi Finance Assistant."""

import json
from decimal import Decimal
from typing import Dict, Any
from munshi.config import MunshiConfig
from munshi.agents.bookkeeper import BookkeeperAgent
from munshi.agents.reconciliation import ReconciliationAgent
from munshi.agents.auditor import AuditorAgent
from munshi.evaluation.synthetic_data import generate_synthetic_dataset


def run_benchmark() -> Dict[str, Any]:
    """Runs end-to-end evaluation and returns quantitative metrics."""
    dataset = generate_synthetic_dataset()
    config = MunshiConfig()

    bookkeeper = BookkeeperAgent(config)
    reconciler = ReconciliationAgent(config)
    auditor = AuditorAgent(config)

    # ----------------------------------------------------
    # 1. Categorization Benchmark
    # ----------------------------------------------------
    cat_cases = dataset["categorization"]
    cat_correct = 0
    cat_total = len(cat_cases)

    for case in cat_cases:
        res = bookkeeper.classify_transaction(case["desc"], case["counterparty"])
        if res["account_code"] == case["expected_code"]:
            cat_correct += 1

    cat_accuracy = (cat_correct / cat_total * 100) if cat_total > 0 else 0.0

    # ----------------------------------------------------
    # 2. Bank Reconciliation Benchmark
    # ----------------------------------------------------
    rec_data = dataset["reconciliation"]
    invoices = rec_data["invoices"]
    bank_lines = rec_data["bank_lines"]

    rec_result = reconciler.reconcile(bank_lines, invoices)
    
    # Calculate Precision and Recall against ground truth
    ground_truth_matches = {
        b["id"]: b["expected_match"] for b in bank_lines if b["expected_match"] is not None
    }
    
    tp_rec = 0
    fp_rec = 0
    for match in rec_result["matches"]:
        b_id = match["bank_line_id"]
        inv_id = match["invoice_id"]
        if ground_truth_matches.get(b_id) == inv_id:
            tp_rec += 1
        else:
            fp_rec += 1

    fn_rec = len(ground_truth_matches) - tp_rec
    rec_precision = (tp_rec / (tp_rec + fp_rec) * 100) if (tp_rec + fp_rec) > 0 else 0.0
    rec_recall = (tp_rec / len(ground_truth_matches) * 100) if len(ground_truth_matches) > 0 else 0.0
    unmatched_discrepancies_caught = len(rec_result["unmatched_bank_lines"])

    # ----------------------------------------------------
    # 3. Anomaly Detection Benchmark (Planted Errors)
    # ----------------------------------------------------
    anomaly_cases = dataset["anomalies"]
    ground_truth_anomalies = {a["id"] for a in anomaly_cases if a.get("is_planted_error")}
    
    audit_result = auditor.audit_batch(anomaly_cases)
    detected_ids = {issue["tx_id"] for issue in audit_result["flagged_issues"]}

    tp_audit = len(detected_ids.intersection(ground_truth_anomalies))
    fp_audit = len(detected_ids - ground_truth_anomalies)
    fn_audit = len(ground_truth_anomalies - detected_ids)

    audit_precision = (tp_audit / (tp_audit + fp_audit) * 100) if (tp_audit + fp_audit) > 0 else 0.0
    audit_recall = (tp_audit / len(ground_truth_anomalies) * 100) if len(ground_truth_anomalies) > 0 else 0.0
    audit_f1 = (
        (2 * audit_precision * audit_recall) / (audit_precision + audit_recall)
        if (audit_precision + audit_recall) > 0
        else 0.0
    )

    results = {
        "categorization": {
            "total_tested": cat_total,
            "correct": cat_correct,
            "accuracy_percent": round(cat_accuracy, 2),
        },
        "reconciliation": {
            "total_bank_lines": len(bank_lines),
            "ground_truth_matches": len(ground_truth_matches),
            "matched_by_agent": len(rec_result["matches"]),
            "match_rate_percent": rec_result["match_rate_percent"],
            "precision_percent": round(rec_precision, 2),
            "recall_percent": round(rec_recall, 2),
            "planted_unmatched_caught": unmatched_discrepancies_caught,
        },
        "anomaly_detection": {
            "total_transactions": len(anomaly_cases),
            "planted_errors_count": len(ground_truth_anomalies),
            "detected_count": len(detected_ids),
            "true_positives": tp_audit,
            "false_positives": fp_audit,
            "false_negatives": fn_audit,
            "precision_percent": round(audit_precision, 2),
            "recall_percent": round(audit_recall, 2),
            "f1_score": round(audit_f1, 2),
        },
    }

    return results


if __name__ == "__main__":
    res = run_benchmark()
    print(json.dumps(res, indent=2))
