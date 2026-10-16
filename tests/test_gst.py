# tests/test_gst.py
from munshi.agents.gst import GSTAgent

def test_gstin_and_blocked_itc():
    gst = GSTAgent(home_state_code="27")
    v = gst.validate_gstin("29AAACI1681G1Z0")
    assert v["valid"] is True
    assert v["state_code"] == "29"

    inter = gst.compute_gst_split(10000, 18, counterparty_state_code="29")
    assert inter["igst"] == 1800.0 and inter["cgst"] == 0.0

    intra = gst.compute_gst_split(10000, 18, counterparty_state_code="27")
    assert intra["cgst"] == 900.0 and intra["sgst"] == 900.0 and intra["igst"] == 0.0

    blocked = gst.compute_gst_split(5000, 5, counterparty_state_code="27", category="food")
    assert blocked["sec_17_5_blocked"] is True
    assert blocked["itc_eligible"] is False
