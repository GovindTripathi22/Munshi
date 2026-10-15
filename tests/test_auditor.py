"""Unit tests for Auditor Agent."""

from munshi.agents.auditor import AuditorAgent


def test_auditor_detects_duplicate_invoice():
    auditor = AuditorAgent()
    transactions = [
        {"id": "T1", "invoice_no": "INV-1001", "gst_rate": 0.18},
        {"id": "T2", "invoice_no": "INV-1001", "gst_rate": 0.18},  # Duplicate
    ]
    res = auditor.audit_batch(transactions)
    assert res["anomalies_detected"] >= 1
    assert res["duplicate_invoices_found"] == 1
    assert any(i["type"] == "DUPLICATE_INVOICE" for i in res["flagged_issues"])


def test_auditor_detects_illegal_gst_rate():
    auditor = AuditorAgent()
    transactions = [
        {"id": "T1", "invoice_no": "INV-1002", "gst_rate": 0.15},  # 15% is invalid in India
    ]
    res = auditor.audit_batch(transactions)
    assert res["tax_errors_found"] == 1
    assert any(i["type"] == "INVALID_GST_RATE" for i in res["flagged_issues"])
