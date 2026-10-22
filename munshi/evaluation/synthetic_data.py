# munshi/evaluation/synthetic_data.py
from typing import List, Dict, Any, Optional

def generate_synthetic_sme_dataset(output_path: Optional[Any] = None) -> List[Dict[str, Any]]:
    return [
        {"text": "Owner capital infusion of INR 500000 via NEFT", "expected_balanced": True, "expected_hitl": False},
        {"text": "Sold SaaS subscription to Bengaluru client for INR 200000", "expected_balanced": True, "expected_hitl": False},
        {"text": "Paid office rent INR 40000 to Mumbai landlord", "expected_balanced": True, "expected_hitl": False},
        {"text": "Paid INR 8000 for team restaurant dinner catering", "expected_balanced": True, "expected_hitl": False},
        {"text": "Purchased MacBook laptop for INR 150000", "expected_balanced": True, "expected_hitl": True},
        {"text": "Paid cash INR 15000 for urgent office repairs", "expected_balanced": True, "expected_hitl": True},
    ]

generate_synthetic_dataset = generate_synthetic_sme_dataset
