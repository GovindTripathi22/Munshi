# tests/test_auditor.py
from munshi.agents.bookkeeper import BookkeeperAgent
from munshi.agents.auditor import AuditorAgent

def test_sec_40a3_cash_violation():
    bk = BookkeeperAgent()
    je = bk.parse_and_create_entry("Paid cash ₹15,000 for office repairs")
    auditor = AuditorAgent()
    flags = auditor.audit_entries([je])
    assert any(f.rule == "SEC_40A_3_CASH_LIMIT" for f in flags)
