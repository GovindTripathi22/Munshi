# munshi/agents/reconciliation.py
from datetime import datetime
from typing import List, Dict, Any
from ..ledger.models import JournalEntry, JournalLine, BankStatementLine, round_money

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
            bank_amt = round_money(bline.credit if bline.credit > 0 else bline.debit)
            best_entry = None
            best_conf = 0.0

            for entry in entries:
                if entry.entry_id in used_entries:
                    continue
                bank_je_lines = [l for l in entry.lines if l.account_code == "1010"]
                if not bank_je_lines:
                    continue
                je_amt = round_money(bank_je_lines[0].debit if bank_je_lines[0].debit > 0 else bank_je_lines[0].credit)

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
        amt = round_money(bline.debit or bline.credit)
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

    def reconcile_invoices(self, invoices: List[Dict[str, Any]], bank_lines: List[Dict[str, Any]]) -> Dict[str, Any]:
        matched = []
        unmatched_bank = []
        used_invoices = set()
        correct_matches = 0
        planted_caught = 0
        ground_truth_matches = sum(1 for b in bank_lines if b.get("expected_match"))

        for bline in bank_lines:
            desc = bline.get("description", "")
            amt = float(bline.get("amount", 0.0))
            best_inv = None

            for inv in invoices:
                if inv.get("id") in used_invoices:
                    continue
                inv_amt = float(inv.get("amount", 0.0))
                inv_ref = inv.get("reference_id", "")
                if inv_ref and inv_ref.upper() in desc.upper():
                    best_inv = inv
                    break
                if abs(inv_amt - amt) < 0.01:
                    days_diff = self._days_between(bline.get("date", ""), inv.get("date", ""))
                    if days_diff <= self.date_tolerance_days:
                        best_inv = inv

            if best_inv:
                used_invoices.add(best_inv["id"])
                is_correct = bline.get("expected_match") == best_inv["id"]
                if is_correct:
                    correct_matches += 1
                matched.append({
                    "bank_line_id": bline.get("id"),
                    "invoice_id": best_inv.get("id"),
                    "amount": amt,
                    "confidence": 1.0 if (best_inv.get("reference_id") and best_inv.get("reference_id") in desc) else 0.95,
                    "correct": is_correct,
                })
            else:
                unmatched_bank.append(bline)
                if bline.get("is_anomaly") or bline.get("expected_match") is None:
                    planted_caught += 1

        total_bank = len(bank_lines)
        matched_count = len(matched)
        precision = round((correct_matches / matched_count * 100.0) if matched_count else 0.0, 2)
        recall = round((correct_matches / ground_truth_matches * 100.0) if ground_truth_matches else 0.0, 2)
        match_rate = round((matched_count / total_bank * 100.0) if total_bank else 0.0, 2)

        return {
            "total_bank_lines": total_bank,
            "ground_truth_matches": ground_truth_matches,
            "matched_by_agent": matched_count,
            "match_rate_percent": match_rate,
            "precision_percent": precision,
            "recall_percent": recall,
            "planted_unmatched_caught": planted_caught,
            "matches": matched,
            "unmatched_bank_lines": unmatched_bank,
        }

