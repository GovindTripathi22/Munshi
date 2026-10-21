# tests/test_edge_cases.py
import pytest
from munshi.ledger.models import JournalLine, JournalEntry, BankStatementLine, round_money
from munshi.ledger.engine import LedgerEngine
from munshi.ledger.audit_trail import AuditTrail
from munshi.agents.gst import GSTAgent
from munshi.agents.bookkeeper import BookkeeperAgent
from munshi.agents.auditor import AuditorAgent
from munshi.agents.reconciliation import ReconciliationAgent
from munshi.graph import MunshiOrchestrator

def test_ledger_models_edge_cases():
    # Negative amounts raise ValueError
    with pytest.raises(ValueError, match="non-negative"):
        JournalLine("1010", "Bank", debit=-100, credit=0)

    with pytest.raises(ValueError, match="non-negative"):
        JournalLine("1010", "Bank", debit=0, credit=-50)

    # Both debit and credit > 0 raises ValueError
    with pytest.raises(ValueError, match="both debit and credit > 0"):
        JournalLine("1010", "Bank", debit=100, credit=100)

    # Single line journal entry raises ValueError
    with pytest.raises(ValueError, match="at least 2 lines"):
        je = JournalEntry("JE-1", "2026-10-01", "Single line", [
            JournalLine("1010", "Bank", debit=100, credit=0)
        ])
        je.validate()

    # Zero amount journal entry is unbalanced
    je_zero = JournalEntry("JE-0", "2026-10-01", "Zero amount", [
        JournalLine("1010", "Bank", debit=0, credit=0),
        JournalLine("3000", "Capital", debit=0, credit=0),
    ])
    assert je_zero.is_balanced is False
    with pytest.raises(ValueError):
        je_zero.validate()

def test_audit_trail_tamper_detection():
    trail = AuditTrail()
    assert trail.verify_integrity() is True

    # Add blocks
    r1 = trail.append("POST", "JE-1", {"amount": 1000})
    r2 = trail.append("POST", "JE-2", {"amount": 2000})
    assert trail.verify_integrity() is True

    # Tamper payload of r1
    trail.records[0].payload["amount"] = 9999
    assert trail.verify_integrity() is False

    # Restore and tamper prev_hash of r2
    trail.records[0].payload["amount"] = 1000
    trail.records[1].prev_hash = "bad_hash"
    assert trail.verify_integrity() is False

def test_gst_validation_and_slabs():
    gst = GSTAgent(home_state_code="27")

    # Empty and invalid GSTINs
    assert gst.validate_gstin("")["valid"] is False
    assert gst.validate_gstin("INVALID123")["valid"] is False
    assert gst.validate_gstin("27ABCDE1234F1Z")["valid"] is False  # 14 chars

    # Lowercase valid GSTIN should normalize and be valid
    v = gst.validate_gstin("27aabcm1234f1z5")
    assert v["valid"] is True
    assert v["state_code"] == "27"
    assert v["state_name"] == "Maharashtra"
    assert v["pan"] == "AABCM1234F"

    # Blocked ITC categories
    for cat in ["food", "catering", "restaurant", "club", "personal_vehicle"]:
        res = gst.compute_gst_split(10000, 18, category=cat)
        assert res["sec_17_5_blocked"] is True
        assert res["itc_eligible"] is False

    # Exempt 0% tax
    exempt = gst.compute_gst_split(10000, 0)
    assert exempt["total_gst"] == 0.0
    assert exempt["gross_total"] == 10000.0

def test_bookkeeper_edge_cases():
    bk = BookkeeperAgent(hitl_threshold=50000.0)

    # Empty prompt fallback
    je_empty = bk.parse_and_create_entry("")
    assert je_empty.is_balanced is True

    # Crore values
    je_cr = bk.parse_and_create_entry("Promoter capital infusion of 2.5 crore via bank")
    assert je_cr.is_balanced is True
    assert je_cr.total_debit == 25000000.0

    # Lakh values
    je_lakh = bk.parse_and_create_entry("Sold SaaS subscription for 3.5 lakhs in Karnataka")
    assert je_lakh.is_balanced is True
    assert je_lakh.taxable_value == 350000.0
    assert je_lakh.igst == 63000.0  # 18% of 3.5L

    # Cash limit > 10,000 u/s 40A(3)
    je_cash = bk.parse_and_create_entry("Paid cash ₹12,000 for office supplies")
    assert je_cash.payment_mode == "CASH"
    assert je_cash.status == "PENDING_HITL"

    # HITL gate on outflows > 50,000
    je_high = bk.parse_and_create_entry("Purchased cloud servers for ₹75,000 via bank")
    assert je_high.status == "PENDING_HITL"

    # Revenue > 50,000 does NOT get blocked by expense HITL gate
    je_rev = bk.parse_and_create_entry("Sold SaaS license to client for ₹1,00,000")
    assert je_rev.status == "POSTED"

def test_hitl_rejection_workflow():
    engine = LedgerEngine()
    bk = BookkeeperAgent(hitl_threshold=50000.0)
    je = bk.parse_and_create_entry("Purchased high-end workstation for ₹1,20,000")
    engine.post_entry(je)

    assert je.status == "PENDING_HITL"
    assert len(engine.posted_entries()) == 0

    # Reject entry
    rejected = engine.reject_hitl_entry(je.entry_id, "Budget unapproved")
    assert rejected is not None
    assert rejected.status == "REJECTED"
    assert len(engine.posted_entries()) == 0
    assert engine.audit_trail.records[-1].action == "HITL_REJECTED"

def test_reconciliation_edge_cases():
    recon = ReconciliationAgent(date_tolerance_days=3)
    # Empty lists
    res_empty = recon.reconcile([], [])
    assert res_empty["matched_count"] == 0
    assert res_empty["unmatched_bank_count"] == 0

    # Bank charge adjustment entry creation
    bline = BankStatementLine("BNK-FEE", "2026-10-15", "MDR Debit Fee", debit=350.0)
    adj = recon.create_adjustment_entry_for_bank_charge(bline)
    assert adj.is_balanced is True
    assert adj.total_debit == 350.0
    assert any(l.account_code == "5600" for l in adj.lines)

def test_auditor_tamper_flag():
    orch = MunshiOrchestrator()
    orch.process_transaction("Owner capital infusion of ₹1,00,000 via NEFT")
    orch.process_transaction("Sold SaaS to client for ₹50,000")

    # Verify no tamper initially
    flags = orch.auditor.audit_entries(orch.ledger.entries, orch.ledger.audit_trail)
    assert not any(f.flag_id == "FLAG-CHAIN-TAMPER" for f in flags)

    # Tamper with ledger audit trail
    orch.ledger.audit_trail.records[0].payload["date"] = "1999-01-01"
    flags_tampered = orch.auditor.audit_entries(orch.ledger.entries, orch.ledger.audit_trail)
    assert any(f.flag_id == "FLAG-CHAIN-TAMPER" for f in flags_tampered)
    assert any(f.severity == "CRITICAL" for f in flags_tampered)

def test_statutory_section_49_gst_setoff():
    gst_agent = GSTAgent(home_state_code="27")
    # Entry with Output CGST ₹10,000, Output SGST ₹0, Input CGST ₹0, Input SGST ₹10,000
    # Under Sec 49(5)(f), SGST cannot offset CGST! Net payable must be ₹10,000 CGST!
    je_out = JournalEntry(
        entry_id="JE-G1",
        date="2026-10-01",
        narration="Intra-state sales partial CGST",
        status="POSTED",
        lines=[
            JournalLine("1010", "Bank", debit=10000, credit=0),
            JournalLine("2110", "Output CGST Payable", debit=0, credit=10000),
        ],
    )
    je_in = JournalEntry(
        entry_id="JE-G2",
        date="2026-10-02",
        narration="Intra-state purchase SGST credit",
        status="POSTED",
        lines=[
            JournalLine("1220", "Input SGST Receivable", debit=10000, credit=0),
            JournalLine("1010", "Bank", debit=0, credit=10000),
        ],
    )
    summary = gst_agent.generate_gstr3b_summary([je_out, je_in])
    # Total output = 10,000, total itc = 10,000, BUT cross-offset is legally barred:
    assert summary["net_gst_payable"] == 10000.0
    assert summary["net_payable_breakdown"]["cgst"] == 10000.0
    assert summary["itc_credit_carry_forward"] == 10000.0
    assert summary["itc_carry_forward_breakdown"]["sgst"] == 10000.0

def test_orchestrator_conditional_routing_no_ledger_pollution():
    orch = MunshiOrchestrator()
    assert len(orch.ledger.entries) == 0

    # Query for audit report
    res_audit = orch.process_transaction("Show audit report")
    assert res_audit["intent"] == "AUDIT"
    assert res_audit["entry"] is None
    assert len(orch.ledger.entries) == 0

    # Query for trial balance report
    res_report = orch.process_transaction("Generate trial balance and P&L report")
    assert res_report["intent"] == "REPORT"
    assert res_report["entry"] is None
    assert len(orch.ledger.entries) == 0

    # Post real bookkeeping transaction
    res_je = orch.process_transaction("Sold SaaS subscription to Bengaluru client for ₹50,000")
    assert res_je["intent"] == "BOOKKEEPING"
    assert res_je["entry"] is not None
    assert len(orch.ledger.entries) == 1

