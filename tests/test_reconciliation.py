"""Unit tests for Bank Reconciliation Agent."""

from munshi.agents.reconciliation import ReconciliationAgent


def test_reconciliation_exact_match():
    reconciler = ReconciliationAgent()
    bank_lines = [
        {"id": "B1", "amount": 11800.0, "date": "2026-10-01", "description": "ACH DEP Acme Corp UTR001"},
    ]
    invoices = [
        {"id": "I1", "invoice_no": "INV-101", "amount": 11800.0, "date": "2026-10-01", "reference_id": "UTR001"},
    ]
    res = reconciler.reconcile(bank_lines, invoices)
    assert res["matched_count"] == 1
    assert res["unmatched_bank_count"] == 0
    assert res["match_rate_percent"] == 100.0


def test_reconciliation_unmatched_bank_line():
    reconciler = ReconciliationAgent()
    bank_lines = [
        {"id": "B1", "amount": 25000.0, "date": "2026-10-01", "description": "ATM CASH WDL UNKNOWN"},
    ]
    invoices = [
        {"id": "I1", "invoice_no": "INV-101", "amount": 5000.0, "date": "2026-10-01", "reference_id": "UTR001"},
    ]
    res = reconciler.reconcile(bank_lines, invoices)
    assert res["matched_count"] == 0
    assert res["unmatched_bank_count"] == 1
    assert res["match_rate_percent"] == 0.0
