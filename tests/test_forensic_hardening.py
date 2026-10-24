# tests/test_forensic_hardening.py
"""
Forensic hardening test suite targeting audit trail immutability,
statutory tax rules, tamper detection, and input parsing resilience.
"""
import pytest
import json
import sqlite3
from munshi.ledger.models import JournalEntry, JournalLine
from munshi.ledger.engine import LedgerEngine
from munshi.agents.bookkeeper import BookkeeperAgent
from munshi.agents.gst import GSTAgent
from munshi.agents.auditor import AuditorAgent
from munshi.graph import MunshiOrchestrator
from munshi.mcp_server import MunshiMCPServer
from fastapi.testclient import TestClient
from munshi.api import app

def test_audit_records_multi_session_no_overwrite(tmp_path):
    db_file = str(tmp_path / "multi_session.db")
    eng1 = LedgerEngine(db_path=db_file)
    eng2 = LedgerEngine(db_path=db_file)
    bk = BookkeeperAgent(hitl_threshold=50000.0)

    # Session 1: post small entry
    e1 = bk.parse_and_create_entry("Paid office supplies for INR 5000", entry_id="JE-001")
    eng1.post_entry(e1)

    # Session 2: post high-value entry (held for HITL)
    e2 = bk.parse_and_create_entry("Purchased server hardware for INR 90000", entry_id="JE-002")
    eng2.post_entry(e2)

    # Session 1: approves e2
    approved = eng1.approve_hitl_entry("JE-002", approver="cfo_govind")
    assert approved is not None
    assert approved.status == "POSTED"

    # Verify audit records in SQLite
    conn = sqlite3.connect(db_file)
    cur = conn.cursor()
    cur.execute("SELECT seq, action, entry_id, prev_hash, record_hash FROM audit_records ORDER BY seq ASC;")
    rows = cur.fetchall()
    conn.close()

    # Must have 3 distinct audit records: record 2 was NOT overwritten!
    assert len(rows) == 3
    assert rows[0][0] == 1 and rows[0][1] == "POST_TRANSACTION" and rows[0][2] == "JE-001"
    assert rows[1][0] == 2 and rows[1][1] == "HOLD_PENDING_HITL" and rows[1][2] == "JE-002"
    assert rows[2][0] == 3 and rows[2][1] == "APPROVE_HITL_ENTRY" and rows[2][2] == "JE-002"

    # Integrity verification must pass 100%
    verify_res = eng1.verify_ledger_integrity()
    assert verify_res["verified"] is True
    assert verify_res["audit_chain_valid"] is True

def test_reposting_entry_id_forbidden(tmp_path):
    db_file = str(tmp_path / "immutable.db")
    engine = LedgerEngine(db_path=db_file)
    bk = BookkeeperAgent()

    e1 = bk.parse_and_create_entry("Purchased office chairs for INR 1000", entry_id="JE-FIXED")
    engine.post_entry(e1)

    # Attempt to re-post same ID with 9000 must fail with Ledger Immutability Violation
    e2 = bk.parse_and_create_entry("Purchased luxury sofa for INR 9000", entry_id="JE-FIXED")
    with pytest.raises(ValueError) as exc:
        engine.post_entry(e2)
    assert "Ledger Immutability Violation" in str(exc.value)

def test_tamper_detection_moving_amount_between_accounts(tmp_path):
    db_file = str(tmp_path / "tamper_accounts.db")
    engine = LedgerEngine(db_path=db_file)
    bk = BookkeeperAgent()

    entry = bk.parse_and_create_entry("Paid office rent INR 40000 via bank", entry_id="JE-RENT")
    engine.post_entry(entry)
    assert engine.verify_ledger_integrity()["verified"] is True

    # Tamper directly in SQLite: change account code from 5100 (Rent) to 3000 (Owner Drawings/Capital)
    conn = sqlite3.connect(db_file)
    cur = conn.cursor()
    cur.execute("SELECT lines_json FROM journal_entries WHERE entry_id = 'JE-RENT';")
    lines = json.loads(cur.fetchone()[0])
    lines[0]["account_code"] = "3000"
    lines[0]["account_name"] = "Owner Capital Account"
    cur.execute("UPDATE journal_entries SET lines_json = ? WHERE entry_id = 'JE-RENT';", (json.dumps(lines),))
    conn.commit()
    conn.close()

    # Re-verify: must detect the altered account line
    check = engine.verify_ledger_integrity()
    assert check["verified"] is False
    assert any("Tamper detected on 'JE-RENT': Account line modified" in err for err in check["errors"])

def test_tamper_detection_editing_approved_entry(tmp_path):
    db_file = str(tmp_path / "tamper_approved.db")
    engine = LedgerEngine(db_path=db_file)
    bk = BookkeeperAgent(hitl_threshold=50000.0)

    # Post high value entry and approve it
    entry = bk.parse_and_create_entry("Purchased specialized tooling for INR 90000 via bank", entry_id="JE-TOOL")
    engine.post_entry(entry)
    engine.approve_hitl_entry("JE-TOOL")
    assert engine.verify_ledger_integrity()["verified"] is True

    # Tamper directly in SQLite: alter debit amount from 90,000 to 10
    conn = sqlite3.connect(db_file)
    cur = conn.cursor()
    cur.execute("SELECT lines_json FROM journal_entries WHERE entry_id = 'JE-TOOL';")
    lines = json.loads(cur.fetchone()[0])
    lines[0]["debit"] = 10.0
    lines[1]["credit"] = 10.0
    cur.execute("UPDATE journal_entries SET lines_json = ? WHERE entry_id = 'JE-TOOL';", (json.dumps(lines),))
    conn.commit()
    conn.close()

    # Re-verify: must detect that approved entry was tampered
    check = engine.verify_ledger_integrity()
    assert check["verified"] is False
    assert any("Tamper detected on entry 'JE-TOOL'" in err for err in check["errors"])

def test_amount_parsing_edge_cases():
    bk = BookkeeperAgent(hitl_threshold=50000.0)

    # 1. 2-digit amount 'Paid 99 for tea' -> must be 99, not 10,000!
    je_tea = bk.parse_and_create_entry("Paid 99 for tea")
    assert je_tea.taxable_value == 99.0

    # 2. Structured amount parameter overrides description numbers
    je_cloud = bk.parse_and_create_entry("Order 12345 cloud hosting", amount=500.0)
    assert je_cloud.taxable_value == 500.0

    # 3. Text with no monetary amount raises ValueError (no invented 10,000)
    with pytest.raises(ValueError) as exc:
        bk.parse_and_create_entry("hello world test narration")
    assert "Could not determine monetary transaction amount" in str(exc.value)

    # 4. '50% advance' does not trigger 0% GST
    je_adv = bk.parse_and_create_entry("50% advance payment for INR 100000 software development")
    assert je_adv.cgst + je_adv.sgst + je_adv.igst == 18000.0  # 18% GST

    # 5. 'Flight to sales conference' is expense, not revenue
    je_flight = bk.parse_and_create_entry("Flight to sales conference for INR 8500 via bank")
    assert any(l.account_code == "5600" for l in je_flight.lines)
    assert not any(l.account_code in ("4000", "4100") for l in je_flight.lines)

    # 6. 'Capital equipment' has 18% GST and is ASSET, not equity
    je_equip = bk.parse_and_create_entry("Capital equipment purchase of laptop for INR 75000 via bank")
    assert any(l.account_code == "1500" for l in je_equip.lines)
    assert je_equip.cgst + je_equip.sgst + je_equip.igst == 13500.0  # 18% of 75k

    # 7. 'Cashback' is processed via bank, not Cash in Hand
    je_cashback = bk.parse_and_create_entry("Cashback reward received of INR 500")
    assert je_cashback.payment_mode == "BANK"
    assert any(l.account_code == "1010" for l in je_cashback.lines)

    # 8. Rent of exactly 20,000 has 0 TDS
    je_rent_20k = bk.parse_and_create_entry("Paid office rent INR 20000 via bank")
    assert je_rent_20k.tds == 0.0

def test_statutory_gst_rate_40_percent_and_non_iso_dates():
    agent = GSTAgent(home_state_code="27")

    # 40% demerit/sin goods rate is valid
    v_40, err_40 = agent.validate_gst_rate(40.0, "2026-10-16")
    assert v_40 is True and err_40 is None

    # 12% is rejected on effective reform date 22-Sep-2025
    v_eff, err_eff = agent.validate_gst_rate(12.0, "2025-09-22")
    assert v_eff is False
    assert "sunset effective 22-Sep-2025" in err_eff

    # Non-ISO date (DD/MM/YYYY) is normalized and properly rejected post-reform
    v_non_iso, err_non_iso = agent.validate_gst_rate(12.0, "16/10/2026")
    assert v_non_iso is False
    assert "sunset effective 22-Sep-2025" in err_non_iso

    # Non-ISO date (DD-MM-YYYY) before reform is accepted
    v_hist, _ = agent.validate_gst_rate(12.0, "15-08-2025")
    assert v_hist is True

def test_api_rejection_updates_db_and_audit(tmp_path):
    client = TestClient(app)
    # 1. Post a high value workflow transaction
    res = client.post("/v1/workflows/run", json={"prompt": "Purchased industrial servers for INR 95000 via bank"})
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "AWAITING_HITL_APPROVAL"
    entry_id = data["entry"]["entry_id"]

    # 2. Reject through API
    rej_res = client.post(f"/v1/workflows/{data['thread_id']}/hitl", json={
        "approved": False,
        "entry_id": entry_id,
        "reviewer_notes": "Capital expenditure denied by board"
    })
    assert rej_res.status_code == 200
    rej_data = rej_res.json()
    assert rej_data["status"] == "REJECTED"

    # 3. Verify that trial balance debit does not include rejected transaction
    tb_res = client.get("/v1/ledger/trial-balance")
    assert tb_res.status_code == 200

    # 4. Attempting to approve an already rejected transaction must return 400
    re_app = client.post(f"/v1/workflows/{data['thread_id']}/hitl", json={"approved": True, "entry_id": entry_id})
    assert re_app.status_code == 400
