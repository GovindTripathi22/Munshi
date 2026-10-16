# tests/test_langgraph_flow.py
from munshi.graph import build_munshi_graph
from munshi.evaluation.benchmark import run_munshi_benchmark

def test_end_to_end_orchestrator_and_benchmark():
    graph = build_munshi_graph()
    res = graph.process_transaction("Sold SaaS license to Bengaluru client for ₹1,00,000")
    assert res["trial_balance"]["is_balanced"] is True
    assert res["gstr3b"]["output_tax"]["igst"] == 18000.0

    bench = run_munshi_benchmark()
    assert bench["double_entry_balance_accuracy"] == 100.0
    assert bench["audit_chain_intact"] is True
