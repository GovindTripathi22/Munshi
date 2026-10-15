"""Unit and integration tests for the Double-Entry Ledger engine and Audit Trail."""

import pytest
from decimal import Decimal
from munshi.ledger.engine import DoubleEntryLedger, LedgerImbalanceError, AccountNotFoundError
from munshi.ledger.models import JournalEntryItem, LedgerTransaction, TransactionStatus
from munshi.ledger.audit_trail import AuditTrail


def test_ledger_initialization():
    ledger = DoubleEntryLedger()
    assert "1010" in ledger.accounts
    assert ledger.accounts["1010"].name == "Bank - Current Account"
    assert ledger.audit_trail.verify_integrity() is True


def test_balanced_transaction_posts_successfully():
    ledger = DoubleEntryLedger()
    tx = LedgerTransaction(
        id="TXN-001",
        date="2026-10-15",
        description="Office Supplies",
        items=[
            JournalEntryItem(account_code="5500", debit=Decimal("5000.00"), credit=Decimal("0.00")),
            JournalEntryItem(account_code="1010", debit=Decimal("0.00"), credit=Decimal("5000.00")),
        ],
    )
    posted = ledger.post_transaction(tx)
    assert posted.status == TransactionStatus.POSTED
    assert ledger.get_account("5500").balance == Decimal("5000.00")
    assert ledger.get_account("1010").balance == Decimal("-5000.00")
    assert ledger.audit_trail.verify_integrity() is True


def test_imbalanced_transaction_raises_error():
    ledger = DoubleEntryLedger()
    tx = LedgerTransaction(
        id="TXN-ERR",
        date="2026-10-15",
        description="Imbalanced Entry",
        items=[
            JournalEntryItem(account_code="5500", debit=Decimal("5000.00"), credit=Decimal("0.00")),
            JournalEntryItem(account_code="1010", debit=Decimal("0.00"), credit=Decimal("4000.00")),
        ],
    )
    with pytest.raises(LedgerImbalanceError) as exc_info:
        ledger.post_transaction(tx)
    assert "Ledger Imbalance" in str(exc_info.value)


def test_unknown_account_raises_error():
    ledger = DoubleEntryLedger()
    tx = LedgerTransaction(
        id="TXN-INV-ACC",
        date="2026-10-15",
        description="Invalid Account Code",
        items=[
            JournalEntryItem(account_code="9999", debit=Decimal("100.00"), credit=Decimal("0.00")),
            JournalEntryItem(account_code="1010", debit=Decimal("0.00"), credit=Decimal("100.00")),
        ],
    )
    with pytest.raises(AccountNotFoundError):
        ledger.post_transaction(tx)


def test_audit_trail_tamper_detection():
    trail = AuditTrail()
    trail.log(event_type="LOGIN", actor="admin", details={"ip": "127.0.0.1"})
    trail.log(event_type="PAYMENT", actor="bookkeeper", details={"amt": 1000})
    assert trail.verify_integrity() is True

    # Tamper with an event
    trail._events[0].details["ip"] = "192.168.1.1"
    assert trail.verify_integrity() is False


def test_trial_balance_and_balance_sheet():
    ledger = DoubleEntryLedger()
    # Post capital injection: Debit Bank (1010) 100k, Credit Equity (3000) 100k
    tx1 = LedgerTransaction(
        id="TX-CAP",
        date="2026-10-01",
        description="Owner Capital",
        items=[
            JournalEntryItem(account_code="1010", debit=Decimal("100000.00"), credit=Decimal("0.00")),
            JournalEntryItem(account_code="3000", debit=Decimal("0.00"), credit=Decimal("100000.00")),
        ],
    )
    ledger.post_transaction(tx1)

    tb = ledger.get_trial_balance()
    assert tb["is_balanced"] is True
    assert Decimal(tb["total_debits"]) == Decimal(tb["total_credits"])

    bs = ledger.get_balance_sheet()
    assert bs["is_balanced"] is True
