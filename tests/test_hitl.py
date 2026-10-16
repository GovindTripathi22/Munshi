# tests/test_hitl.py
from munshi.graph import MunshiOrchestrator

def test_hitl_approval_lifecycle():
    orch = MunshiOrchestrator(hitl_threshold=50000.0)
    res = orch.process_transaction("Purchased server equipment for ₹1,00,000")
    entry_id = res["entry"].entry_id
    assert res["requires_hitl"] is True
    assert orch.ledger.get_trial_balance()["total_debit"] == 0.0

    orch.ledger.approve_hitl_entry(entry_id)
    assert orch.ledger.get_trial_balance()["total_debit"] == 118000.0
