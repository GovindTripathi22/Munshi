"""Auditor Agent: Financial anomaly detection, fraud checks, and regulatory compliance."""

from decimal import Decimal
from typing import Dict, List, Any, Optional
from collections import defaultdict
from munshi.config import MunshiConfig, VALID_GST_RATES
from munshi.ledger.models import LedgerTransaction


class AuditorAgent:
    """Detects planted errors, duplicates, tax anomalies, and ledger imbalances."""

    def __init__(self, config: Optional[MunshiConfig] = None):
        self.config = config or MunshiConfig()

    def audit_transaction(self, tx: LedgerTransaction) -> Dict[str, Any]:
        """Audits a single ledger transaction for inconsistencies."""
        anomalies: List[Dict[str, Any]] = []
        severity = "CLEAN"

        # Check 1: Balance Invariant
        dr = tx.total_debits()
        cr = tx.total_credits()
        if dr != cr:
            anomalies.append({
                "type": "IMBALANCE_ERROR",
                "severity": "CRITICAL",
                "message": f"Debits ({dr}) do not equal Credits ({cr}). Imbalance of {dr - cr}.",
            })
            severity = "CRITICAL"

        # Check 2: High Value Threshold
        if dr >= self.config.high_value_approval_threshold:
            anomalies.append({
                "type": "HIGH_VALUE_TRANSACTION",
                "severity": "MEDIUM",
                "message": f"Transaction amount ({dr}) exceeds human approval threshold ({self.config.high_value_approval_threshold}).",
            })
            if severity not in ["HIGH", "CRITICAL"]:
                severity = "MEDIUM"

        return {
            "transaction_id": tx.id,
            "has_anomalies": len(anomalies) > 0,
            "anomalies": anomalies,
            "overall_severity": severity,
        }

    def audit_batch(
        self,
        transactions: List[Dict[str, Any]],
        existing_invoice_numbers: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Scans a batch of transactions for duplicates, tax mismatches, and planted errors.
        """
        seen_invoices = set(existing_invoice_numbers or [])
        invoice_counts = defaultdict(int)
        flagged_issues: List[Dict[str, Any]] = []

        total_tx = len(transactions)
        duplicate_count = 0
        tax_error_count = 0
        imbalance_count = 0

        for tx in transactions:
            tx_id = tx.get("id") or tx.get("invoice_no", "")
            invoice_no = tx.get("invoice_no")

            # Check Duplicate Invoice Number
            if invoice_no:
                if invoice_no in seen_invoices:
                    duplicate_count += 1
                    flagged_issues.append({
                        "tx_id": tx_id,
                        "type": "DUPLICATE_INVOICE",
                        "severity": "HIGH",
                        "message": f"Duplicate invoice number detected: '{invoice_no}'.",
                    })
                seen_invoices.add(invoice_no)

            # Check Planted GST Rate Discrepancy
            rate = tx.get("gst_rate")
            if rate is not None:
                dec_rate = Decimal(str(rate))
                if dec_rate > 1:
                    dec_rate = dec_rate / Decimal("100")
                if dec_rate not in VALID_GST_RATES:
                    tax_error_count += 1
                    flagged_issues.append({
                        "tx_id": tx_id,
                        "type": "INVALID_GST_RATE",
                        "severity": "HIGH",
                        "message": f"Unrecognized GST rate: {rate}. Valid slabs: 0%, 5%, 12%, 18%, 28%.",
                    })

            # Check Math / Total discrepancy if taxable and tax provided
            taxable = tx.get("taxable_value")
            tax = tx.get("tax_amount")
            total = tx.get("total_amount")
            if taxable is not None and tax is not None and total is not None:
                calc_total = Decimal(str(taxable)) + Decimal(str(tax))
                if abs(calc_total - Decimal(str(total))) > Decimal("0.05"):
                    tax_error_count += 1
                    flagged_issues.append({
                        "tx_id": tx_id,
                        "type": "TAX_TOTAL_MISMATCH",
                        "severity": "HIGH",
                        "message": f"Taxable ({taxable}) + Tax ({tax}) = {calc_total} does not match Total ({total}).",
                    })

            # Check debit / credit imbalance if provided as items
            items = tx.get("items", [])
            if items:
                sum_dr = sum(Decimal(str(it.get("debit", 0))) for it in items)
                sum_cr = sum(Decimal(str(it.get("credit", 0))) for it in items)
                if sum_dr != sum_cr:
                    imbalance_count += 1
                    flagged_issues.append({
                        "tx_id": tx_id,
                        "type": "LEDGER_IMBALANCE",
                        "severity": "CRITICAL",
                        "message": f"Debit sum ({sum_dr}) != Credit sum ({sum_cr}).",
                    })

        anomaly_count = len(flagged_issues)
        risk_score = min(100, int((anomaly_count / max(1, total_tx)) * 100))

        return {
            "total_transactions_scanned": total_tx,
            "anomalies_detected": anomaly_count,
            "duplicate_invoices_found": duplicate_count,
            "tax_errors_found": tax_error_count,
            "imbalances_found": imbalance_count,
            "risk_score": risk_score,
            "flagged_issues": flagged_issues,
            "status": "FLAGGED" if anomaly_count > 0 else "CLEAN",
        }
