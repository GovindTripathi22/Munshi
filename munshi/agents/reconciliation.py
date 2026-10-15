"""Bank Reconciliation Agent: Matches bank statement lines with internal invoices."""

from decimal import Decimal
from typing import Dict, List, Any, Optional
from datetime import datetime
from munshi.config import MunshiConfig


class BankStatementLine(Dict[str, Any]):
    """Represents a single bank statement record."""
    pass


class ReconciliationAgent:
    """Automates bank statement vs ledger reconciliation with fuzzy matching."""

    def __init__(self, config: Optional[MunshiConfig] = None):
        self.config = config or MunshiConfig()

    def _date_diff_days(self, date_str_1: str, date_str_2: str) -> int:
        try:
            d1 = datetime.strptime(date_str_1[:10], "%Y-%m-%d")
            d2 = datetime.strptime(date_str_2[:10], "%Y-%m-%d")
            return abs((d1 - d2).days)
        except Exception:
            return 30

    def compute_match_score(
        self,
        bank_line: Dict[str, Any],
        invoice: Dict[str, Any],
    ) -> float:
        """Computes a match score between 0.0 and 1.0."""
        score = 0.0

        # 1. Amount matching (Critical - 50% of weight)
        bank_amt = Decimal(str(bank_line.get("amount", 0)))
        inv_amt = Decimal(str(invoice.get("amount", 0)))
        if bank_amt == inv_amt and bank_amt > 0:
            score += 0.50
        elif abs(bank_amt - inv_amt) < Decimal("5.00"):
            score += 0.35  # Minor rounding or bank fee variance

        # 2. Reference / UTR / Invoice number match (30% of weight)
        bank_desc = str(bank_line.get("description", "")).lower()
        inv_ref = str(invoice.get("reference_id", "")).lower()
        inv_no = str(invoice.get("invoice_no", "")).lower()

        if inv_ref and inv_ref in bank_desc:
            score += 0.30
        elif inv_no and inv_no in bank_desc:
            score += 0.30
        else:
            # Check counterparty name
            party = str(invoice.get("counterparty", "")).lower()
            if party and party in bank_desc:
                score += 0.20

        # 3. Date proximity (20% of weight)
        bank_date = bank_line.get("date", "")
        inv_date = invoice.get("date", "")
        days_diff = self._date_diff_days(bank_date, inv_date)
        if days_diff == 0:
            score += 0.20
        elif days_diff <= 3:
            score += 0.15
        elif days_diff <= 7:
            score += 0.10

        return round(min(score, 1.0), 3)

    def reconcile(
        self,
        bank_lines: List[Dict[str, Any]],
        internal_invoices: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Reconciles bank statement items against internal ledger invoices.
        Returns match rate, matched pairs, and un-reconciled items.
        """
        matched_pairs: List[Dict[str, Any]] = []
        unmatched_bank: List[Dict[str, Any]] = []
        matched_invoice_ids = set()

        for bank_item in bank_lines:
            best_match = None
            best_score = 0.0

            for inv in internal_invoices:
                inv_id = inv.get("id") or inv.get("invoice_no")
                if inv_id in matched_invoice_ids:
                    continue

                score = self.compute_match_score(bank_item, inv)
                if score > best_score:
                    best_score = score
                    best_match = inv

            if best_score >= self.config.auto_approve_reconciliation_confidence and best_match:
                inv_id = best_match.get("id") or best_match.get("invoice_no")
                matched_invoice_ids.add(inv_id)
                matched_pairs.append({
                    "bank_line_id": bank_item.get("id"),
                    "invoice_id": inv_id,
                    "amount": str(bank_item.get("amount")),
                    "match_score": best_score,
                    "status": "MATCHED",
                })
            else:
                unmatched_bank.append({
                    "bank_line": bank_item,
                    "closest_score": best_score,
                    "closest_invoice": best_match.get("invoice_no") if best_match else None,
                    "reason": "Low confidence match" if best_score > 0.4 else "No corresponding invoice found",
                })

        unmatched_invoices = [
            inv for inv in internal_invoices
            if (inv.get("id") or inv.get("invoice_no")) not in matched_invoice_ids
        ]

        total_bank_count = len(bank_lines)
        match_rate = (len(matched_pairs) / total_bank_count * 100) if total_bank_count > 0 else 100.0

        return {
            "total_bank_lines": total_bank_count,
            "matched_count": len(matched_pairs),
            "unmatched_bank_count": len(unmatched_bank),
            "unmatched_invoice_count": len(unmatched_invoices),
            "match_rate_percent": round(match_rate, 2),
            "matches": matched_pairs,
            "unmatched_bank_lines": unmatched_bank,
            "unmatched_invoices": unmatched_invoices,
            "requires_review": len(unmatched_bank) > 0 or len(unmatched_invoices) > 0,
        }
