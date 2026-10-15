"""Tests for Model Context Protocol (MCP) server endpoints."""

import json
from munshi.mcp_server import (
    record_transaction,
    compute_gst,
    reconcile_statement,
    run_financial_audit,
    get_trial_balance,
    get_profit_and_loss,
    get_gst_summary,
)


def test_mcp_record_transaction():
    res_str = record_transaction(
        description="Office Supplies",
        amount=5000.0,
        is_sale=False,
    )
    res = json.loads(res_str)
    assert res["is_balanced"] is True
    assert res["status"] == "POSTED"


def test_mcp_compute_gst():
    res_str = compute_gst(taxable_value=10000.0, rate_percent=18.0)
    res = json.loads(res_str)
    assert res["total_tax"] == "1800.00"
    assert res["cgst"] == "900.00"
    assert res["sgst"] == "900.00"


def test_mcp_reconcile_statement():
    bank_lines = [{"id": "B1", "amount": 1000.0, "date": "2026-10-01", "description": "INV-1"}]
    invoices = [{"id": "I1", "invoice_no": "INV-1", "amount": 1000.0, "date": "2026-10-01"}]
    res_str = reconcile_statement(json.dumps(bank_lines), json.dumps(invoices))
    res = json.loads(res_str)
    assert res["matched_count"] == 1


def test_mcp_audit():
    txs = [{"id": "T1", "invoice_no": "INV-01"}, {"id": "T2", "invoice_no": "INV-01"}]
    res_str = run_financial_audit(json.dumps(txs))
    res = json.loads(res_str)
    assert res["duplicate_invoices_found"] == 1


def test_mcp_reports():
    tb = json.loads(get_trial_balance())
    assert "is_balanced" in tb

    pnl = json.loads(get_profit_and_loss())
    assert "net_profit" in pnl

    gst = json.loads(get_gst_summary())
    assert "output_liability" in gst
