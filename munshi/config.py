"""Configuration settings for Munshi multi-agent system."""

import os
from decimal import Decimal
from typing import Dict, Set
from pydantic import BaseModel, Field, ConfigDict

# Indian State GST Codes (Standard 2-digit prefixes)
INDIAN_STATE_GST_CODES: Dict[str, str] = {
    "01": "JAMMU AND KASHMIR",
    "02": "HIMACHAL PRADESH",
    "03": "PUNJAB",
    "04": "CHANDIGARH",
    "05": "UTTARAKHAND",
    "06": "HARYANA",
    "07": "DELHI",
    "08": "RAJASTHAN",
    "09": "UTTAR PRADESH",
    "10": "BIHAR",
    "19": "WEST BENGAL",
    "24": "GUJARAT",
    "27": "MAHARASHTRA",
    "29": "KARNATAKA",
    "32": "KERALA",
    "33": "TAMIL NADU",
    "36": "TELANGANA",
    "37": "ANDHRA PRADESH",
}

# Standard Indian GST Rates
VALID_GST_RATES: Set[Decimal] = {
    Decimal("0.00"),
    Decimal("0.05"),
    Decimal("0.12"),
    Decimal("0.18"),
    Decimal("0.28"),
}


class MunshiConfig(BaseModel):
    """System configuration parameters."""
    
    # Financial entity settings
    company_name: str = Field(default="Munshi Enterprises Pvt Ltd")
    home_state_code: str = Field(default="27", description="Home GST State Code (e.g. 27 for Maharashtra)")
    gstin: str = Field(default="27AAAAA0000A1Z5", description="Company GSTIN")
    currency: str = Field(default="INR")

    # Safety & Human-in-the-Loop (HITL) Thresholds
    high_value_approval_threshold: Decimal = Field(
        default=Decimal("50000.00"),
        description="Transactions exceeding this value require human approval"
    )
    low_confidence_threshold: float = Field(
        default=0.75,
        description="Categorization confidence below this threshold triggers human review"
    )
    auto_approve_reconciliation_confidence: float = Field(
        default=0.90,
        description="Reconciliation match score required for automatic clearing"
    )

    # Database
    db_path: str = Field(default="munshi_ledger.db")

    # Model settings
    model_name: str = Field(default=os.getenv("MUNSHI_MODEL", "gemini-2.5-flash"))
    api_key: str = Field(default_factory=lambda: os.getenv("GEMINI_API_KEY", ""))

    model_config = ConfigDict(arbitrary_types_allowed=True)
