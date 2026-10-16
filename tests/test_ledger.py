# tests/test_ledger.py
import pytest
from munshi.ledger.models import JournalEntry, JournalLine
from munshi.ledger.engine import LedgerEngine

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

def test_unbalanced_entry_rejected():
    with pytest.raises(ValueError):
        je = JournalEntry(
            entry_id="JE-BAD",
            date="2026-10-01",
            narration="Unbalanced",
            lines=[
                JournalLine("1010", "HDFC Bank Current A/c", debit=5000, credit=0),
                JournalLine("3000", "Owner Capital Account", debit=0, credit=4000),
            ],
        )
        je.validate()
