# tests/test_bookkeeper.py
from munshi.agents.bookkeeper import BookkeeperAgent

def test_bookkeeper_parsing_and_tds():
    bk = BookkeeperAgent(home_state_code="27", hitl_threshold=50000.0)
    je_rent = bk.parse_and_create_entry("Paid office rent ₹30,000 via bank")
    assert je_rent.is_balanced is True
    assert je_rent.tds == 3000.0
    assert je_rent.status == "POSTED"

    je_lakh = bk.parse_and_create_entry("Purchased MacBook laptop for 1.2 lakh")
    assert je_lakh.is_balanced is True
    assert je_lakh.taxable_value == 120000.0
    assert je_lakh.status == "PENDING_HITL"
