"""LangGraph StateGraph builder for Munshi Multi-Agent Finance Assistant."""

from decimal import Decimal
from datetime import date
from typing import Dict, Any, Optional
from langgraph.graph import StateGraph, START, END

from munshi.config import MunshiConfig
from munshi.ledger.engine import DoubleEntryLedger
from munshi.ledger.models import LedgerTransaction, TransactionStatus
from munshi.agents.state import AgentState
from munshi.agents.supervisor import SupervisorAgent
from munshi.agents.bookkeeper import BookkeeperAgent
from munshi.agents.gst import GSTComputationAgent
from munshi.agents.reconciliation import ReconciliationAgent
from munshi.agents.auditor import AuditorAgent
from munshi.agents.reporter import ReportingAgent


def create_munshi_graph(
    ledger: Optional[DoubleEntryLedger] = None,
    config: Optional[MunshiConfig] = None,
):
    """
    Constructs and compiles the supervisor-routed multi-agent LangGraph workflow.
    """
    conf = config or MunshiConfig()
    led = ledger or DoubleEntryLedger(conf.db_path)

    supervisor = SupervisorAgent(conf)
    bookkeeper = BookkeeperAgent(conf)
    gst_agent = GSTComputationAgent(conf)
    reconciler = ReconciliationAgent(conf)
    auditor = AuditorAgent(conf)
    reporter = ReportingAgent(led, conf)

    # Define Node functions
    def supervisor_node(state: AgentState) -> Dict[str, Any]:
        updated_state = supervisor.process_state(state)
        return {
            "current_agent": "supervisor",
            "next_agent": updated_state.next_agent,
            "task_type": updated_state.task_type,
            "requires_human_approval": updated_state.requires_human_approval,
            "approval_reason": updated_state.approval_reason,
            "messages": [f"Supervisor: routing to {updated_state.next_agent}"],
        }

    def bookkeeper_node(state: AgentState) -> Dict[str, Any]:
        tx_data = state.raw_transaction or {}
        description = tx_data.get("description", state.query)
        amount = Decimal(str(tx_data.get("amount", 0)))
        counterparty_gstin = tx_data.get("counterparty_gstin")
        is_sale = tx_data.get("is_sale", False)
        payment_method = tx_data.get("payment_method", "BANK")
        date_str = tx_data.get("date", date.today().isoformat())
        tx_id = tx_data.get("id", f"TXN-{date_str[:10]}-001")

        counterparty = tx_data.get("counterparty", "")
        classification = bookkeeper.classify_transaction(description, counterparty)
        tx = bookkeeper.create_journal_transaction(
            tx_id=tx_id,
            date=date_str,
            description=description,
            amount=amount,
            is_sale=is_sale,
            counterparty_gstin=counterparty_gstin,
            payment_method=payment_method,
            counterparty=counterparty,
        )

        requires_approval = (
            tx.total_debits() >= conf.high_value_approval_threshold
            or classification["confidence"] < conf.low_confidence_threshold
        )

        approval_reason = None
        if requires_approval:
            reasons = []
            if tx.total_debits() >= conf.high_value_approval_threshold:
                reasons.append(f"Amount ₹{tx.total_debits()} exceeds ₹{conf.high_value_approval_threshold}")
            if classification["confidence"] < conf.low_confidence_threshold:
                reasons.append(f"Low confidence ({classification['confidence']}) categorization")
            approval_reason = "; ".join(reasons)

        return {
            "current_agent": "bookkeeper",
            "categorization": {
                "account_code": classification["account_code"],
                "account_name": classification["account_name"],
                "confidence": classification["confidence"],
                "transaction_draft": tx.model_dump(),
            },
            "transaction_id": tx_id,
            "requires_human_approval": requires_approval,
            "approval_reason": approval_reason,
            "messages": [f"Bookkeeper: Drafted transaction {tx_id} ({classification['account_name']})"],
        }

    def gst_node(state: AgentState) -> Dict[str, Any]:
        tx_data = state.raw_transaction or {}
        taxable_val = Decimal(str(tx_data.get("taxable_value", tx_data.get("amount", 0))))
        rate = Decimal(str(tx_data.get("rate", "0.18")))
        gstin = tx_data.get("counterparty_gstin")

        gst_calc = gst_agent.compute_gst(
            taxable_value=taxable_val,
            rate=rate,
            counterparty_gstin=gstin,
        )
        return {
            "current_agent": "gst",
            "gst_details": gst_calc,
            "messages": [f"GST: Computed total tax ₹{gst_calc['total_tax']}"],
        }

    def reconciliation_node(state: AgentState) -> Dict[str, Any]:
        rec_input = state.raw_transaction or state.reconciliation_data or {}
        bank_lines = rec_input.get("bank_lines", [])
        invoices = rec_input.get("invoices", [])

        rec_result = reconciler.reconcile(bank_lines, invoices)
        return {
            "current_agent": "reconciliation",
            "reconciliation_data": rec_result,
            "messages": [f"Reconciliation: Match rate {rec_result['match_rate_percent']}%"],
        }

    def auditor_node(state: AgentState) -> Dict[str, Any]:
        audit_input = state.raw_transaction or {}
        tx_list = audit_input.get("transactions", [])
        if not tx_list and state.categorization:
            # Audit the drafted transaction
            tx_draft = state.categorization.get("transaction_draft")
            if tx_draft:
                tx_obj = LedgerTransaction.model_validate(tx_draft)
                res = auditor.audit_transaction(tx_obj)
                return {
                    "current_agent": "auditor",
                    "audit_findings": res,
                    "messages": [f"Auditor: Scanned transaction with severity {res['overall_severity']}"],
                }

        batch_res = auditor.audit_batch(tx_list)
        return {
            "current_agent": "auditor",
            "audit_findings": batch_res,
            "messages": [f"Auditor: Detected {batch_res['anomalies_detected']} anomalies"],
        }

    def reporter_node(state: AgentState) -> Dict[str, Any]:
        sub_type = state.raw_transaction.get("report_type", "trial_balance") if state.raw_transaction else "trial_balance"
        q = state.query.lower()

        if "profit" in q or "p&l" in q or sub_type == "pnl":
            content = reporter.generate_profit_loss_report()
            raw = led.get_profit_and_loss()
        elif "gst" in q or sub_type == "gst":
            raw = reporter.generate_gst_summary()
            content = f"GST Summary:\n- Output: ₹{raw['output_liability']['total']}\n- ITC: ₹{raw['input_tax_credit']['total']}\n- Net Payable: ₹{raw['net_tax_payable_cash']}"
        else:
            content = reporter.generate_trial_balance_report()
            raw = led.get_trial_balance()

        return {
            "current_agent": "reporter",
            "report_output": {"markdown": content, "raw": raw},
            "messages": ["Reporter: Generated financial statement"],
        }

    def post_ledger_node(state: AgentState) -> Dict[str, Any]:
        if state.categorization and "transaction_draft" in state.categorization:
            tx_dict = state.categorization["transaction_draft"]
            tx = LedgerTransaction.model_validate(tx_dict)
            try:
                posted_tx = led.post_transaction(tx, actor="agent:langgraph_pipeline", force_approval=True)
                return {
                    "current_agent": "post_ledger",
                    "ledger_posted": True,
                    "transaction_id": posted_tx.id,
                    "messages": [f"PostLedger: Successfully posted {posted_tx.id} to ledger"],
                }
            except Exception as e:
                return {
                    "current_agent": "post_ledger",
                    "ledger_posted": False,
                    "errors": [str(e)],
                    "messages": [f"PostLedger Error: {str(e)}"],
                }
        return {"current_agent": "post_ledger", "ledger_posted": False}

    def human_approval_node(state: AgentState) -> Dict[str, Any]:
        # Represents the human approval gate
        if state.human_decision == "APPROVED":
            return {
                "requires_human_approval": False,
                "messages": ["Human Reviewer: Transaction APPROVED"],
            }
        elif state.human_decision == "REJECTED":
            return {
                "requires_human_approval": False,
                "messages": ["Human Reviewer: Transaction REJECTED"],
            }
        else:
            return {
                "requires_human_approval": True,
                "messages": [f"Awaiting human approval: {state.approval_reason}"],
            }

    # Conditional edge router
    def route_from_supervisor(state: AgentState) -> str:
        target = state.next_agent
        if target in ["bookkeeper", "gst", "reconciliation", "auditor", "reporter", "human_approval", "post_ledger"]:
            return target
        return END

    def route_after_worker(state: AgentState) -> str:
        # Loop back to supervisor to verify state and advance
        return "supervisor"

    def route_from_human_approval(state: AgentState) -> str:
        if state.human_decision == "APPROVED":
            return "post_ledger"
        elif state.human_decision == "REJECTED":
            return END
        else:
            # Pauses execution at human approval gate
            return END

    # Build the StateGraph
    workflow = StateGraph(AgentState)

    # Add nodes
    workflow.add_node("supervisor", supervisor_node)
    workflow.add_node("bookkeeper", bookkeeper_node)
    workflow.add_node("gst", gst_node)
    workflow.add_node("reconciliation", reconciliation_node)
    workflow.add_node("auditor", auditor_node)
    workflow.add_node("reporter", reporter_node)
    workflow.add_node("post_ledger", post_ledger_node)
    workflow.add_node("human_approval", human_approval_node)

    # Connect edges
    workflow.add_edge(START, "supervisor")

    workflow.add_conditional_edges(
        "supervisor",
        route_from_supervisor,
        {
            "bookkeeper": "bookkeeper",
            "gst": "gst",
            "reconciliation": "reconciliation",
            "auditor": "auditor",
            "reporter": "reporter",
            "human_approval": "human_approval",
            "post_ledger": "post_ledger",
            END: END,
        },
    )

    # Worker nodes report back to supervisor
    workflow.add_edge("bookkeeper", "supervisor")
    workflow.add_edge("gst", "supervisor")
    workflow.add_edge("reconciliation", "supervisor")
    workflow.add_edge("auditor", "supervisor")
    workflow.add_edge("reporter", "supervisor")
    workflow.add_edge("post_ledger", END)

    workflow.add_conditional_edges(
        "human_approval",
        route_from_human_approval,
        {
            "post_ledger": "post_ledger",
            END: END,
        },
    )

    return workflow.compile()
