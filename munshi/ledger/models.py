"""Double-entry ledger data models and Chart of Accounts."""

from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import List, Optional, Dict
from pydantic import BaseModel, Field


class AccountType(str, Enum):
    ASSET = "ASSET"
    LIABILITY = "LIABILITY"
    EQUITY = "EQUITY"
    REVENUE = "REVENUE"
    EXPENSE = "EXPENSE"


class NormalBalance(str, Enum):
    DEBIT = "DEBIT"
    CREDIT = "CREDIT"


class TransactionStatus(str, Enum):
    DRAFT = "DRAFT"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    POSTED = "POSTED"


class Account(BaseModel):
    """Account in the general ledger."""
    code: str
    name: str
    type: AccountType
    normal_balance: NormalBalance
    balance: Decimal = Field(default=Decimal("0.00"))
    description: str = ""

    def update_balance(self, debit: Decimal, credit: Decimal) -> None:
        """Update account balance based on normal balance convention."""
        if self.normal_balance == NormalBalance.DEBIT:
            self.balance += (debit - credit)
        else:
            self.balance += (credit - debit)


class JournalEntryItem(BaseModel):
    """Single debit or credit line in a journal entry."""
    account_code: str
    debit: Decimal = Field(default=Decimal("0.00"))
    credit: Decimal = Field(default=Decimal("0.00"))
    narration: str = ""

    def validate_single_sided(self) -> None:
        """Validate that line has debit XOR credit, not both and not neither."""
        if self.debit > 0 and self.credit > 0:
            raise ValueError(f"Line cannot have both debit ({self.debit}) and credit ({self.credit}).")
        if self.debit == 0 and self.credit == 0:
            raise ValueError("Line must specify either a non-zero debit or credit.")


class LedgerTransaction(BaseModel):
    """A balanced double-entry transaction containing multiple journal entry items."""
    id: str
    date: str
    reference_id: str = ""
    description: str
    items: List[JournalEntryItem]
    status: TransactionStatus = TransactionStatus.DRAFT
    requires_approval: bool = False
    approved: bool = False
    approved_by: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: Dict[str, str] = Field(default_factory=dict)

    def total_debits(self) -> Decimal:
        return sum((item.debit for item in self.items), Decimal("0.00"))

    def total_credits(self) -> Decimal:
        return sum((item.credit for item in self.items), Decimal("0.00"))

    def is_balanced(self) -> bool:
        """Enforces the fundamental double-entry invariant: Debits == Credits."""
        return self.total_debits() == self.total_credits()


# Standard Chart of Accounts (COA) for Indian Businesses
DEFAULT_CHART_OF_ACCOUNTS: Dict[str, Account] = {
    # Assets (1000 - 1999)
    "1000": Account(code="1000", name="Cash on Hand", type=AccountType.ASSET, normal_balance=NormalBalance.DEBIT),
    "1010": Account(code="1010", name="Bank - Current Account", type=AccountType.ASSET, normal_balance=NormalBalance.DEBIT),
    "1200": Account(code="1200", name="Accounts Receivable", type=AccountType.ASSET, normal_balance=NormalBalance.DEBIT),
    "1300": Account(code="1300", name="Input CGST", type=AccountType.ASSET, normal_balance=NormalBalance.DEBIT),
    "1310": Account(code="1310", name="Input SGST", type=AccountType.ASSET, normal_balance=NormalBalance.DEBIT),
    "1320": Account(code="1320", name="Input IGST", type=AccountType.ASSET, normal_balance=NormalBalance.DEBIT),
    
    # Liabilities (2000 - 2999)
    "2000": Account(code="2000", name="Accounts Payable", type=AccountType.LIABILITY, normal_balance=NormalBalance.CREDIT),
    "2100": Account(code="2100", name="Output CGST", type=AccountType.LIABILITY, normal_balance=NormalBalance.CREDIT),
    "2110": Account(code="2110", name="Output SGST", type=AccountType.LIABILITY, normal_balance=NormalBalance.CREDIT),
    "2120": Account(code="2120", name="Output IGST", type=AccountType.LIABILITY, normal_balance=NormalBalance.CREDIT),
    "2200": Account(code="2200", name="GST Payable Clearing", type=AccountType.LIABILITY, normal_balance=NormalBalance.CREDIT),
    
    # Equity (3000 - 3999)
    "3000": Account(code="3000", name="Owner's Capital", type=AccountType.EQUITY, normal_balance=NormalBalance.CREDIT),
    "3100": Account(code="3100", name="Retained Earnings", type=AccountType.EQUITY, normal_balance=NormalBalance.CREDIT),
    
    # Revenue (4000 - 4999)
    "4000": Account(code="4000", name="Product Sales Revenue", type=AccountType.REVENUE, normal_balance=NormalBalance.CREDIT),
    "4100": Account(code="4100", name="Professional Services Revenue", type=AccountType.REVENUE, normal_balance=NormalBalance.CREDIT),
    "4200": Account(code="4200", name="Other Operating Income", type=AccountType.REVENUE, normal_balance=NormalBalance.CREDIT),
    
    # Expenses (5000 - 5999)
    "5000": Account(code="5000", name="Cost of Goods Sold (COGS)", type=AccountType.EXPENSE, normal_balance=NormalBalance.DEBIT),
    "5100": Account(code="5100", name="Office Rent Expense", type=AccountType.EXPENSE, normal_balance=NormalBalance.DEBIT),
    "5200": Account(code="5200", name="Software & Cloud Subscriptions", type=AccountType.EXPENSE, normal_balance=NormalBalance.DEBIT),
    "5300": Account(code="5300", name="Legal & Professional Fees", type=AccountType.EXPENSE, normal_balance=NormalBalance.DEBIT),
    "5400": Account(code="5400", name="Bank Charges & Fees", type=AccountType.EXPENSE, normal_balance=NormalBalance.DEBIT),
    "5500": Account(code="5500", name="Office Supplies & Utilities", type=AccountType.EXPENSE, normal_balance=NormalBalance.DEBIT),
    "5600": Account(code="5600", name="Travel & Conveyance", type=AccountType.EXPENSE, normal_balance=NormalBalance.DEBIT),
}
