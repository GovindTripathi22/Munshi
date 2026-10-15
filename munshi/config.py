# munshi/config.py
import os
from dataclasses import dataclass

@dataclass
class MunshiConfig:
    company_name: str = "Munshi Enterprise Technologies Pvt Ltd"
    company_gstin: str = "27AABCM1234F1Z5"
    home_state_code: str = "27"  # Maharashtra
    currency: str = "INR"
    hitl_threshold_inr: float = 50000.0
    cash_limit_sec_40a3_inr: float = 10000.0
    reconciliation_date_Window_days: int = 3
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    model_name: str = os.getenv("MUNSHI_MODEL", "gemini-2.5-flash")

DEFAULT_CONFIG = MunshiConfig()
