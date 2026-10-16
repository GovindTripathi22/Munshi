# munshi/evaluation/benchmark.py
from typing import Dict, Any
from ..graph import MunshiOrchestrator
from .synthetic_data import generate_synthetic_sme_dataset

def run_munshi_benchmark() -> Dict[str, Any]:
    orch = MunshiOrchestrator()
    dataset = generate_synthetic_sme_dataset()
    balanced_ok = 0
    hitl_ok = 0

    for row in dataset:
        res = orch.process_transaction(row["text"])
        if res["entry"].is_balanced == row["expected_balanced"]:
            balanced_ok += 1
        if res["requires_hitl"] == row["expected_hitl"]:
            hitl_ok += 1

    total = len(dataset)
    return {
        "total_samples": total,
        "double_entry_balance_accuracy": round((balanced_ok / total) * 100, 2),
        "hitl_governance_accuracy": round((hitl_ok / total) * 100, 2),
        "audit_chain_intact": orch.ledger.audit_trail.verify_integrity(),
    }

run_benchmark = run_munshi_benchmark

