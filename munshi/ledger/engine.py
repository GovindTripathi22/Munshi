"""Double-entry ledger engine enforcing strict accounting invariants."""

import sqlite3
from decimal import Decimal
from typing import Dict, List, Optional, Tuple, Any
from copy import deepcopy

from munshi.ledger.models import (
    Account,
    AccountType,
    NormalBalance,
    JournalEntryItem,
    LedgerTransaction,
    TransactionStatus,
    DEFAULT_CHART_OF_ACCOUNTS,
)
from munshi.ledger.audit_trail import AuditTrail


class LedgerError(Exception):
    """Base exception for ledger operations."""
    pass


class LedgerImbalanceError(LedgerError):
    """Raised when total debits do not equal total credits."""
    pass


class AccountNotFoundError(LedgerError):
    """Raised when an invalid account code is referenced."""
    pass


class DoubleEntryLedger:
    """Core double-entry accounting engine."""

    def __init__(self, db_path: str = ":memory:"):
        self.db_path = db_path
        self.accounts: Dict[str, Account] = deepcopy(DEFAULT_CHART_OF_ACCOUNTS)
        self.transactions: Dict[str, LedgerTransaction] = {}
        self.audit_trail = AuditTrail()
        self._init_sqlite()

    def _init_sqlite(self) -> None:
        """Initialize SQLite tables for persistent storage."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS accounts (
                    code TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    type TEXT NOT NULL,
                    normal_balance TEXT NOT NULL,
                    balance TEXT NOT NULL
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS transactions (
                    id TEXT PRIMARY KEY,
                    date TEXT NOT NULL,
                    reference_id TEXT,
                    description TEXT NOT NULL,
                    status TEXT NOT NULL,
                    total_debits TEXT NOT NULL,
                    total_credits TEXT NOT NULL,
                    requires_approval INTEGER NOT NULL,
                    approved INTEGER NOT NULL,
                    approved_by TEXT,
                    created_at TEXT NOT NULL
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS journal_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    transaction_id TEXT NOT NULL,
                    account_code TEXT NOT NULL,
                    debit TEXT NOT NULL,
                    credit TEXT NOT NULL,
                    narration TEXT,
                    FOREIGN KEY (transaction_id) REFERENCES transactions (id)
                )
            """)
            conn.commit()

    def get_account(self, code: str) -> Account:
        if code not in self.accounts:
            raise AccountNotFoundError(f"Account with code '{code}' does not exist in Chart of Accounts.")
        return self.accounts[code]

    def add_account(self, account: Account) -> None:
        self.accounts[account.code] = account

    def post_transaction(
        self,
        transaction: LedgerTransaction,
        actor: str = "agent:bookkeeper",
        force_approval: bool = False,
    ) -> LedgerTransaction:
        """
        Posts a journal transaction to the ledger.
        
        Strict Invariants Enforced:
        1. Debits == Credits (zero-sum balance)
        2. All accounts exist in the Chart of Accounts
        3. Single-line item consistency (no line with both debit and credit)
        """
        # Invariant 1: Validate line-level rules
        for item in transaction.items:
            item.validate_single_sided()
            if item.account_code not in self.accounts:
                raise AccountNotFoundError(f"Unknown account code: {item.account_code}")

        # Invariant 2: Mathematical Balance (Debits == Credits)
        total_dr = transaction.total_debits()
        total_cr = transaction.total_credits()
        if total_dr != total_cr:
            raise LedgerImbalanceError(
                f"Ledger Imbalance: Total Debits ({total_dr}) != Total Credits ({total_cr}). "
                f"Difference: {total_dr - total_cr}."
            )

        # Check if transaction requires human approval
        if transaction.requires_approval and not transaction.approved and not force_approval:
            transaction.status = TransactionStatus.PENDING_APPROVAL
            self.transactions[transaction.id] = transaction
            self.audit_trail.log(
                event_type="TRANSACTION_PENDING_APPROVAL",
                actor=actor,
                transaction_id=transaction.id,
                details={
                    "total_amount": str(total_dr),
                    "description": transaction.description,
                    "reason": "Requires human approval",
                },
            )
            return transaction

        # Post entries to account balances
        for item in transaction.items:
            acc = self.accounts[item.account_code]
            acc.update_balance(debit=item.debit, credit=item.credit)

        transaction.status = TransactionStatus.POSTED
        self.transactions[transaction.id] = transaction

        # Log to immutable audit trail
        self.audit_trail.log(
            event_type="TRANSACTION_POSTED",
            actor=actor,
            transaction_id=transaction.id,
            details={
                "total_dr": str(total_dr),
                "total_cr": str(total_cr),
                "description": transaction.description,
                "item_count": len(transaction.items),
            },
        )
        return transaction

    def approve_transaction(self, transaction_id: str, approver: str = "user:manager") -> LedgerTransaction:
        """Approves a pending transaction and commits it to the ledger balances."""
        if transaction_id not in self.transactions:
            raise LedgerError(f"Transaction {transaction_id} not found.")

        tx = self.transactions[transaction_id]
        if tx.status != TransactionStatus.PENDING_APPROVAL:
            raise LedgerError(f"Transaction {transaction_id} is in status {tx.status}, cannot approve.")

        tx.approved = True
        tx.approved_by = approver
        return self.post_transaction(tx, actor=approver, force_approval=True)

    def reject_transaction(
        self, transaction_id: str, approver: str = "user:manager", reason: str = ""
    ) -> LedgerTransaction:
        """Rejects a pending transaction."""
        if transaction_id not in self.transactions:
            raise LedgerError(f"Transaction {transaction_id} not found.")

        tx = self.transactions[transaction_id]
        tx.status = TransactionStatus.REJECTED
        self.audit_trail.log(
            event_type="TRANSACTION_REJECTED",
            actor=approver,
            transaction_id=transaction_id,
            details={"reason": reason},
        )
        return tx

    def get_trial_balance(self) -> Dict[str, Any]:
        """
        Generates the Trial Balance.
        Verifies that sum(Debits) == sum(Credits) across all active accounts.
        """
        total_debits = Decimal("0.00")
        total_credits = Decimal("0.00")
        rows: List[Dict[str, Any]] = []

        for code, acc in sorted(self.accounts.items()):
            if acc.balance == Decimal("0.00"):
                continue

            dr_amt = Decimal("0.00")
            cr_amt = Decimal("0.00")

            if acc.normal_balance == NormalBalance.DEBIT:
                if acc.balance >= 0:
                    dr_amt = acc.balance
                else:
                    cr_amt = abs(acc.balance)
            else:
                if acc.balance >= 0:
                    cr_amt = acc.balance
                else:
                    dr_amt = abs(acc.balance)

            total_debits += dr_amt
            total_credits += cr_amt

            rows.append({
                "code": acc.code,
                "name": acc.name,
                "type": acc.type.value,
                "debit": str(dr_amt),
                "credit": str(cr_amt),
            })

        is_balanced = total_debits == total_credits

        return {
            "rows": rows,
            "total_debits": str(total_debits),
            "total_credits": str(total_credits),
            "is_balanced": is_balanced,
            "difference": str(total_debits - total_credits),
        }

    def get_profit_and_loss(self) -> Dict[str, Any]:
        """Computes Total Revenue, Total Expenses, and Net Profit/Loss."""
        revenue_items = []
        expense_items = []
        total_revenue = Decimal("0.00")
        total_expense = Decimal("0.00")

        for code, acc in self.accounts.items():
            if acc.type == AccountType.REVENUE:
                bal = acc.balance
                total_revenue += bal
                revenue_items.append({"code": code, "name": acc.name, "amount": str(bal)})
            elif acc.type == AccountType.EXPENSE:
                bal = acc.balance
                total_expense += bal
                expense_items.append({"code": code, "name": acc.name, "amount": str(bal)})

        net_profit = total_revenue - total_expense

        return {
            "revenues": revenue_items,
            "total_revenue": str(total_revenue),
            "expenses": expense_items,
            "total_expenses": str(total_expense),
            "net_profit": str(net_profit),
            "is_profitable": net_profit >= 0,
        }

    def get_balance_sheet(self) -> Dict[str, Any]:
        """
        Computes Balance Sheet: Assets, Liabilities, and Equity.
        Validates accounting equation: Assets = Liabilities + Equity + Current Period Earnings.
        """
        assets = []
        liabilities = []
        equity = []
        total_assets = Decimal("0.00")
        total_liabilities = Decimal("0.00")
        total_equity = Decimal("0.00")

        for code, acc in self.accounts.items():
            if acc.type == AccountType.ASSET:
                total_assets += acc.balance
                assets.append({"code": code, "name": acc.name, "balance": str(acc.balance)})
            elif acc.type == AccountType.LIABILITY:
                total_liabilities += acc.balance
                liabilities.append({"code": code, "name": acc.name, "balance": str(acc.balance)})
            elif acc.type == AccountType.EQUITY:
                total_equity += acc.balance
                equity.append({"code": code, "name": acc.name, "balance": str(acc.balance)})

        # Factor in Net Profit from Revenue - Expense into Equity
        pnl = self.get_profit_and_loss()
        net_profit = Decimal(pnl["net_profit"])
        retained_with_profit = total_equity + net_profit

        is_balanced = total_assets == (total_liabilities + retained_with_profit)

        return {
            "assets": assets,
            "total_assets": str(total_assets),
            "liabilities": liabilities,
            "total_liabilities": str(total_liabilities),
            "equity": equity,
            "total_equity": str(total_equity),
            "net_profit_current_period": str(net_profit),
            "total_liabilities_and_equity": str(total_liabilities + retained_with_profit),
            "is_balanced": is_balanced,
        }
