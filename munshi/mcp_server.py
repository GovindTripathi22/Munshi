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
        if name == "post_transaction":
            res = self.orchestrator.process_transaction(arguments.get("text", ""), arguments.get("date", "2026-10-16"))
            return {
                "entry_id": res["entry"].entry_id,
                "status": res["status"],
                "total_debit": res["entry"].total_debit,
                "total_credit": res["entry"].total_credit,
                "requires_hitl": res["requires_hitl"],
            }
        elif name == "validate_gstin":
            return self.orchestrator.gst_agent.validate_gstin(arguments.get("gstin", ""))
        elif name == "compute_gst":
            return self.orchestrator.gst_agent.compute_gst_split(
                float(arguments.get("taxable_amount", 0)),
                float(arguments.get("gst_rate", 18)),
                arguments.get("state_code", "27"),
                arguments.get("category", "general"),
            )
        elif name == "get_financial_statements":
            return self.orchestrator.run_full_close()
        elif name == "approve_hitl_entry":
            entry = self.orchestrator.ledger.approve_hitl_entry(arguments.get("entry_id", ""))
            return {"approved": entry is not None, "entry_id": entry.entry_id if entry else None}
        elif name == "verify_audit_chain":
            return {"valid": self.orchestrator.ledger.audit_trail.verify_integrity(), "records": len(self.orchestrator.ledger.audit_trail.records)}
        raise ValueError(f"Unknown MCP tool: {name}")
