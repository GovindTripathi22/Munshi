"""LangGraph shared state definition for Munshi multi-agent system."""

from typing import Annotated, Dict, Any, List, Optional
from pydantic import BaseModel, Field
import operator


class AgentState(BaseModel):
    """Global state flowing through LangGraph supervisor and worker agents."""
    
    # User input and conversation history
    query: str = ""
    messages: Annotated[List[Any], operator.add] = Field(default_factory=list)

    # Core routing control
    current_agent: str = "supervisor"
    next_agent: str = "END"
    task_type: str = ""  # "bookkeeping", "reconciliation", "gst", "audit", "reporting"

    # Transaction processing payload
    raw_transaction: Optional[Dict[str, Any]] = None
    categorization: Optional[Dict[str, Any]] = None
    gst_details: Optional[Dict[str, Any]] = None
    reconciliation_data: Optional[Dict[str, Any]] = None
    audit_findings: Optional[Dict[str, Any]] = None
    report_output: Optional[Dict[str, Any]] = None

    # Human-in-the-Loop (HITL) fields
    requires_human_approval: bool = False
    approval_reason: Optional[str] = None
    human_decision: Optional[str] = None  # "APPROVED", "REJECTED"
    human_feedback: Optional[str] = None

    # Ledger commitment status
    transaction_id: Optional[str] = None
    ledger_posted: bool = False
    errors: List[str] = Field(default_factory=list)
