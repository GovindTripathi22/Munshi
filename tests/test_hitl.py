"""Tests for Human-in-the-Loop (HITL) approval gates."""

from decimal import Decimal
from munshi.config import MunshiConfig
from munshi.ledger.engine import DoubleEntryLedger
from munshi.agents.bookkeeper import BookkeeperAgent
from munshi.ledger.models import TransactionStatus


def test_high_value_transaction_triggers_hitl():
    config = MunshiConfig(high_value_approval_threshold=Decimal("50000.00"))
    bookkeeper = BookkeeperAgent(config)
    ledger = DoubleEntryLedger()

    # Create transaction of ₹100,000 (exceeds ₹50,000 threshold)
    tx = bookkeeper.create_journal_transaction(
        tx_id="TX-HIGH-01",
        date="2026-10-15",
        description="Enterprise Server Purchase",
        amount=Decimal("100000.00"),
    )
    assert tx.requires_approval is True

    # Posting without approval sets status to PENDING_APPROVAL
    posted = ledger.post_transaction(tx)
    assert posted.status == TransactionStatus.PENDING_APPROVAL
    assert "TX-HIGH-01" in ledger.transactions

    # Approve transaction
    approved_tx = ledger.approve_transaction("TX-HIGH-01", approver="cfo@company.com")
    assert approved_tx.status == TransactionStatus.POSTED
    assert approved_tx.approved is True
    assert approved_tx.approved_by == "cfo@company.com"


def test_rejection_of_pending_transaction():
    ledger = DoubleEntryLedger()
    bookkeeper = BookkeeperAgent()
    tx = bookkeeper.create_journal_transaction(
        tx_id="TX-REJ-01",
        date="2026-10-15",
        description="Unverified vendor invoice",
        amount=Decimal("80000.00"),
    )
    ledger.post_transaction(tx)
    rejected = ledger.reject_transaction("TX-REJ-01", approver="cfo@company.com", reason="Unverified vendor")
    assert rejected.status == TransactionStatus.REJECTED
