# munshi/graph.py
from typing import Dict, Any, List
from .ledger.engine import LedgerEngine
from .ledger.models import BankStatementLine
from .agents.bookkeeper import BookkeeperAgent
from .agents.gst import GSTAgent
from .agents.reconciliation import ReconciliationAgent
from .agents.auditor import AuditorAgent

class MunshiOrchestrator:
    """
    End-to-End LangGraph-compatible Multi-Agent Orchestrator:
    Supervisor -> Bookkeeper -> GST -> Reconciliation -> Auditor -> HITL Gate -> Reporter
    """
    def __init__(self, home_state_code: str = "27", hitl_threshold: float = 50000.0):
        self.ledger = LedgerEngine()
        self.bookkeeper = BookkeeperAgent(home_state_code=home_state_code, hitl_threshold=hitl_threshold)
        self.gst_agent = GSTAgent(home_state_code=home_state_code)
        self.reconciler = ReconciliationAgent()
        self.auditor = AuditorAgent(hitl_threshold=hitl_threshold)

    def process_transaction(self, raw_text: str, date: str = "2026-10-16") -> Dict[str, Any]:
        entry = self.bookkeeper.parse_and_create_entry(raw_text, date=date)
        self.ledger.post_entry(entry)
        flags = self.auditor.audit_entries(self.ledger.entries, self.ledger.audit_trail)
        gstr3b = self.gst_agent.generate_gstr3b_summary(self.ledger.entries)
        return {
            "entry": entry,
            "status": entry.status,
            "requires_hitl": entry.status == "PENDING_HITL",
            "audit_flags": flags,
            "trial_balance": self.ledger.get_trial_balance(),
            "gstr3b": gstr3b,
        }

    def run_full_close(self, bank_lines: List[BankStatementLine] | None = None) -> Dict[str, Any]:
        recon = self.reconciler.reconcile(self.ledger.entries, bank_lines or [])
        flags = self.auditor.audit_entries(self.ledger.entries, self.ledger.audit_trail)
        return {
            "trial_balance": self.ledger.get_trial_balance(),
            "profit_and_loss": self.ledger.get_profit_and_loss(),
            "balance_sheet": self.ledger.get_balance_sheet(),
            "gstr3b": self.gst_agent.generate_gstr3b_summary(self.ledger.entries),
            "reconciliation": recon,
            "audit_flags": flags,
            "audit_chain_valid": self.ledger.audit_trail.verify_integrity(),
        }

def create_munshi_graph(home_state_code: str = "27", hitl_threshold: float = 50000.0, ledger: LedgerEngine | None = None) -> MunshiOrchestrator:
    orch = MunshiOrchestrator(home_state_code=home_state_code, hitl_threshold=hitl_threshold)
    if ledger:
        orch.ledger = ledger
    return orch

