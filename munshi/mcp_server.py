# munshi/mcp_server.py
from typing import Dict, Any, Optional
import json
import sys
import asyncio
from .graph import MunshiOrchestrator
from .config import get_config

try:
    from mcp.server.mcpserver import MCPServer
    HAS_MCP = True
except ImportError:
    HAS_MCP = False

class MunshiMCPServer:
    """
    Model Context Protocol (MCP) Server for AI Agents (Claude Desktop / Cursor / Antigravity).
    Human-in-the-Loop Governance: MCP AI agents can record and read ledger data,
    but CANNOT approve high-value transactions. Approvals must be performed by
    authenticated human operators via CLI or REST API.
    """
    def __init__(self, orchestrator: Optional[MunshiOrchestrator] = None):
        self.orchestrator = orchestrator or MunshiOrchestrator()

    def list_tools(self):
        return [
            {"name": "post_transaction", "description": "Parse natural language voucher into double-entry journal entry with GST & TDS"},
            {"name": "validate_gstin", "description": "Verify 15-character Indian GSTIN format, state code, and PAN"},
            {"name": "compute_gst", "description": "Calculate CGST/SGST vs IGST and check Section 17(5) Blocked ITC"},
            {"name": "get_financial_statements", "description": "Return Trial Balance, P&L, Balance Sheet, and GSTR-3B summary"},
            {"name": "verify_audit_chain", "description": "Verify SHA-256 cryptographic hash chain integrity"},
            {"name": "reconcile_statement", "description": "Reconcile bank statement lines against ledger entries"},
        ]

    def call_tool(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        normalized = name.lower().strip()
        if normalized in ("post_transaction", "record_transaction"):
            txt = arguments.get("text") or arguments.get("narrative") or arguments.get("raw_text") or ""
            dt = arguments.get("date")
            amt = float(arguments.get("amount")) if arguments.get("amount") is not None else None
            res = self.orchestrator.process_transaction(txt, date=dt, amount=amt)
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
                invoice_date=arguments.get("date"),
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
            raise PermissionError(
                "Access Denied: AI subagents cannot approve high-value transactions via MCP. "
                "Approvals require human sign-off via CLI ('munshi chat' / '/approve') or authenticated REST API."
            )
        elif normalized in ("verify_audit_chain", "run_financial_audit"):
            return {
                "valid": self.orchestrator.ledger.audit_trail.verify_integrity(),
                "records": len(self.orchestrator.ledger.audit_trail.records),
                "audit_flags": [f.rule for f in self.orchestrator.auditor.audit_entries(self.orchestrator.ledger.entries, self.orchestrator.ledger.audit_trail)],
            }
        elif normalized in ("reconcile_statement", "reconcile"):
            return self.orchestrator.reconciler.reconcile(self.orchestrator.ledger.entries, arguments.get("bank_lines", []))
        raise ValueError(f"Unknown MCP tool: {name}")

def create_mcp_app():
    if not HAS_MCP:
        return None
    app = MCPServer("munshi-mcp-server")
    server = MunshiMCPServer()

    @app.tool()
    def post_transaction(text: str, date: str = "", amount: float = 0.0) -> str:
        """Parse natural language voucher into double-entry journal entry with GST & TDS."""
        res = server.call_tool("post_transaction", {"text": text, "date": date or None, "amount": amount or None})
        return json.dumps(res, default=str)

    @app.tool()
    def validate_gstin(gstin: str) -> str:
        """Verify 15-character Indian GSTIN format, state code, and PAN."""
        res = server.call_tool("validate_gstin", {"gstin": gstin})
        return json.dumps(res, default=str)

    @app.tool()
    def compute_gst(taxable_amount: float, gst_rate: float = 18.0, state_code: str = "27", category: str = "general", date: str = "") -> str:
        """Calculate CGST/SGST vs IGST and check Section 17(5) Blocked ITC."""
        res = server.call_tool("compute_gst", {
            "taxable_amount": taxable_amount, "gst_rate": gst_rate, "state_code": state_code, "category": category, "date": date or None
        })
        return json.dumps(res, default=str)

    @app.tool()
    def get_financial_statements() -> str:
        """Return Trial Balance, P&L, Balance Sheet, and GSTR-3B summary."""
        res = server.call_tool("get_financial_statements", {})
        return json.dumps(res, default=str)

    @app.tool()
    def verify_audit_chain() -> str:
        """Verify SHA-256 cryptographic hash chain integrity and tamper status."""
        res = server.call_tool("verify_audit_chain", {})
        return json.dumps(res, default=str)

    @app.tool()
    def approve_hitl_entry(entry_id: str) -> str:
        """Attempt to approve a pending HITL voucher. Strict governance: ALWAYS FAILS."""
        server.call_tool("approve_hitl_entry", {"entry_id": entry_id})
        return "approved"

    return app

def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--tools":
        server = MunshiMCPServer()
        print(json.dumps(server.list_tools(), indent=2))
        return
    if HAS_MCP:
        mcp_app = create_mcp_app()
        if mcp_app:
            asyncio.run(mcp_app.run_stdio_async())
            return
    server = MunshiMCPServer()
    print(f"Munshi MCP Server active. Exposed tools: {[t['name'] for t in server.list_tools()]}")

if __name__ == "__main__":
    main()
