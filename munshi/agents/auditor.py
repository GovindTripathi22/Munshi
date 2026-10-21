# munshi/agents/auditor.py
from typing import List, Dict, Any
from ..ledger.models import JournalEntry, AuditFlag
from ..ledger.audit_trail import AuditTrail

class AuditorAgent:
    def __init__(self, hitl_threshold: float = 50000.0, cash_limit: float = 10000.0):
        self.hitl_threshold = hitl_threshold
        self.cash_limit = cash_limit

    def audit_entries(self, entries: List[JournalEntry], audit_trail: AuditTrail | None = None) -> List[AuditFlag]:
        flags: List[AuditFlag] = []
        seen_signatures = {}

        if audit_trail and not audit_trail.verify_integrity():
            flags.append(
                AuditFlag(
                    flag_id="FLAG-CHAIN-TAMPER",
                    entry_id="SYSTEM",
                    severity="CRITICAL",
                    rule="SHA256_HASH_CHAIN",
                    detail="Cryptographic hash-chain integrity check failed! Ledger tampering detected.",
                    requires_hitl=True,
                )
            )

        for idx, entry in enumerate(entries):
            if entry.payment_mode == "CASH" and entry.total_debit > self.cash_limit:
                flags.append(
                    AuditFlag(
                        flag_id=f"FLAG-40A3-{idx+1}",
                        entry_id=entry.entry_id,
                        severity="CRITICAL",
                        rule="SEC_40A_3_CASH_LIMIT",
                        detail=f"Cash payment of ₹{entry.total_debit:,.2f} exceeds ₹{self.cash_limit:,.0f} limit u/s 40A(3) Income Tax Act.",
                        requires_hitl=True,
                    )
                )

            is_capital_or_sales = any(l.account_code in ("3000", "4000", "4100") for l in entry.lines)
            if not is_capital_or_sales and entry.total_debit > self.hitl_threshold:
                flags.append(
                    AuditFlag(
                        flag_id=f"FLAG-HITL-{idx+1}",
                        entry_id=entry.entry_id,
                        severity="HIGH",
                        rule="HIGH_VALUE_HITL_GATE",
                        detail=f"High-value outflow ₹{entry.total_debit:,.2f} exceeds HITL threshold ₹{self.hitl_threshold:,.0f}.",
                        requires_hitl=True,
                    )
                )

            sig = (entry.party.lower().strip(), entry.total_debit, entry.date)
            if sig in seen_signatures:
                prev_id = seen_signatures[sig]
                flags.append(
                    AuditFlag(
                        flag_id=f"FLAG-DUP-{idx+1}",
                        entry_id=entry.entry_id,
                        severity="HIGH",
                        rule="DUPLICATE_VOUCHER",
                        detail=f"Potential duplicate transaction with {prev_id} for {entry.party} (₹{entry.total_debit:,.2f}).",
                        requires_hitl=True,
                    )
                )
            else:
                seen_signatures[sig] = entry.entry_id

        return flags

    def audit_transaction_records(self, transactions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Audit batch of invoice/transaction records (e.g. synthetic anomaly benchmark)
        Flags:
        - DUPLICATE_INVOICE: repeated invoice_no
        - INVALID_GST_RATE: non-statutory GST rate outside [0.0, 0.05, 0.12, 0.18, 0.28]
        - TAX_TOTAL_MISMATCH: taxable_value + tax_amount != total_amount
        """
        seen_invoices = set()
        valid_gst_rates = {0.0, 0.05, 0.12, 0.18, 0.28}
        flagged = []
        planted_errors_count = sum(1 for t in transactions if t.get("is_planted_error"))
        true_positives = 0
        false_positives = 0

        for t in transactions:
            inv_no = t.get("invoice_no")
            gst_rate = round(float(t.get("gst_rate", 0.0)), 2)
            taxable = float(t.get("taxable_value", 0.0))
            tax = float(t.get("tax_amount", 0.0))
            total = float(t.get("total_amount", 0.0))

            detected_error = None

            if inv_no in seen_invoices:
                detected_error = "DUPLICATE_INVOICE"
            elif gst_rate not in valid_gst_rates:
                detected_error = "INVALID_GST_RATE"
            elif abs((taxable + tax) - total) > 0.01:
                detected_error = "TAX_TOTAL_MISMATCH"

            seen_invoices.add(inv_no)

            is_planted = t.get("is_planted_error", False)
            if detected_error:
                if is_planted:
                    true_positives += 1
                else:
                    false_positives += 1
                flagged.append({
                    "id": t.get("id"),
                    "invoice_no": inv_no,
                    "error_type": detected_error,
                    "is_planted": is_planted,
                })

        false_negatives = planted_errors_count - true_positives
        precision = round((true_positives / (true_positives + false_positives) * 100.0) if (true_positives + false_positives) else 0.0, 2)
        recall = round((true_positives / planted_errors_count * 100.0) if planted_errors_count else 0.0, 2)
        f1 = round((2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0, 2)

        return {
            "total_transactions": len(transactions),
            "planted_errors_count": planted_errors_count,
            "detected_count": len(flagged),
            "true_positives": true_positives,
            "false_positives": false_positives,
            "false_negatives": false_negatives,
            "precision_percent": precision,
            "recall_percent": recall,
            "f1_score": f1,
            "flagged": flagged,
        }

