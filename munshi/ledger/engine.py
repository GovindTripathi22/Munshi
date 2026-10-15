# munshi/ledger/engine.py
from typing import Dict, List, Any, Optional
from .models import Account, JournalEntry, JournalLine, round_Money
from .audit_trail import AuditTrail

DEFAULT_CHART: List[Account] = [
    Account("1000", "Cash in Hand", "ASSET"),
    Account("1010", "HDFC Bank Current A/c", "ASSET"),
    Account("1100", "Accounts Receivable", "ASSET"),
    Account("1210", "Input CGST Receivable", "ASSET"),
    Account("1220", "Input SGST Receivable", "ASSET"),
    Account("1230", "Input IGST Receivable", "ASSET"),
    Account("1500", "Computer & Office Equipment", "ASSET"),
    Account("2000", "Accounts Payable", "LIABILITY"),
    Account("2110", "Output CGST Payable", "LIABILITY"),
    Account("2120", "Output SGST Payable", "LIABILITY"),
    Account("2130", "Output IGST Payable", "LIABILITY"),
    Account("2200", "TDS Payable", "LIABILITY"),
    Account("3000", "Owner Capital Account", "EQUITY"),
    Account("4000", "Sales & Product Revenue", "REVENUE"),
    Account("4100", "SaaS & Consulting Revenue", "REVENUE"),
    Account("5000", "Cost of Goods Sold", "EXPENSE"),
    Account("5100", "Office Rent Expense", "EXPENSE"),
    Account("5200", "Cloud & Software Subscriptions", "EXPENSE"),
    Account("5300", "Professional & Legal Fees", "EXPENSE"),
    Account("5400", "Staff Welfare & Blocked ITC Expense", "EXPENSE"),
    Account("5500", "Repairs & Maintenance", "EXPENSE"),
    Account("5600", "Bank Charges", "EXPENSE"),
]

class LedgerEngine:
    def __init__(self):
        self.accounts: Dict[str, Account] = {a.code: a for a in DEFAULT_CHART}
        self.entries: List[JournalEntry] = []
        self.audit_trail = AuditTrail()

    def register_account(self, account: Account) -> None:
        self.accounts[account.code] = account

    def post_entry(self, entry: JournalEntry) -> JournalEntry:
        entry.validate()
        for line in entry.lines:
            if line.account_code not in self.accounts:
                self.accounts[line.account_code] = Account(line.account_code, line.account_name, "EXPENSE")
        self.entries.append(entry)
        self.audit_trail.append(
            action=f"ENTRY_{entry.status}",
            entry_id=entry.entry_id,
            payload={
                "date": entry.date,
                "narration": entry.narration,
                "total_debit": entry.total_debit,
                "total_credit": entry.total_credit,
                "status": entry.status,
            },
        )
        return entry

    def approve_hitl_entry(self, entry_id: str) -> Optional[JournalEntry]:
        for entry in self.entries:
            if entry.entry_id == entry_id:
                entry.status = "POSTED"
                self.audit_trail.append("HITL_APPROVED", entry_id, {"status": "POSTED"})
                return entry
        return None

    def reject_hitl_entry(self, entry_id: str, reason: str = "Rejected by reviewer") -> Optional[JournalEntry]:
        for entry in self.entries:
            if entry.entry_id == entry_id:
                entry.status = "REJECTED"
                self.audit_trail.append("HITL_REJECTED", entry_id, {"status": "REJECTED", "reason": reason})
                return entry
        return None

    def posted_entries(self) -> List[JournalEntry]:
        return [e for e in self.entries if e.status == "POSTED"]

    def get_account_balance(self, account_code: str) -> float:
        acct = self.accounts.get(account_code)
        if not acct:
            return 0.0
        dr = sum(l.debit for e in self.posted_entries() for l in e.lines if l.account_code == account_code)
        cr = sum(l.credit for e in self.posted_entries() for l in e.lines if l.account_code == account_code)
        return round_Money(dr - cr if acct.normal_side == "DEBIT" else cr - dr)

    def get_trial_balance(self) -> Dict[str, Any]:
        rows = []
        total_dr = 0.0
        total_cr = 0.0
        for code, acct in sorted(self.accounts.items()):
            dr = round_Money(sum(l.debit for e in self.posted_entries() for l in e.lines if l.account_code == code))
            cr = round_Money(sum(l.credit for e in self.posted_entries() for l in e.lines if l.account_code == code))
            if dr > 0 or cr > 0:
                rows.append({"code": code, "name": acct.name, "type": acct.account_type, "debit": dr, "credit": cr})
                total_dr = round_Money(total_dr + dr)
                total_cr = round_Money(total_cr + cr)
        return {
            "rows": rows,
            "total_debit": total_dr,
            "total_credit": total_cr,
            "is_balanced": abs(total_dr - total_cr) < 0.01,
        }

    def get_profit_and_loss(self) -> Dict[str, Any]:
        revenues = {a.code: self.get_account_balance(a.code) for a in self.accounts.values() if a.account_type == "REVENUE"}
        expenses = {a.code: self.get_account_balance(a.code) for a in self.accounts.values() if a.account_type == "EXPENSE"}
        total_rev = round_Money(sum(revenues.values()))
        total_exp = round_Money(sum(expenses.values()))
        net_profit = round_Money(total_rev - total_exp)
        return {
            "total_revenue": total_rev,
            "total_expense": total_exp,
            "net_profit": net_profit,
            "revenues": {k: v for k, v in revenues.items() if v != 0},
            "expenses": {k: v for k, v in expenses.items() if v != 0},
        }

    def get_balance_sheet(self) -> Dict[str, Any]:
        pnl = self.get_profit_and_loss()
        assets = {a.code: self.get_account_balance(a.code) for a in self.accounts.values() if a.account_type == "ASSET"}
        liabilities = {a.code: self.get_account_balance(a.code) for a in self.accounts.values() if a.account_type == "LIABILITY"}
        equity = {a.code: self.get_account_balance(a.code) for a in self.accounts.values() if a.account_type == "EQUITY"}
        total_assets = round_Money(sum(assets.values()))
        total_liabilities = round_Money(sum(liabilities.values()))
        total_equity = round_Money(sum(equity.values()) + pnl["net_profit"])
        return {
            "total_assets": total_assets,
            "total_liabilities": total_liabilities,
            "total_equity": total_equity,
            "retained_earnings": pnl["net_profit"],
            "is_balanced": abs(total_assets - (total_liabilities + total_equity)) < 0.01,
        }

DoubleEntryLedger = LedgerEngine

