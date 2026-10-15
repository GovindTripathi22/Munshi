"""Tests for LangGraph StateGraph supervisor workflow."""

from munshi.graph import create_munshi_graph
from munshi.agents.state import AgentState
from munshi.ledger.engine import DoubleEntryLedger


def test_langgraph_bookkeeping_workflow():
    ledger = DoubleEntryLedger()
    graph = create_munshi_graph(ledger=ledger)

    state = AgentState(
        query="Record AWS hosting bill of 5000",
        raw_transaction={
            "description": "AWS cloud hosting monthly bill",
            "amount": 5000.0,
            "is_sale": False,
        },
    )
    res = graph.invoke(state)
    assert res["task_type"] == "bookkeeping"
    assert res["categorization"] is not None
    assert res["categorization"]["account_code"] == "5200"
    assert res["ledger_posted"] is True


def test_langgraph_reporting_workflow():
    ledger = DoubleEntryLedger()
    graph = create_munshi_graph(ledger=ledger)

    state = AgentState(query="Show me the trial balance report")
    res = graph.invoke(state)
    assert res["task_type"] == "reporting"
    assert res["report_output"] is not None
    assert "Trial Balance" in res["report_output"]["markdown"]
