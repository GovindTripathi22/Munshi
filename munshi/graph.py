# munshi/graph.py
from typing import Dict, Any, List
from langgraph.graph import StateGraph, START, END
from .ledger.engine import LedgerEngine
from .ledger.models import BankStatementLine
from .agents.state import MunshiAgentState
from .agents.supervisor import SupervisorAgent
from .agents.bookkeeper import BookkeeperAgent
from .agents.gst import GSTAgent
from .agents.reconciliation import ReconciliationAgent
from .agents.auditor import AuditorAgent
from .agents.reporter import ReporterAgent

class MunshiOrchestrator:
    """
    End-to-End LangGraph Multi-Agent Orchestrator:
    Supervisor -> Bookkeeper -> GST -> Auditor -> Reporter
    """
    def __init__(self, home_state_code: str = "27", hitl_threshold: float = 50000.0):
        self.ledger = LedgerEngine()
        self.supervisor = SupervisorAgent()
        self.bookkeeper = BookkeeperAgent(home_state_code=home_state_code, hitl_threshold=hitl_threshold)
        self.gst_agent = GSTAgent(home_state_code=home_state_code)
        self.reconciler = ReconciliationAgent()
        self.auditor = AuditorAgent(hitl_threshold=hitl_threshold)
        self.reporter = ReporterAgent()
        self.compiled_graph = self._build_langgraph()

    def _build_langgraph(self):
        builder = StateGraph(MunshiAgentState)

        def supervisor_node(state: MunshiAgentState):
            intent = self.supervisor.route_intent(state.get("raw_input", ""))
            return {"intent": intent}

        def bookkeeper_node(state: MunshiAgentState):
            entry = self.bookkeeper.parse_and_create_entry(
                state.get("raw_input", ""),
                date=state.get("date", "2026-10-16"),
            )
            self.ledger.post_entry(entry)
            return {
                "entry": entry,
                "status": entry.status,
                "requires_hitl": entry.status == "PENDING_HITL",
            }

        def gst_node(state: MunshiAgentState):
            gstr3b = self.gst_agent.generate_gstr3b_summary(self.ledger.entries)
            return {"gstr3b": gstr3b}

        def auditor_node(state: MunshiAgentState):
            flags = self.auditor.audit_entries(self.ledger.entries, self.ledger.audit_trail)
            return {"audit_flags": flags}

        def reporter_node(state: MunshiAgentState):
            tb = self.ledger.get_trial_balance()
            pnl = self.ledger.get_profit_and_loss()
            bs = self.ledger.get_balance_sheet()
            flags = state.get("audit_flags", [])
            gstr3b = state.get("gstr3b", {})
            report_md = self.reporter.generate_executive_report(tb, pnl, bs, gstr3b, flags)
            return {
                "trial_balance": tb,
                "profit_and_loss": pnl,
                "balance_sheet": bs,
                "report_markdown": report_md,
            }

        def reconciler_node(state: MunshiAgentState):
            recon = self.reconciler.reconcile(self.ledger.entries, state.get("bank_lines", []))
            return {"reconciliation": recon}

        builder.add_node("supervisor", supervisor_node)
        builder.add_node("bookkeeper", bookkeeper_node)
        builder.add_node("gst", gst_node)
        builder.add_node("reconciler", reconciler_node)
        builder.add_node("auditor", auditor_node)
        builder.add_node("reporter", reporter_node)

        def route_by_intent(state: MunshiAgentState):
            intent = state.get("intent", "BOOKKEEPING")
            if intent == "BOOKKEEPING":
                return "bookkeeper"
            elif intent == "GST_CHECK":
                return "gst"
            elif intent == "RECONCILIATION":
                return "reconciler"
            elif intent == "AUDIT":
                return "auditor"
            else:
                return "reporter"

        builder.add_edge(START, "supervisor")
        builder.add_conditional_edges(
            "supervisor",
            route_by_intent,
            {
                "bookkeeper": "bookkeeper",
                "gst": "gst",
                "reconciler": "reconciler",
                "auditor": "auditor",
                "reporter": "reporter",
            },
        )
        builder.add_edge("bookkeeper", "gst")
        builder.add_edge("gst", "auditor")
        builder.add_edge("auditor", "reporter")
        builder.add_edge("reconciler", "reporter")
        builder.add_edge("reporter", END)

        return builder.compile()

    def process_transaction(self, raw_text: str, date: str = "2026-10-16", bank_lines: List[BankStatementLine] | None = None) -> Dict[str, Any]:
        initial_state: MunshiAgentState = {
            "raw_input": raw_text,
            "date": date,
            "bank_lines": bank_lines or [],
            "status": "PROCESSING",
        }
        res = self.compiled_graph.invoke(initial_state)
        return {
            "intent": res.get("intent"),
            "entry": res.get("entry"),
            "status": res.get("status", "COMPLETED"),
            "requires_hitl": res.get("requires_hitl", False),
            "audit_flags": res.get("audit_flags", []),
            "trial_balance": res.get("trial_balance", {}),
            "profit_and_loss": res.get("profit_and_loss", {}),
            "balance_sheet": res.get("balance_sheet", {}),
            "gstr3b": res.get("gstr3b", {}),
            "reconciliation": res.get("reconciliation", {}),
            "report_markdown": res.get("report_markdown", ""),
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
