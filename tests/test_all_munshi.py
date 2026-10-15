# tests/test_all_munshi.py
import pytest
from munshi.ledger.models import JournalEntry, JournalLine, BankStatementLine
from munshi.ledger.engine import LedgerEngine
from munshi.agents.gst import GSTAgent
from munshi.agents.bookkeeper import BookkeeperAgent
from munshi.agents.reconciliation import ReconciliationAgent
from munshi.agents.auditor import AuditorAgent
from munshi.mcp_server import MunshiMCPServer

def test_double_entry_and_hash_chain():
    engine = LedgerEngine()
    je = JournalEntry(
        entry_id="JE-1",
        date="2026-10-01",
        narration="Capital infusion",
        lines=[
            JournalLine("1010", "HDFC Bank Current A/c", debit=100000, credit=0),
            JournalLine("3000", "Owner Capital Account", debit=0, credit=100000),
        ],
    )
    engine.post_entry(je)
    tb = engine.get_trial_balance()
    assert tb["is_balanced"] is True
    assert tb["total_debit"] == 100000.0
    assert engine.audit_trail.verify_integrity() is True

def test_gstin_and_blocked_itc():
    gst = GSTAgent(home_state_code="27")
    v = gst.validate_gstin("29AAACI1681G1Z0")
    assert v["valid"] is True
    assert v["state_code"] == "29"

    inter = gst.compute_gst_split(10000, 18, counterparty_state_code="29")
    assert inter["igst"] == 1800.0 and inter["cgst"] == 0.0

    blocked = gst.compute_gst_split(5000, 5, counterparty_state_code="27", category="food")
    assert blocked["sec_17_5_blocked"] is True
    assert blocked["itc_eligible"] is False

def test_bookkeeper_and_hitl_gate():
    bk = BookkeeperAgent(home_state_code="27", hitl_threshold=50000.0)
    je_rent = bk.parse_and_create_entry("Paid office rent ₹30,000 via bank")
    assert je_rent.is_balanced is True
    assert je_rent.tds == 3000.0
    assert je_rent.status == "POSTED"

    je_high = bk.parse_and_create_entry("Purchased MacBook laptop for ₹1,20,000")
    assert je_high.status == "PENDING_HITL"

def test_reconciliation_and_auditor():
    bk = BookkeeperAgent()
    je = bk.parse_and_create_entry("Paid cash ₹15,000 for office repairs")
    auditor = AuditorAgent()
    flags = auditor.audit_entries([je])
    assert any(f.rule == "SEC_40A_3_CASH_LIMIT" for f in flags)

def test_mcp_server_tools():
    mcp = MunshiMCPServer()
    tools = mcp.list_tools()
    assert len(tools) >= 6
    res = mcp.call_tool("post_transaction", {"text": "Sold SaaS subscription in Bengaluru for ₹50,000"})
    assert res["total_debit"] == 59000.0
