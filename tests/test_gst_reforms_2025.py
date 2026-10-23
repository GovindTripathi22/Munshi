# tests/test_gst_reforms_2025.py
import pytest
from munshi.agents.gst import GSTAgent, GST_REFORM_DATE
from munshi.agents.bookkeeper import BookkeeperAgent
from munshi.ledger.engine import LedgerEngine

def test_gst_rate_validation_pre_and_post_reform():
    agent = GSTAgent(home_state_code="27")

    # 1. Historical invoice (before 22-Sep-2025): 12% and 28% are allowed
    valid_pre_12, _ = agent.validate_gst_rate(12.0, "2025-08-15")
    valid_pre_28, _ = agent.validate_gst_rate(28.0, "2025-08-15")
    assert valid_pre_12 is True
    assert valid_pre_28 is True

    # 2. Current invoice (after 22-Sep-2025): 12% and 28% are rejected
    valid_post_12, err_12 = agent.validate_gst_rate(12.0, "2026-10-16")
    valid_post_28, err_28 = agent.validate_gst_rate(28.0, "2026-10-16")
    assert valid_post_12 is False
    assert "sunset effective 22-Sep-2025" in err_12
    assert valid_post_28 is False
    assert "sunset effective 22-Sep-2025" in err_28

    # 3. Post-reform standard slabs (0%, 5%, 18%) remain valid
    for rate in (0.0, 5.0, 18.0):
        v, _ = agent.validate_gst_rate(rate, "2026-10-16")
        assert v is True

def test_bookkeeper_rejects_discontinued_rate_post_reform():
    engine = LedgerEngine(db_path=":memory:")
    bookkeeper = BookkeeperAgent(home_state_code="27")

    with pytest.raises(ValueError) as excinfo:
        bookkeeper.parse_and_create_entry("Purchased office supplies for INR 5000 with 12% GST", date="2026-10-16")
    assert "discontinued on 2025-09-22" in str(excinfo.value)

def test_madhya_pradesh_inter_state_igst_calculation():
    agent = GSTAgent(home_state_code="27")  # Maharashtra
    # Supplier in Madhya Pradesh (State code 23)
    split = agent.compute_gst_split(
        taxable_amount=10000.0,
        gst_rate=18.0,
        counterparty_state_code="23",
        category="general",
        invoice_date="2026-10-16",
    )
    assert split["supply_type"] == "INTER_STATE"
    assert split["igst"] == 1800.0
    assert split["cgst"] == 0.0
    assert split["sgst"] == 0.0
