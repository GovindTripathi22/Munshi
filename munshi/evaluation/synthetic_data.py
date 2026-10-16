# munshi/evaluation/synthetic_data.py
from typing import List, Dict, Any

def generate_synthetic_sme_dataset() -> List[Dict[str, Any]]:
    return [
        {"text": "Owner capital infusion of ₹5,00,000 via NEFT", "expected_balanced": True, "expected_hitl": False},
        {"text": "Sold SaaS subscription to Bengaluru client for ₹2,00,000", "expected_balanced": True, "expected_hitl": False},
        {"text": "Paid office rent ₹40,000 to Mumbai landlord", "expected_balanced": True, "expected_hitl": False},
        {"text": "Paid ₹8,000 for team restaurant dinner catering", "expected_balanced": True, "expected_hitl": False},
        {"text": "Purchased MacBook laptop for ₹1,50,000", "expected_balanced": True, "expected_hitl": True},
        {"text": "Paid cash ₹15,000 for urgent office repairs", "expected_balanced": True, "expected_hitl": True},
    ]

generate_synthetic_dataset = generate_synthetic_sme_dataset

