# tests/test_reconciliation.py
from munshi.ledger.models import JournalEntry, JournalLine, BankStatementLine
from munshi.agents.reconciliation import ReconciliationAgent

def test_bank_reconciliation():
    recon = ReconciliationAgent()
    je = JournalEntry(
        entry_id="JE-101",
        date="2026-10-01",
        narration="Capital",
        utr="UTR998877",
        lines=[
            JournalLine("1010", "HDFC Bank Current A/c", debit=50000, credit=0),
            JournalLine("3000", "Owner Capital Account", debit=0, credit=50000),
        ],
    )
    bline = BankStatementLine("BNK-1", "2026-10-01", "NEFT CR", credit=50000, utr="UTR998877")
    res = recon.reconcile([je], [bline])
    assert res["matched_count"] == 1
    assert res["matches"][0]["confidence"] == 1.0
