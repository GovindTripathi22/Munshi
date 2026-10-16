# munshi/agents/state.py
from typing import TypedDict, List, Dict, Any, Optional
from ..ledger.models import JournalEntry, AuditFlag, BankStatementLine

class MunshiAgentState(TypedDict, total=False):
    raw_input: str
    date: str
    intent: str
    entry: Optional[JournalEntry]
    bank_lines: List[BankStatementLine]
    reconciliation: Dict[str, Any]
    gstr3b: Dict[str, Any]
    audit_flags: List[AuditFlag]
    requires_hitl: bool
    status: str
    trial_balance: Dict[str, Any]
    profit_and_loss: Dict[str, Any]
    balance_sheet: Dict[str, Any]
    report_markdown: str
