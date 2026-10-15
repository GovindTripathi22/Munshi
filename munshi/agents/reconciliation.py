# munshi/agents/reconciliation.py
from datetime import datetime
from typing import List, Dict, Any
from ..ledger.models import JournalEntry, JournalLine, BankStatementLine, round_Money

class ReconciliationAgent:
    def __init__(self, date_tolerance_days: int = 3):
        self.date_tolerance_days = date_tolerance_days

    @staticmethod
    def _days_between(d1: str, d2: str) -> int:
        try:
            dt1 = datetime.strptime(d1[:10], "%Y-%m-%d")
            dt2 = datetime.strptime(d2[:10], "%Y-%m-%d")
            return abs((dt1 - dt2).days)
        except Exception:
            return 0

    def reconcile(self, entries: List[JournalEntry], bank_lines: List[BankStatementLine]) -> Dict[str, Any]:
        matched = []
        unmatched_bank = []
        used_entries = set()

        for bline in bank_lines:
            bank_amt = round_Money(bline.credit if bline.credit > 0 else bline.debit)
            best_entry = None
            best_conf = 0.0

            for entry in entries:
                if entry.entry_id in used_entries:
                    continue
                # Find bank line in journal entry
                bank_je_lines = [l for l in entry.lines if l.account_code == "1010"]
                if not bank_je_lines:
                    continue
                je_amt = round_Money(bank_je_lines[0].debit if bank_je_lines[0].debit > 0 else bank_je_lines[0].credit)

                if abs(bank_amt - je_amt) < 0.01:
                    if bline.utr and entry.utr and bline.utr.upper() == entry.utr.upper():
                        best_entry = entry
                        best_conf = 1.0
                        break
                    days_diff = self._days_between(bline.date, entry.date)
                    if days_diff <= self.date_tolerance_days:
                        best_entry = entry
                        best_conf = round(0.95 - days_diff * 0.03, 2)

            if best_entry:
                used_entries.add(best_entry.entry_id)
                bline.matched_entry_id = best_entry.entry_id
                bline.confidence = best_conf
                matched.append({"bank_line_id": bline.line_id, "entry_id": best_entry.entry_id, "amount": bank_amt, "confidence": best_conf})
            else:
                unmatched_bank.append(bline)

        return {
            "matched_count": len(matched),
            "unmatched_bank_count": len(unmatched_bank),
            "matches": matched,
            "unmatched_bank_lines": unmatched_bank,
        }

    def create_adjustment_entry_for_bank_charge(self, bline: BankStatementLine) -> JournalEntry:
        amt = round_Money(bline.debit or bline.credit)
        return JournalEntry(
            entry_id=f"JE-ADJ-{bline.line_id}",
            date=bline.date,
            narration=f"Auto-Reconciled Bank Charge: {bline.description}",
            utr=bline.utr,
            payment_mode="BANK",
            status="POSTED",
            lines=[
                JournalLine("5600", "Bank Charges", debit=amt, credit=0.0),
                JournalLine("1010", "HDFC Bank Current A/c", debit=0.0, credit=amt),
            ],
        )
