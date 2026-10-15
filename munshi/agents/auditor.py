# munshi/agents/auditor.py
from typing import List
from ..ledger.models import JournalEntry, AuditFlag
from ..ledger.audit_trail import AuditTrail

class AuditorAgent:
    def __init__(self, hitl_threshold: float = 50000.0, cash_limit: float = 10000.0):
        self.hitl_threshold = hitl_threshold
        self.cash_limit = cash_limit

    def audit_entries(self, entries: List[JournalEntry], audit_trail: AuditTrail | None = None) -> List[AuditFlag]:
        flags: List[AuditFlag] = []
        seen_signatures = {}

        if audit_trail and not audit_trail.verify_integrity():
            flags.append(
                AuditFlag(
                    flag_id="FLAG-CHAIN-TAMPER",
                    entry_id="SYSTEM",
                    severity="CRITICAL",
                    rule="SHA256_HASH_CHAIN",
                    detail="Cryptographic hash-chain integrity check failed! Ledger tampering detected.",
                    requires_hitl=True,
                )
            )

        for idx, entry in enumerate(entries):
            # 1. Section 40A(3) Income Tax Act: Cash expenditure > ₹10,000 in a day
            if entry.payment_mode == "CASH" and entry.total_debit > self.cash_limit:
                flags.append(
                    AuditFlag(
                        flag_id=f"FLAG-40A3-{idx+1}",
                        entry_id=entry.entry_id,
                        severity="CRITICAL",
                        rule="SEC_40A_3_CASH_LIMIT",
                        detail=f"Cash payment of ₹{entry.total_debit:,.2f} exceeds ₹{self.cash_limit:,.0f} limit u/s 40A(3) Income Tax Act.",
                        requires_hitl=True,
                    )
                )

            # 2. High-Value HITL Governance Check (> ₹50,000)
            is_capital_or_sales = any(l.account_code in ("3000", "4000", "4100") for l in entry.lines)
            if not is_capital_or_sales and entry.total_debit > self.hitl_threshold:
                flags.append(
                    AuditFlag(
                        flag_id=f"FLAG-HITL-{idx+1}",
                        entry_id=entry.entry_id,
                        severity="HIGH",
                        rule="HIGH_VALUE_HITL_GATE",
                        detail=f"High-value outflow ₹{entry.total_debit:,.2f} exceeds HITL threshold ₹{self.hitl_threshold:,.0f}.",
                        requires_hitl=True,
                    )
                )

            # 3. Duplicate Voucher / Double Payment Check
            sig = (entry.party.lower().strip(), entry.total_debit, entry.date)
            if sig in seen_signatures:
                prev_id = seen_signatures[sig]
                flags.append(
                    AuditFlag(
                        flag_id=f"FLAG-DUP-{idx+1}",
                        entry_id=entry.entry_id,
                        severity="HIGH",
                        rule="DUPLICATE_VOUCHER",
                        detail=f"Potential duplicate transaction with {prev_id} for {entry.party} (₹{entry.total_debit:,.2f}).",
                        requires_hitl=True,
                    )
                )
            else:
                seen_signatures[sig] = entry.entry_id

        return flags
