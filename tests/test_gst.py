"""Unit tests for Indian GST Computation Agent."""

import pytest
from decimal import Decimal
from munshi.config import MunshiConfig
from munshi.agents.gst import GSTComputationAgent


def test_intra_state_gst_computation():
    config = MunshiConfig(home_state_code="27")  # Maharashtra
    agent = GSTComputationAgent(config)

    # Intra-state: Vendor is also from Maharashtra (GSTIN starts with 27)
    res = agent.compute_gst(
        taxable_value=Decimal("10000.00"),
        rate=Decimal("0.18"),
        counterparty_gstin="27ABCDE1234F1Z5",
    )
    assert res["is_inter_state"] is False
    assert res["cgst"] == "900.00"
    assert res["sgst"] == "900.00"
    assert res["igst"] == "0.00"
    assert res["total_tax"] == "1800.00"
    assert res["total_invoice_amount"] == "11800.00"


def test_inter_state_gst_computation():
    config = MunshiConfig(home_state_code="27")  # Maharashtra
    agent = GSTComputationAgent(config)

    # Inter-state: Vendor is from Karnataka (GSTIN starts with 29)
    res = agent.compute_gst(
        taxable_value=Decimal("10000.00"),
        rate=Decimal("0.18"),
        counterparty_gstin="29ABCDE1234F1Z5",
    )
    assert res["is_inter_state"] is True
    assert res["cgst"] == "0.00"
    assert res["sgst"] == "0.00"
    assert res["igst"] == "1800.00"
    assert res["total_tax"] == "1800.00"
    assert res["total_invoice_amount"] == "11800.00"


def test_invalid_gst_rate_raises_error():
    agent = GSTComputationAgent()
    with pytest.raises(ValueError) as exc_info:
        agent.compute_gst(taxable_value=Decimal("1000.00"), rate=Decimal("0.15"))
    assert "Invalid GST rate" in str(exc_info.value)
