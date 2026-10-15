"""Supervisor Agent: Master orchestrator and router in LangGraph."""

import re
from typing import Dict, Any, Optional
from munshi.config import MunshiConfig
from munshi.agents.state import AgentState


class SupervisorAgent:
    """Master agent that routes queries and determines next actions and approval gates."""

    def __init__(self, config: Optional[MunshiConfig] = None):
        self.config = config or MunshiConfig()

    def route_query(self, query: str) -> str:
        """Determines the target agent based on query intent."""
        q = query.lower()

        if any(w in q for w in ["reconcile", "reconciliation", "bank statement", "statement match", "utr"]):
            return "reconciliation"
        elif any(w in q for w in ["audit", "anomaly", "anomalies", "duplicate", "fraud", "error", "check ledger"]):
            return "audit"
        elif any(w in q for w in ["report", "balance sheet", "p&l", "profit", "loss", "trial balance", "gstr", "tax summary"]):
            return "reporting"
        elif any(w in q for w in ["gst", "tax rate", "cgst", "sgst", "igst", "itc"]):
            return "gst"
        elif any(w in q for w in ["invoice", "bill", "expense", "sale", "paid", "received", "bookkeep", "entry", "post"]):
            return "bookkeeping"
        else:
            return "bookkeeping"

    def process_state(self, state: AgentState) -> AgentState:
        """Processes the state, updates next_agent routing, and checks HITL gates."""
        if not state.task_type:
            state.task_type = self.route_query(state.query)

        # Check if human approval is requested
        if state.requires_human_approval and state.human_decision is None:
            state.next_agent = "human_approval"
            return state

        # Check if human decision was provided
        if state.human_decision == "REJECTED":
            state.next_agent = "END"
            state.errors.append("Transaction was rejected by human reviewer.")
            return state

        # Route to appropriate specialist
        if state.task_type == "bookkeeping" or state.task_type == "bookkeeper":
            if not state.categorization:
                state.next_agent = "bookkeeper"
            elif state.requires_human_approval and not state.human_decision:
                state.next_agent = "human_approval"
            elif not state.ledger_posted:
                state.next_agent = "post_ledger"
            else:
                state.next_agent = "END"
        elif state.task_type == "reconciliation":
            state.next_agent = "reconciliation" if not state.reconciliation_data else "END"
        elif state.task_type == "audit" or state.task_type == "auditor":
            state.next_agent = "auditor" if not state.audit_findings else "END"
        elif state.task_type == "reporting" or state.task_type == "reporter":
            state.next_agent = "reporter" if not state.report_output else "END"
        elif state.task_type == "gst":
            state.next_agent = "gst" if not state.gst_details else "END"
        else:
            state.next_agent = "END"

        return state
