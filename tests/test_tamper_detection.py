# tests/test_tamper_detection.py
import pytest
import sqlite3
from munshi.ledger.engine import LedgerEngine
from munshi.ledger.models import JournalEntry, JournalLine
from fastapi.testclient import TestClient
from munshi.api import app

def test_tamper_detection_direct_db_edit(tmp_path):
    db_file = tmp_path / "tamper_test.db"
    engine = LedgerEngine(db_path=str(db_file))

    entry = JournalEntry(
        entry_id="JE-TAMP-01",
        date="2026-10-16",
        narration="Authentic transaction",
        lines=[
            JournalLine("1010", "HDFC Bank Current A/c", debit=5000.0, credit=0.0),
            JournalLine("4000", "Sales & Product Revenue", debit=0.0, credit=5000.0),
        ],
    )
    engine.post_entry(entry)

    # Initial verification: clean
    assert engine.verify_ledger_integrity()["verified"] is True

    # Malicious direct modification directly in SQLite database (altering amount to 9999.0)
    conn = sqlite3.connect(str(db_file))
    cursor = conn.cursor()
    tampered_lines = [
        {"account_code": "1010", "account_name": "HDFC Bank Current A/c", "debit": 9999.0, "credit": 0.0},
        {"account_code": "4000", "account_name": "Sales & Product Revenue", "debit": 0.0, "credit": 9999.0},
    ]
    cursor.execute("UPDATE journal_entries SET lines_json = ? WHERE entry_id = ?;", (str(tampered_lines).replace("'", '"'), "JE-TAMP-01"))
    conn.commit()
    conn.close()

    # Restart engine from the tampered database
    tampered_engine = LedgerEngine(db_path=str(db_file))
    integrity = tampered_engine.verify_ledger_integrity()

    # Verification must catch the database tamper!
    assert integrity["verified"] is False
    assert any("Tamper detected" in err for err in integrity["errors"])

def test_health_endpoint_fails_on_tamper(tmp_path, monkeypatch):
    client = TestClient(app)
    # Healthy initially
    resp = client.get("/health")
    assert resp.status_code == 200

    # Simulate tampered engine
    from munshi.api import _SESSIONS
    orch = _SESSIONS.get("health")
    if orch:
        # Corrupt audit trail hash
        orch.ledger.audit_trail.records.append(
            orch.ledger.audit_trail.append("BAD_RECORD", "JE-BAD", {"bad": True})
        )
        orch.ledger.audit_trail.records[-1].record_hash = "0" * 64

        bad_resp = client.get("/health")
        assert bad_resp.status_code == 500
        assert "Tamper detected" in bad_resp.json()["detail"]["error"]
