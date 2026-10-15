"""Reporting Agent: Financial statement generation and GST compliance summaries."""

from decimal import Decimal
from typing import Dict, Any, Optional
from munshi.ledger.engine import DoubleEntryLedger
from munshi.config import MunshiConfig


class ReportingAgent:
    """Compiles Trial Balance, Profit & Loss, Balance Sheet, and GSTR-3B returns."""

    def __init__(self, ledger: DoubleEntryLedger, config: Optional[MunshiConfig] = None):
        self.ledger = ledger
        self.config = config or MunshiConfig()

    def generate_trial_balance_report(self) -> str:
        """Returns Markdown-formatted Trial Balance."""
        tb = self.ledger.get_trial_balance()
        lines = [
            f"# Trial Balance: {self.config.company_name}",
            f"**Status:** {'Balanced (Debits = Credits)' if tb['is_balanced'] else 'IMBALANCED'}",
            "",
            "| Code | Account Name | Type | Debit (INR ) | Credit (INR ) |",
            "| :--- | :--- | :--- | :---: | :---: |",
        ]
        for row in tb["rows"]:
            lines.append(f"| {row['code']} | {row['name']} | {row['type']} | {row['debit']} | {row['credit']} |")

        lines.extend([
            f"| **TOTAL** | | | **INR {tb['total_debits']}** | **INR {tb['total_credits']}** |",
            "",
            f"*Difference: INR {tb['difference']}*",
        ])
        return "\n".join(lines)

    def generate_profit_loss_report(self) -> str:
        """Returns Markdown-formatted Profit and Loss Statement."""
        pnl = self.ledger.get_profit_and_loss()
        lines = [
            f"# Profit & Loss Statement: {self.config.company_name}",
            "",
            "### Revenue",
            "| Code | Account | Amount (INR ) |",
            "| :--- | :--- | :---: |",
        ]
        for rev in pnl["revenues"]:
            lines.append(f"| {rev['code']} | {rev['name']} | INR {rev['amount']} |")
        lines.append(f"| **Total Revenue** | | **INR {pnl['total_revenue']}** |")

        lines.extend([
            "",
            "### Expenses",
            "| Code | Account | Amount (INR ) |",
            "| :--- | :--- | :---: |",
        ])
        for exp in pnl["expenses"]:
            lines.append(f"| {exp['code']} | {exp['name']} | INR {exp['amount']} |")
        lines.append(f"| **Total Expenses** | | **INR {pnl['total_expenses']}** |")

        lines.extend([
            "",
            "---",
            f"### **Net Profit / (Loss): INR {pnl['net_profit']}**",
        ])
        return "\n".join(lines)

    def generate_gst_summary(self) -> Dict[str, Any]:
        """
        Generates Indian GSTR-3B monthly tax summary:
        - Output GST on Sales (Liabilities: 2100 CGST, 2110 SGST, 2120 IGST)
        - Input Tax Credit (ITC) Available (Assets: 1300 CGST, 1310 SGST, 1320 IGST)
        - Net Tax Payable in Cash = max(0, Output - ITC)
        """
        out_cgst = self.ledger.get_account("2100").balance
        out_sgst = self.ledger.get_account("2110").balance
        out_igst = self.ledger.get_account("2120").balance
        total_output_liability = out_cgst + out_sgst + out_igst

        in_cgst = self.ledger.get_account("1300").balance
        in_sgst = self.ledger.get_account("1310").balance
        in_igst = self.ledger.get_account("1320").balance
        total_itc_available = in_cgst + in_sgst + in_igst

        # Offsetting rules:
        net_payable_cgst = max(Decimal("0.00"), out_cgst - in_cgst)
        net_payable_sgst = max(Decimal("0.00"), out_sgst - in_sgst)
        net_payable_igst = max(Decimal("0.00"), out_igst - in_igst)
        net_cash_payable = net_payable_cgst + net_payable_sgst + net_payable_igst

        return {
            "company": self.config.company_name,
            "gstin": self.config.gstin,
            "output_liability": {
                "cgst": str(out_cgst),
                "sgst": str(out_sgst),
                "igst": str(out_igst),
                "total": str(total_output_liability),
            },
            "input_tax_credit": {
                "cgst": str(in_cgst),
                "sgst": str(in_sgst),
                "igst": str(in_igst),
                "total": str(total_itc_available),
            },
            "net_tax_payable_cash": str(net_cash_payable),
        }
