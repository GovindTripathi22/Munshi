# munshi/mcp_server.py
from typing import Dict, Any
from .graph import MunshiOrchestrator

class MunshiMCPServer:
    """
    Model Context Protocol (MCP) Server for AI Agents (Claude Desktop / Cursor / Antigravity).
    """
    def __init__(self):
        self.orchestrator = MunshiOrchestrator()

    def list_tools(self):
        return [
            {"name": "post_transaction", "description": "Parse natural language voucher into double-entry journal entry with GST & TDS"},
            {"name": "validate_gstin", "description": "Verify 15-character Indian GSTIN format, state code, and PAN"},
            {"name": "compute_gst", "description": "Calculate CGST/SGST vs IGST and check Section 17(5) Blocked ITC"},
            {"name": "get_financial_statements", "description": "Return Trial Balance, P&L, Balance Sheet, and GSTR-3B summary"},
            {"name": "approve_hitl_entry", "description": "Approve a high-value Pending HITL journal entry"},
            {"name": "verify_audit_chain", "description": "Verify SHA-256 cryptographic hash chain integrity"},
        ]

    def call_tool(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        normalized = name.lower().strip()
        if normalized in ("post_transaction", "record_transaction"):
            txt = arguments.get("text") or arguments.get("narrative") or arguments.get("raw_text") or ""
            dt = arguments.get("date", "2026-10-16")
            res = self.orchestrator.process_transaction(txt, dt)
            entry = res.get("entry")
            if entry:
                return {
                    "entry_id": entry.entry_id,
                    "status": res["status"],
                    "total_debit": entry.total_debit,
                    "total_credit": entry.total_credit,
                    "requires_hitl": res["requires_hitl"],
                    "trial_balance_balanced": res.get("trial_balance", {}).get("is_balanced", True),
                }
            return {
                "intent": res.get("intent"),
                "status": res.get("status", "COMPLETED"),
                "report_markdown": res.get("report_markdown", ""),
                "audit_flags": [f.rule for f in res.get("audit_flags", [])],
                "trial_balance_balanced": res.get("trial_balance", {}).get("is_balanced", True),
            }
        elif normalized == "validate_gstin":
            return self.orchestrator.gst_agent.validate_gstin(arguments.get("gstin", ""))
        elif normalized == "compute_gst":
            return self.orchestrator.gst_agent.compute_gst_split(
                float(arguments.get("taxable_amount", 0)),
                float(arguments.get("gst_rate", 18)),
                arguments.get("state_code", "27"),
                arguments.get("category", "general"),
            )
        elif normalized in ("get_financial_statements", "run_full_close"):
            return self.orchestrator.run_full_close()
        elif normalized == "get_trial_balance":
            return self.orchestrator.ledger.get_trial_balance()
        elif normalized in ("get_profit_and_loss", "get_pnl"):
            return self.orchestrator.ledger.get_profit_and_loss()
        elif normalized in ("get_gst_summary", "get_gstr3b"):
            return self.orchestrator.gst_agent.generate_gstr3b_summary(self.orchestrator.ledger.entries)
        elif normalized == "approve_hitl_entry":
            entry = self.orchestrator.ledger.approve_hitl_entry(arguments.get("entry_id", ""))
            return {"approved": entry is not None, "entry_id": entry.entry_id if entry else None}
        elif normalized in ("verify_audit_chain", "run_financial_audit"):
            return {
                "valid": self.orchestrator.ledger.audit_trail.verify_integrity(),
                "records": len(self.orchestrator.ledger.audit_trail.records),
                "audit_flags": [f.rule for f in self.orchestrator.auditor.audit_entries(self.orchestrator.ledger.entries, self.orchestrator.ledger.audit_trail)],
            }
        elif normalized in ("reconcile_statement", "reconcile"):
            return self.orchestrator.reconciler.reconcile(self.orchestrator.ledger.entries, arguments.get("bank_lines", []))
        raise ValueError(f"Unknown MCP tool: {name}")

def main():
    import json
    import sys
    server = MunshiMCPServer()
    if len(sys.argv) > 1 and sys.argv[1] == "--tools":
        print(json.dumps(server.list_tools(), indent=2))
        return
    print(f"Munshi MCP Server active. Exposed tools: {[t['name'] for t in server.list_tools()]}")

if __name__ == "__main__":
    main()

