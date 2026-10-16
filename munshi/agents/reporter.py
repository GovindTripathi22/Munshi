# munshi/agents/reporter.py
from typing import Dict, Any, List
from ..ledger.models import AuditFlag

class ReporterAgent:
    def generate_executive_report(
        self,
        trial_balance: Dict[str, Any],
        pnl: Dict[str, Any],
        balance_sheet: Dict[str, Any],
        gstr3b: Dict[str, Any],
        audit_flags: List[AuditFlag],
    ) -> str:
        lines = [
            "# MUNSHI CA STATUTORY EXECUTIVE REPORT",
            f"- **Trial Balance Status**: {'BALANCED' if trial_balance.get('is_balanced') else 'UNBALANCED'} (Dr INR {trial_balance.get('total_debit', 0):,.2f} == Cr INR {trial_balance.get('total_credit', 0):,.2f})",
            f"- **Net Profit (P&L)**: INR {pnl.get('net_profit', 0):,.2f} (Revenue: INR {pnl.get('total_revenue', 0):,.2f}, Expense: INR {pnl.get('total_expense', 0):,.2f})",
            f"- **Balance Sheet Equation**: {'BALANCED' if balance_sheet.get('is_balanced') else 'CHECK'} (Assets: INR {balance_sheet.get('total_assets', 0):,.2f})",
            f"- **Net GST Payable (GSTR-3B)**: INR {gstr3b.get('net_gst_payable', 0):,.2f}",
            f"- **Forensic Audit Flags**: {len(audit_flags)} active flag(s)",
        ]
        return "\n".join(lines)
