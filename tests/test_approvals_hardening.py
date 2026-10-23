# tests/test_approvals_hardening.py
import pytest
from munshi.ledger.engine import LedgerEngine
from munshi.agents.bookkeeper import BookkeeperAgent
from munshi.mcp_server import MunshiMCPServer

def test_pending_hitl_entry_persists_in_sqlite(tmp_path):
    db_file = tmp_path / "approval_persist.db"
    engine1 = LedgerEngine(db_path=str(db_file))
    bookkeeper = BookkeeperAgent(hitl_threshold=50000.0)

    # Post high value entry (> 50,000)
    entry = bookkeeper.parse_and_create_entry("Purchased plant machinery for INR 80000 with 18% GST", date="2026-10-16")
    assert entry.status == "PENDING_HITL"
    engine1.post_entry(entry)

    # Restart engine from SQLite database file
    engine2 = LedgerEngine(db_path=str(db_file))
    loaded_entry = next((e for e in engine2.entries if e.entry_id == entry.entry_id), None)
    assert loaded_entry is not None
    assert loaded_entry.status == "PENDING_HITL"

    # Human approves entry
    approved = engine2.approve_hitl_entry(entry.entry_id)
    assert approved is not None
    assert approved.status == "POSTED"

    # Re-approving already posted entry must be refused
    re_approved = engine2.approve_hitl_entry(entry.entry_id)
    assert re_approved is None

    # Rejecting already posted entry must be refused
    re_rejected = engine2.reject_hitl_entry(entry.entry_id)
    assert re_rejected is None

def test_hitl_threshold_strictly_exceeds_50k():
    bookkeeper = BookkeeperAgent(hitl_threshold=50000.0)
    # Total gross exactly 50,000 does NOT require approval
    # e.g., base 42372.88 + 18% tax = 50,000.0
    entry_exact = bookkeeper.parse_and_create_entry("Purchased software for INR 42372.88 with 18% GST", date="2026-10-16")
    assert entry_exact.total_debit == 50000.0
    assert entry_exact.status == "POSTED"

    # Total gross exceeding 50,000 DOES require approval
    entry_exceeds = bookkeeper.parse_and_create_entry("Purchased software for INR 42373.00 with 18% GST", date="2026-10-16")
    assert entry_exceeds.total_debit > 50000.0
    assert entry_exceeds.status == "PENDING_HITL"

def test_mcp_cannot_approve_hitl():
    mcp = MunshiMCPServer()
    tools = [t["name"] for t in mcp.list_tools()]
    assert "approve_hitl_entry" not in tools

    with pytest.raises(PermissionError) as excinfo:
        mcp.call_tool("approve_hitl_entry", {"entry_id": "JE-101"})
    assert "Access Denied" in str(excinfo.value)
