# munshi/agents/supervisor.py
from typing import Literal

IntentType = Literal["BOOKKEEPING", "GST_CHECK", "RECONCILIATION", "AUDIT", "REPORT"]

class SupervisorAgent:
    def route_intent(self, raw_input: str) -> IntentType:
        lower = (raw_input or "").lower()
        if any(k in lower for k in ("reconcile", "bank statement", "utr match")):
            return "RECONCILIATION"
        if any(k in lower for k in ("audit", "forensic", "tamper", "40a(3)")):
            return "AUDIT"
        if any(k in lower for k in ("gstr", "gstin", "hsn")) and not any(k in lower for k in ("paid", "sold", "purchased", "billed")):
            return "GST_CHECK"
        if any(k in lower for k in ("trial balance", "balance sheet", "p&l", "profit and loss", "report")):
            return "REPORT"
        return "BOOKKEEPING"
