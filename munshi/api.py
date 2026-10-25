# munshi/api.py
"""
Production Multi-Agent Indian Accounting, GST, Reconciliation & Audit REST API.
Built with FastAPI, LangGraph, and Uvicorn.
"""
from __future__ import annotations

import os
import uuid
import threading
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, Header, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, RedirectResponse
from pydantic import BaseModel, Field

from munshi.config import get_config
from munshi.ledger.engine import LedgerEngine
from munshi.graph import MunshiOrchestrator, build_munshi_graph
from munshi.ledger.models import BankStatementLine
from munshi.evaluation.benchmark import run_munshi_benchmark
from munshi.agents.gst import normalize_date

app = FastAPI(
    title="Munshi API",
    description="Autonomous Multi-Agent Indian Accounting, GST, Reconciliation & Forensic Audit Engine",
    version="1.0.0",
)

# Secure CORS: disallow wildcard credential reflection
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Shared Singleton Ledger Engine to guarantee database consistency and prevent memory leaks
_SHARED_ENGINE: Optional[LedgerEngine] = None
_ENGINE_LOCK = threading.Lock()

def get_shared_engine() -> LedgerEngine:
    global _SHARED_ENGINE
    with _ENGINE_LOCK:
        if _SHARED_ENGINE is None:
            cfg = get_config()
            _SHARED_ENGINE = LedgerEngine(db_path=cfg.db_path)
        return _SHARED_ENGINE

_SESSIONS: Dict[str, MunshiOrchestrator] = {}
_SESSIONS_LOCK = threading.Lock()

def get_or_create_orchestrator(thread_id: str = "default") -> MunshiOrchestrator:
    with _SESSIONS_LOCK:
        if thread_id not in _SESSIONS:
            cfg = get_config()
            _SESSIONS[thread_id] = build_munshi_graph(
                home_state_code=cfg.home_state_code,
                hitl_threshold=cfg.hitl_threshold_inr,
                ledger=get_shared_engine(),
            )
        return _SESSIONS[thread_id]

def verify_api_key(x_api_key: Optional[str] = Header(default=None, alias="X-API-Key")) -> str:
    cfg = get_config()
    expected = cfg.api_key
    if expected:
        if not x_api_key or x_api_key.strip() != expected.strip():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Unauthorized: Invalid or missing X-API-Key header",
            )
        return x_api_key
    return "anonymous"

# ---------------------------------------------------------
# Request & Response Schemas
# ---------------------------------------------------------
class WorkflowRequest(BaseModel):
    thread_id: Optional[str] = None
    prompt: Optional[str] = Field(default=None, description="Natural language transaction prompt")
    raw_input: Optional[str] = None
    date: Optional[str] = None
    amount: Optional[float] = None
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
@app.get("/api/health")
@app.get("/")
def health() -> Dict[str, Any]:
    engine = get_shared_engine()
    integrity = engine.verify_ledger_integrity()
    if not integrity["verified"]:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "status": "unhealthy",
                "error": "Tamper detected: Ledger cryptographic verification failed",
                "details": integrity["errors"],
            },
        )
    return {
        "status": "healthy",
        "service": "munshi",
        "version": "1.0.0",
        "database_verified": True,
        "features": [
            "Double-Entry General Ledger with SQLite Persistence",
            "Indian GST Sec 49 / 17(5) Rules & 2025 Reforms",
            "Bank Statement 3-Factor Reconciliation",
            "Sec 40A(3) & 194C/J Audit Engine",
            "SHA-256 Tamper-Evident Hash Chain",
            "Model Context Protocol (MCP) Ready",
        ],
    }

@app.post("/v1/workflows/run", dependencies=[Depends(verify_api_key)])
@app.post("/api/v1/workflows/run", dependencies=[Depends(verify_api_key)])
def run_workflow(req: WorkflowRequest) -> Dict[str, Any]:
    thread_id = req.thread_id or str(uuid.uuid4())
    orch = get_or_create_orchestrator(thread_id)
    req_date = normalize_date(req.date)

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
                    date=str(row.get("date", req_date)),
                    description=str(row.get("description", "Bank Transaction")),
                    debit=dr,
                    credit=cr,
                    utr=row.get("reference") or row.get("utr"),
                )
            )

    text_input = req.prompt or req.raw_input
    if text_input:
        res = orch.process_transaction(text_input, date=req_date, amount=req.amount, bank_lines=bank_lines)
    elif req.transactions:
        last_res = {}
        for tx in req.transactions:
            if isinstance(tx, dict):
                tx_desc = tx.get("description") or str(tx)
                tx_amt = float(tx.get("amount")) if tx.get("amount") is not None else None
                tx_date = tx.get("date", req_date)
                last_res = orch.process_transaction(tx_desc, date=tx_date, amount=tx_amt, bank_lines=bank_lines)
            else:
                last_res = orch.process_transaction(str(tx), date=req_date, bank_lines=bank_lines)
        res = last_res
    else:
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
@app.post("/api/v1/workflows/{thread_id}/hitl", dependencies=[Depends(verify_api_key)])
def resume_hitl(
    thread_id: str,
    decision: HITLResumeRequest,
    caller_key: str = Depends(verify_api_key),
) -> Dict[str, Any]:
    orch = get_or_create_orchestrator(thread_id)
    entry_id = decision.entry_id

    if not entry_id:
        pending = [e for e in orch.ledger.entries if e.status == "PENDING_HITL"]
        if pending:
            entry_id = pending[-1].entry_id

    if not entry_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No pending HITL voucher found.")

    approver_name = f"user_{caller_key[:8]}" if caller_key != "anonymous" else "human_reviewer"

    if decision.approved:
        approved_entry = orch.ledger.approve_hitl_entry(entry_id, approver=approver_name)
        if not approved_entry:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot approve voucher {entry_id}: entry not found or not in PENDING_HITL status."
            )
        return {
            "thread_id": thread_id,
            "entry_id": entry_id,
            "status": "APPROVED",
            "entry": asdict(approved_entry),
            "reviewer_notes": decision.reviewer_notes,
            "trial_balance": orch.ledger.get_trial_balance(),
        }
    else:
        rejected_entry = orch.ledger.reject_hitl_entry(
            entry_id,
            reason=decision.reviewer_notes or "Rejected by reviewer",
            rejector=approver_name,
        )
        if not rejected_entry:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot reject voucher {entry_id}: entry not found or not in PENDING_HITL status."
            )
        return {
            "thread_id": thread_id,
            "entry_id": entry_id,
            "status": "REJECTED",
            "entry": asdict(rejected_entry),
            "reviewer_notes": decision.reviewer_notes,
            "trial_balance": orch.ledger.get_trial_balance(),
        }

@app.get("/v1/ledger/trial-balance", dependencies=[Depends(verify_api_key)])
@app.get("/api/v1/ledger/trial-balance", dependencies=[Depends(verify_api_key)])
def get_trial_balance(thread_id: str = "default") -> Dict[str, Any]:
    orch = get_or_create_orchestrator(thread_id)
    return orch.ledger.get_trial_balance()

@app.get("/v1/ledger/pnl", dependencies=[Depends(verify_api_key)])
@app.get("/api/v1/ledger/pnl", dependencies=[Depends(verify_api_key)])
def get_pnl(thread_id: str = "default") -> Dict[str, Any]:
    orch = get_or_create_orchestrator(thread_id)
    return orch.ledger.get_profit_and_loss()

@app.get("/v1/ledger/balance-sheet", dependencies=[Depends(verify_api_key)])
@app.get("/api/v1/ledger/balance-sheet", dependencies=[Depends(verify_api_key)])
def get_balance_sheet(thread_id: str = "default") -> Dict[str, Any]:
    orch = get_or_create_orchestrator(thread_id)
    return orch.ledger.get_balance_sheet()

@app.get("/v1/gst/gstr3b", dependencies=[Depends(verify_api_key)])
@app.get("/api/v1/gst/gstr3b", dependencies=[Depends(verify_api_key)])
def get_gstr3b(thread_id: str = "default") -> Dict[str, Any]:
    orch = get_or_create_orchestrator(thread_id)
    return orch.gst_agent.generate_gstr3b_summary(orch.ledger.entries)

@app.get("/v1/audit/findings", dependencies=[Depends(verify_api_key)])
@app.get("/api/v1/audit/findings", dependencies=[Depends(verify_api_key)])
def get_audit_findings(thread_id: str = "default") -> Dict[str, Any]:
    orch = get_or_create_orchestrator(thread_id)
    flags = orch.auditor.audit_entries(orch.ledger.entries, orch.ledger.audit_trail)
    return {
        "audit_chain_valid": orch.ledger.audit_trail.verify_integrity(),
        "total_flags": len(flags),
        "flags": [asdict(f) for f in flags],
    }

@app.get("/v1/benchmark", dependencies=[Depends(verify_api_key)])
@app.get("/api/v1/benchmark", dependencies=[Depends(verify_api_key)])
def run_benchmark_endpoint() -> Dict[str, Any]:
    return run_munshi_benchmark()

# ---------------------------------------------------------
# Web UI & Static Frontend Routes
# ---------------------------------------------------------
frontend_dist = Path(__file__).resolve().parent.parent / "frontend" / "dist"

@app.get("/index.html")
@app.get("/ui")
@app.get("/app")
def get_dashboard_ui():
    index_file = frontend_dist / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    return {"message": "Munshi API active. Frontend static build located at frontend/dist/"}

if frontend_dist.exists():
    assets_dir = frontend_dist / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")
    if (frontend_dist / "index.html").exists():
        app.mount("/dashboard", StaticFiles(directory=str(frontend_dist), html=True), name="dashboard")
