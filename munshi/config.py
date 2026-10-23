# munshi/config.py
from __future__ import annotations
import os
import re
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, Any, Optional

def load_env_file(filepath: Optional[str | Path] = None) -> Dict[str, str]:
    """
    Native custom parser for .env files without requiring external python-dotenv.
    Correctly strips inline comments, handles single/double quotes, and sets os.environ.
    """
    env_vars: Dict[str, str] = {}
    if filepath is None:
        # Search current working directory, then repo root
        candidates = [Path.cwd() / ".env", Path(__file__).resolve().parent.parent / ".env"]
        for cand in candidates:
            if cand.exists():
                filepath = cand
                break

    if not filepath or not Path(filepath).exists():
        return env_vars

    path = Path(filepath)
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            # Match KEY=VALUE
            if "=" not in line:
                continue
            key, val = line.split("=", 1)
            key = key.strip()
            val = val.strip()

            # Handle quotes
            if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                val = val[1:-1]
            else:
                # Remove inline comment if present
                val = re.sub(r"\s+#.*$", "", val).strip()

            env_vars[key] = val
            # Only set in os.environ if not already defined
            if key not in os.environ:
                os.environ[key] = val

    return env_vars

# Automatically parse .env on import
load_env_file()

@dataclass
class MunshiConfig:
    company_name: str = field(
        default_factory=lambda: os.getenv("COMPANY_NAME", "Munshi Enterprise Technologies Pvt Ltd").strip('"\'')
    )
    company_gstin: str = field(
        default_factory=lambda: os.getenv("COMPANY_GSTIN", "27AABCM1234F1Z5").strip('"\'')
    )
    home_state_code: str = field(
        default_factory=lambda: os.getenv("HOME_STATE_CODE", "27").strip('"\'')
    )
    currency: str = "INR"
    hitl_threshold_inr: float = field(
        default_factory=lambda: float(os.getenv("HIGH_VALUE_THRESHOLD", os.getenv("HITL_APPROVAL_THRESHOLD", "50000.0")))
    )
    cash_limit_sec_40a3_inr: float = field(
        default_factory=lambda: float(os.getenv("CASH_EXPENSE_LIMIT_40A3", os.getenv("CASH_LIMIT_40A3", "10000.0")))
    )
    reconciliation_date_window_days: int = 3
    db_path: str = field(
        default_factory=lambda: os.getenv("MUNSHI_DB_PATH", os.getenv("DATABASE_PATH", str(Path(__file__).resolve().parent.parent / "data" / "munshi.db")))
    )
    api_key: str = field(
        default_factory=lambda: os.getenv("MUNSHI_API_KEY", "")
    )
    gemini_api_key: str = field(
        default_factory=lambda: os.getenv("GEMINI_API_KEY", "")
    )
    openai_api_key: str = field(
        default_factory=lambda: os.getenv("OPENAI_API_KEY", "")
    )
    model_name: str = field(
        default_factory=lambda: os.getenv("MUNSHI_MODEL", "gemini-2.5-flash")
    )
    port: int = field(
        default_factory=lambda: int(os.getenv("PORT", "8000"))
    )

def get_config() -> MunshiConfig:
    return MunshiConfig()

DEFAULT_CONFIG = get_config()
