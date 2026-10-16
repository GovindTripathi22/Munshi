# munshi/graph.py
from typing import Dict, Any, List
from .ledger.engine import LedgerEngine
from .ledger.models import BankStatementLine
from .agents.supervisor import SupervisorAgent
from .agents.bookkeeper import BookkeeperAgent
from .agents.gst import GSTAgent
from .agents.reconciliation import ReconciliationAgent
from .agents.auditor import AuditorAgent
from .agents.reporter import ReporterAgent

class MunshiOrchestrator:
    """
    End-to-End LangGraph-compatible Multi-Agent Orchestrator:
    Supervisor -> Bookkeeper -> GST -> Reconciliation -> Auditor -> HITL Gate -> Reporter
    """
    def __init__(self, home_state_code: str = "27", hitl_threshold: float = 50000.0):
        self.ledger = LedgerEngine()
        self.supervisor = SupervisorAgent()
        self.bookkeeper = BookkeeperAgent(home_state_code=home_state_code, hitl_threshold=hitl_threshold)
        self.gst_agent = GSTAgent(home_state_code=home_state_code)
        self.reconciler = ReconciliationAgent()
        self.auditor = AuditorAgent(hitl_threshold=hitl_threshold)
        self.reporter = ReporterAgent()

    def process_transaction(self, raw_text: str, date: str = "2026-10-16") -> Dict[str, Any]:
        intent = self.supervisor.route_intent(raw_text)
        entry = self.bookkeeper.parse_and_create_entry(raw_text, date=date)
        self.ledger.post_entry(entry)
        flags = self.auditor.audit_entries(self.ledger.entries, self.ledger.audit_trail)
        gstr3b = self.gst_agent.generate_gstr3b_summary(self.ledger.entries)
        tb = self.ledger.get_trial_balance()
        pnl = self.ledger.get_profit_and_loss()
        bs = self.ledger.get_balance_sheet()
        report_md = self.reporter.generate_executive_report(tb, pnl, bs, gstr3b, flags)
        return {
            "intent": intent,
            "entry": entry,
            "status": entry.status,
            "requires_hitl": entry.status == "PENDING_HITL",
            "audit_flags": flags,
            "trial_balance": tb,
            "profit_and_loss": pnl,
            "balance_sheet": bs,
            "gstr3b": gstr3b,
            "report_markdown": report_md,
        }

    def run_full_close(self, bank_lines: List[BankStatementLine] | None = None) -> Dict[str, Any]:
        recon = self.reconciler.reconcile(self.ledger.entries, bank_lines or [])
        flags = self.auditor.audit_entries(self.ledger.entries, self.ledger.audit_trail)
        tb = self.ledger.get_trial_balance()
        pnl = self.ledger.get_profit_and_loss()
        bs = self.ledger.get_balance_sheet()
        gstr3b = self.gst_agent.generate_gstr3b_summary(self.ledger.entries)
        return {
            "trial_balance": tb,
            "profit_and_loss": pnl,
            "balance_sheet": bs,
            "gstr3b": gstr3b,
            "reconciliation": recon,
            "audit_flags": flags,
            "audit_chain_valid": self.ledger.audit_trail.verify_integrity(),
            "report_markdown": self.reporter.generate_executive_report(tb, pnl, bs, gstr3b, flags),
        }

def build_munshi_graph(home_state_code: str = "27", hitl_threshold: float = 50000.0) -> MunshiOrchestrator:
    return MunshiOrchestrator(home_state_code=home_state_code, hitl_threshold=hitl_threshold)
