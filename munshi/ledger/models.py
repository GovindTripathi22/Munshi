# munshi/ledger/models.py
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional, Literal
from decimal import Decimal, ROUND_HALF_UP

AccountType = Literal["ASSET", "LIABILITY", "EQUITY", "REVENUE", "EXPENSE"]

def round_Money(val: float | Decimal) -> float:
    return float(Decimal(str(val)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))

@dataclass
class Account:
    code: str
    name: str
    account_type: AccountType

    @property
    def normal_side(self) -> Literal["DEBIT", "CREDIT"]:
        return "DEBIT" if self.account_type in ("ASSET", "EXPENSE") else "CREDIT"

@dataclass
class JournalLine:
    account_code: str
    account_name: str
    debit: float = 0.0
    credit: float = 0.0

    def __post_init__(self):
        self.debit = round_Money(self.debit)
        self.credit = round_Money(self.credit)
        if self.debit < 0 or self.credit < 0:
            raise ValueError("Debit and credit amounts must be non-negative.")
        if self.debit > 0 and self.credit > 0:
            raise ValueError("A single journal line cannot have both debit and credit > 0.")

@dataclass
class JournalEntry:
    entry_id: str
    date: str
    narration: str
    lines: List[JournalLine]
    party: str = "General Counterparty"
    party_gstin: Optional[str] = None
    utr: Optional[str] = None
    payment_mode: Literal["BANK", "CASH", "CREDIT"] = "BANK"
    status: Literal["POSTED", "PENDING_HITL", "REJECTED"] = "POSTED"
    taxable_value: float = 0.0
    cgst: float = 0.0
    sgst: float = 0.0
    igst: float = 0.0
    tds: float = 0.0
    itc_eligible: bool = True

    @property
    def total_debit(self) -> float:
        return round_Money(sum(l.debit for l in self.lines))

    @property
    def total_credit(self) -> float:
        return round_Money(sum(l.credit for l in self.lines))

    @property
    def is_balanced(self) -> bool:
        return abs(self.total_debit - self.total_credit) < 0.01 and self.total_debit > 0

    def validate(self) -> bool:
        if len(self.lines) < 2:
            raise ValueError("Double-entry journal entry requires at least 2 lines.")
        if not self.is_balanced:
            raise ValueError(f"Unbalanced JournalEntry {self.entry_id}: Dr={self.total_debit} != Cr={self.total_credit}")
        return True

@dataclass
class BankStatementLine:
    line_id: str
    date: str
    description: str
    debit: float = 0.0
    credit: float = 0.0
    utr: Optional[str] = None
    matched_entry_id: Optional[str] = None
    confidence: float = 0.0

@dataclass
class AuditFlag:
    flag_id: str
    entry_id: str
    severity: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    rule: str
    detail: str
    requires_hitl: bool = False
