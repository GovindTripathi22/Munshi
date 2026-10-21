# tests/test_cli.py
import json
import pytest
from click.testing import CliRunner
from munshi.cli import cli
from munshi.agents.bookkeeper import BookkeeperAgent
from munshi.agents.reconciliation import ReconciliationAgent
from munshi.agents.auditor import AuditorAgent
from munshi.evaluation.benchmark import run_synthetic_dataset_benchmark, run_munshi_benchmark
from munshi.mcp_server import MunshiMCPServer

def test_cli_help():
    runner = CliRunner()
    res = runner.invoke(cli, ["--help"])
    assert res.exit_code == 0
    assert "Munshi" in res.output
    assert "post" in res.output
    assert "benchmark" in res.output
    assert "report" in res.output

def test_cli_post_transaction():
    runner = CliRunner()
    res = runner.invoke(cli, ["post", "Sold SaaS subscription to Bengaluru client for ₹50,000"])
    assert res.exit_code == 0
    assert "VOUCHER" in res.output
    assert "Double-Entry General Ledger Voucher" in res.output
    assert "BALANCED" in res.output

def test_cli_post_hitl_high_value():
    runner = CliRunner()
    res = runner.invoke(cli, ["post", "Purchased MacBook laptop for ₹1,50,000"])
    assert res.exit_code == 0
    assert "PAUSED AT HITL GATE" in res.output

def test_cli_benchmark_json():
    runner = CliRunner()
    res = runner.invoke(cli, ["benchmark", "--json-out"])
    assert res.exit_code == 0
    data = json.loads(res.output)
    assert data["double_entry_balance_accuracy"] == 100.0
    assert data["hitl_governance_accuracy"] == 100.0
    assert data["audit_chain_intact"] is True
    assert data["categorization"]["accuracy_percent"] == 100.0
    assert data["reconciliation"]["precision_percent"] == 100.0
    assert data["anomaly_detection"]["f1_score"] == 100.0

def test_cli_benchmark_rich_table():
    runner = CliRunner()
    res = runner.invoke(cli, ["benchmark"])
    assert res.exit_code == 0
    assert "BENCHMARK EVALUATION" in res.output
    assert "PASSED" in res.output

def test_cli_reports():
    runner = CliRunner()
    for rtype in ["trial_balance", "pnl", "balance_sheet", "gst"]:
        res = runner.invoke(cli, ["report", "--type", rtype])
        assert res.exit_code == 0

def test_cli_audit():
    runner = CliRunner()
    res = runner.invoke(cli, ["audit"])
    assert res.exit_code == 0
    assert "FORENSIC" in res.output
    assert "SHA-256 HASH CHAIN: INTACT" in res.output

def test_cli_reconcile():
    runner = CliRunner()
    res = runner.invoke(cli, ["reconcile"])
    assert res.exit_code == 0
    assert "RECONCILIATION" in res.output
    assert "100.0%" in res.output

def test_bookkeeper_categorization_suite():
    bk = BookkeeperAgent()
    assert bk.categorize_transaction("AWS Cloud Hosting monthly infrastructure", "Amazon Web Services") == "5200"
    assert bk.categorize_transaction("Office rent payment for October", "WeWork Management") == "5100"
    assert bk.categorize_transaction("Legal consultation retainer for trademark filing", "Singhania Advocates") == "5300"
    assert bk.categorize_transaction("Annual Bank Account Maintenance fee debit", "HDFC Bank") == "5400"
    assert bk.categorize_transaction("Printer paper and stationery for back office", "Staples Office Supplies") == "5500"
    assert bk.categorize_transaction("Uber ride to client meeting in BKC", "Uber India") == "5600"
    assert bk.categorize_transaction("Product sale invoice delivered to retail buyer", "Retail Mart") == "4000"
    assert bk.categorize_transaction("Enterprise consulting invoice for Q3", "Acme Corp") == "4100"

def test_mcp_extended_tools():
    mcp = MunshiMCPServer()
    # Test tool aliases
    tb = mcp.call_tool("get_trial_balance", {})
    assert "total_debit" in tb

    pnl = mcp.call_tool("get_profit_and_loss", {})
    assert "net_profit" in pnl

    gst = mcp.call_tool("get_gst_summary", {})
    assert "net_gst_payable" in gst

    audit = mcp.call_tool("run_financial_audit", {})
    assert audit["valid"] is True

def test_cli_post_query_non_entry():
    runner = CliRunner()
    res = runner.invoke(cli, ["post", "Show audit report"])
    assert res.exit_code == 0
    assert "QUERY RESULT: AUDIT" in res.output
    assert "CA Statutory Executive Report" in res.output

def test_cli_post_revenue_tax_characterization():
    runner = CliRunner()
    res = runner.invoke(cli, ["post", "Sold SaaS subscription to Bengaluru client for ₹1,50,000"])
    assert res.exit_code == 0
    assert "Output Tax Liability (Payable to Govt)" in res.output

