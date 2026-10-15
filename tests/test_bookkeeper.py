"""Unit tests for Bookkeeper Agent."""

from decimal import Decimal
from munshi.agents.bookkeeper import BookkeeperAgent


def test_bookkeeper_classification():
    agent = BookkeeperAgent()
    
    c1 = agent.classify_transaction("AWS Cloud server hosting monthly bill")
    assert c1["account_code"] == "5200"

    c2 = agent.classify_transaction("WeWork office space monthly lease")
    assert c2["account_code"] == "5100"

    c3 = agent.classify_transaction("Legal advocate retainer fee")
    assert c3["account_code"] == "5300"


def test_bookkeeper_journal_creation_is_balanced():
    agent = BookkeeperAgent()
    tx = agent.create_journal_transaction(
        tx_id="TX-AWS-01",
        date="2026-10-15",
        description="AWS Hosting",
        amount=Decimal("10000.00"),
        is_sale=False,
    )
    assert tx.is_balanced() is True
    assert tx.total_debits() == tx.total_credits()
    assert tx.total_debits() == Decimal("11800.00")  # 10k + 18% GST


def test_bookkeeper_sale_journal_is_balanced():
    agent = BookkeeperAgent()
    tx = agent.create_journal_transaction(
        tx_id="TX-SALE-01",
        date="2026-10-15",
        description="Product sales to distributor",
        amount=Decimal("50000.00"),
        is_sale=True,
    )
    assert tx.is_balanced() is True
    assert tx.total_debits() == tx.total_credits()
    assert tx.total_debits() == Decimal("59000.00")
