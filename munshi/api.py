# munshi/api.py
"""
Production Multi-Agent Indian Accounting, GST, Reconciliation & Audit REST API.
Built with FastAPI, LangGraph, and Uvicorn.
"""
from __future__ import annotations

import os
import uuid
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, RedirectResponse
from pydantic import BaseModel, Field

from munshi.graph import MunshiOrchestrator, build_munshi_graph
from munshi.ledger.models import BankStatementLine
from munshi.evaluation.benchmark import run_munshi_benchmark

app = FastAPI(
    title="Munshi API",
    description="Autonomous Multi-Agent Indian Accounting, GST, Reconciliation & Forensic Audit Engine",
    version="1.0.0",
)

# Enable CORS for external frontends and dashboards
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global in-memory orchestrator sessions keyed by thread_id
_SESSIONS: Dict[str, MunshiOrchestrator] = {}

def get_or_create_orchestrator(thread_id: str = "default") -> MunshiOrchestrator:
    if thread_id not in _SESSIONS:
        _SESSIONS[thread_id] = build_munshi_graph()
    return _SESSIONS[thread_id]

def verify_api_key(x_api_key: Optional[str] = Header(default=None)) -> None:
    expected = os.getenv("MUNSHI_API_KEY", "")
    if expected and x_api_key != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing X-API-Key header",
        )

# ---------------------------------------------------------
# Request & Response Schemas
# ---------------------------------------------------------
class WorkflowRequest(BaseModel):
    thread_id: Optional[str] = None
    prompt: Optional[str] = Field(default=None, description="Natural language transaction prompt")
    raw_input: Optional[str] = None
    date: Optional[str] = "2026-10-16"
    transactions: Optional[List[Dict[str, Any]]] = None
    bank_statement: Optional[List[Dict[str, Any]]] = None
    hitl_approved: Optional[bool] = None

class HITLResumeRequest(BaseModel):
    approved: bool
    entry_id: Optional[str] = None
    reviewer_notes: Optional[str] = None

# ---------------------------------------------------------
# REST API Endpoints
# ---------------------------------------------------------
@app.get("/health")
@app.get("/")
def health() -> Dict[str, Any]:
    return {
        "status": "healthy",
        "service": "munshi",
        "version": "1.0.0",
        "features": [
            "Double-Entry General Ledger",
            "Indian GST Sec 49 / 17(5) Rules",
            "Bank Statement 3-Factor Reconciliation",
            "Sec 40A(3) & 194C/J Audit Engine",
            "SHA-256 Tamper-Evident Hash Chain",
            "Model Context Protocol (MCP) Ready",
        ],
    }

@app.post("/v1/workflows/run", dependencies=[Depends(verify_api_key)])
def run_workflow(req: WorkflowRequest) -> Dict[str, Any]:
    thread_id = req.thread_id or str(uuid.uuid4())
    orch = get_or_create_orchestrator(thread_id)

    bank_lines = []
    if req.bank_statement:
        for idx, row in enumerate(req.bank_statement):
            amt = float(row.get("amount", 0.0))
            direction = str(row.get("direction", "DEBIT")).upper()
            dr = amt if direction == "DEBIT" else 0.0
            cr = amt if direction == "CREDIT" else 0.0
            bank_lines.append(
                BankStatementLine(
                    line_id=str(row.get("tx_id", f"BNK-{idx+1:03d}")),
                    date=str(row.get("date", req.date or "2026-10-16")),
                    description=str(row.get("description", "Bank Transaction")),
                    debit=dr,
                    credit=cr,
                    utr=row.get("reference") or row.get("utr"),
                )
            )

    text_input = req.prompt or req.raw_input
    if text_input:
        res = orch.process_transaction(text_input, date=req.date or "2026-10-16", bank_lines=bank_lines)
    elif req.transactions:
        # Process list of structured or unstructured transactions
        last_res = {}
        for tx in req.transactions:
            if isinstance(tx, dict) and "description" in tx and "amount" in tx:
                prompt_line = f"{tx.get('description')} for INR {tx.get('amount')}"
            else:
                prompt_line = str(tx)
            last_res = orch.process_transaction(prompt_line, date=req.date or "2026-10-16", bank_lines=bank_lines)
        res = last_res
    else:
        # Full reporting close
        close_res = orch.run_full_close(bank_lines=bank_lines)
        return {
            "thread_id": thread_id,
            "status": "COMPLETED",
            "state": close_res,
        }

    if res.get("entry"):
        entry_data = asdict(res["entry"])
        entry_data["total_debit"] = res["entry"].total_debit
        entry_data["total_credit"] = res["entry"].total_credit
        entry_data["is_balanced"] = res["entry"].is_balanced
    else:
        entry_data = None
    audit_flags_data = [asdict(f) if hasattr(f, "__dataclass_fields__") else f for f in res.get("audit_flags", [])]

    return {
        "thread_id": thread_id,
        "status": "AWAITING_HITL_APPROVAL" if res.get("requires_hitl") else "COMPLETED",
        "requires_hitl": res.get("requires_hitl", False),
        "intent": res.get("intent"),
        "entry": entry_data,
        "trial_balance": res.get("trial_balance"),
        "profit_and_loss": res.get("profit_and_loss"),
        "balance_sheet": res.get("balance_sheet"),
        "gstr3b": res.get("gstr3b"),
        "reconciliation": res.get("reconciliation"),
        "audit_flags": audit_flags_data,
        "report_markdown": res.get("report_markdown"),
    }

@app.post("/v1/workflows/{thread_id}/hitl", dependencies=[Depends(verify_api_key)])
def resume_hitl(thread_id: str, decision: HITLResumeRequest) -> Dict[str, Any]:
    orch = get_or_create_orchestrator(thread_id)
    entry_id = decision.entry_id

    # If no specific entry_id supplied, find first pending voucher
    if not entry_id:
        pending = [e for e in orch.ledger.entries if e.status == "PENDING_HITL"]
        if pending:
            entry_id = pending[-1].entry_id

    if not entry_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No pending HITL voucher found.")

    if decision.approved:
        approved_entry = orch.ledger.approve_hitl_entry(entry_id)
        if not approved_entry:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Failed to approve voucher {entry_id}")
        return {
            "thread_id": thread_id,
            "entry_id": entry_id,
            "status": "APPROVED",
            "entry": asdict(approved_entry),
            "reviewer_notes": decision.reviewer_notes,
            "trial_balance": orch.ledger.get_trial_balance(),
        }
    else:
        # Mark as rejected
        for e in orch.ledger.entries:
            if e.entry_id == entry_id:
                e.status = "REJECTED"
        return {
            "thread_id": thread_id,
            "entry_id": entry_id,
            "status": "REJECTED",
            "reviewer_notes": decision.reviewer_notes,
        }

@app.get("/v1/ledger/trial-balance")
def get_trial_balance(thread_id: str = "default") -> Dict[str, Any]:
    orch = get_or_create_orchestrator(thread_id)
    return orch.ledger.get_trial_balance()

@app.get("/v1/ledger/pnl")
def get_pnl(thread_id: str = "default") -> Dict[str, Any]:
    orch = get_or_create_orchestrator(thread_id)
    return orch.ledger.get_profit_and_loss()

@app.get("/v1/ledger/balance-sheet")
def get_balance_sheet(thread_id: str = "default") -> Dict[str, Any]:
    orch = get_or_create_orchestrator(thread_id)
    return orch.ledger.get_balance_sheet()

@app.get("/v1/gst/gstr3b")
def get_gstr3b(thread_id: str = "default") -> Dict[str, Any]:
    orch = get_or_create_orchestrator(thread_id)
    return orch.gst_agent.generate_gstr3b_summary(orch.ledger.entries)

@app.get("/v1/audit/findings")
def get_audit_findings(thread_id: str = "default") -> Dict[str, Any]:
    orch = get_or_create_orchestrator(thread_id)
    flags = orch.auditor.audit_entries(orch.ledger.entries, orch.ledger.audit_trail)
    return {
        "audit_chain_valid": orch.ledger.audit_trail.verify_integrity(),
        "total_flags": len(flags),
        "flags": [asdict(f) for f in flags],
    }

@app.get("/v1/benchmark")
def run_benchmark_endpoint() -> Dict[str, Any]:
    return run_munshi_benchmark()

@app.get("/ui")
@app.get("/app")
def get_dashboard_ui():
    index_file = frontend_dist / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    return {"message": "Frontend not yet built. Static build located in frontend/dist/"}

# Static Files: Mount pre-built React frontend if dist/ exists
frontend_dist = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if frontend_dist.exists() and (frontend_dist / "index.html").exists():
    app.mount("/dashboard", StaticFiles(directory=str(frontend_dist), html=True), name="dashboard")
