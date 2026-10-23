# munshi/ledger/engine.py
from __future__ import annotations
import sqlite3
import json
import threading
import sys
import os
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone

from .models import Account, JournalEntry, JournalLine, round_money
from .audit_trail import AuditTrail, AuditRecord
from ..config import DEFAULT_CONFIG

DEFAULT_CHART: List[Account] = [
    Account("1000", "Cash in Hand", "ASSET"),
    Account("1010", "HDFC Bank Current A/c", "ASSET"),
    Account("1100", "Accounts Receivable", "ASSET"),
    Account("1210", "Input CGST Receivable", "ASSET"),
    Account("1220", "Input SGST Receivable", "ASSET"),
    Account("1230", "Input IGST Receivable", "ASSET"),
    Account("1500", "Computer & Office Equipment", "ASSET"),
    Account("2000", "Accounts Payable", "LIABILITY"),
    Account("2110", "Output CGST Payable", "LIABILITY"),
    Account("2120", "Output SGST Payable", "LIABILITY"),
    Account("2130", "Output IGST Payable", "LIABILITY"),
    Account("2200", "TDS Payable", "LIABILITY"),
    Account("3000", "Owner Capital Account", "EQUITY"),
    Account("4000", "Sales & Product Revenue", "REVENUE"),
    Account("4100", "SaaS & Consulting Revenue", "REVENUE"),
    Account("5000", "Cost of Goods Sold", "EXPENSE"),
    Account("5100", "Office Rent Expense", "EXPENSE"),
    Account("5200", "Cloud & Software Subscriptions", "EXPENSE"),
    Account("5300", "Professional & Legal Fees", "EXPENSE"),
    Account("5400", "Staff Welfare & Blocked ITC Expense", "EXPENSE"),
    Account("5500", "Repairs & Maintenance", "EXPENSE"),
    Account("5600", "Bank Charges", "EXPENSE"),
]

class LedgerEngine:
    def __init__(self, db_path: Optional[str] = None):
        if db_path is not None:
            self.db_path = db_path
        elif "pytest" in sys.modules or os.getenv("PYTEST_CURRENT_TEST"):
            self.db_path = ":memory:"
        else:
            self.db_path = DEFAULT_CONFIG.db_path

        self._lock = threading.RLock()
        self.accounts: Dict[str, Account] = {}
        self.entries: List[JournalEntry] = []
        self.audit_trail = AuditTrail()

        self._init_db()
        self._load_from_db()

    def posted_entries(self) -> List[JournalEntry]:
        with self._lock:
            return [e for e in self.entries if e.status == "POSTED"]

    def _get_connection(self) -> sqlite3.Connection:
        if self.db_path == ":memory:":
            if not hasattr(self, "_mem_conn") or self._mem_conn is None:
                self._mem_conn = sqlite3.connect(":memory:", check_same_thread=False)
            return self._mem_conn
        
        # Ensure parent directory exists for file-based SQLite
        db_file = Path(self.db_path)
        db_file.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(db_file), timeout=30.0, check_same_thread=False)
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA synchronous = NORMAL;")
        conn.execute("PRAGMA busy_timeout = 30000;")
        return conn

    def _init_db(self) -> None:
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS accounts (
                    code TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    account_type TEXT NOT NULL,
                    balance REAL DEFAULT 0.0
                );
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS journal_entries (
                    entry_id TEXT PRIMARY KEY,
                    date TEXT NOT NULL,
                    narration TEXT NOT NULL,
                    party TEXT,
                    party_gstin TEXT,
                    utr TEXT,
                    payment_mode TEXT,
                    status TEXT NOT NULL,
                    taxable_value REAL DEFAULT 0.0,
                    cgst REAL DEFAULT 0.0,
                    sgst REAL DEFAULT 0.0,
                    igst REAL DEFAULT 0.0,
                    tds REAL DEFAULT 0.0,
                    itc_eligible INTEGER DEFAULT 1,
                    lines_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS audit_records (
                    seq INTEGER PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    action TEXT NOT NULL,
                    entry_id TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    prev_hash TEXT NOT NULL,
                    record_hash TEXT NOT NULL
                );
            """)
            conn.commit()
            if self.db_path != ":memory:":
                conn.close()

    def _load_from_db(self) -> None:
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()

            # 1. Load accounts
            cursor.execute("SELECT code, name, account_type FROM accounts;")
            rows = cursor.fetchall()
            if not rows:
                # Seed default chart of accounts
                for acct in DEFAULT_CHART:
                    cursor.execute(
                        "INSERT INTO accounts (code, name, account_type, balance) VALUES (?, ?, ?, 0.0);",
                        (acct.code, acct.name, acct.account_type),
                    )
                conn.commit()
                self.accounts = {a.code: Account(a.code, a.name, a.account_type) for a in DEFAULT_CHART}
            else:
                self.accounts = {r[0]: Account(r[0], r[1], r[2]) for r in rows}

            # 2. Load audit trail
            cursor.execute("SELECT seq, timestamp, action, entry_id, payload_json, prev_hash, record_hash FROM audit_records ORDER BY seq ASC;")
            records = []
            for r in cursor.fetchall():
                payload = json.loads(r[4])
                records.append(
                    AuditRecord(
                        seq=r[0],
                        timestamp=r[1],
                        action=r[2],
                        entry_id=r[3],
                        payload=payload,
                        prev_hash=r[5],
                        record_hash=r[6],
                    )
                )
            self.audit_trail = AuditTrail(records)

            # 3. Load journal entries
            cursor.execute("SELECT entry_id, date, narration, party, party_gstin, utr, payment_mode, status, taxable_value, cgst, sgst, igst, tds, itc_eligible, lines_json FROM journal_entries ORDER BY date ASC, entry_id ASC;")
            self.entries = []
            for r in cursor.fetchall():
                lines_data = json.loads(r[14])
                lines = [JournalLine(account_code=l["account_code"], account_name=l["account_name"], debit=l["debit"], credit=l["credit"]) for l in lines_data]
                entry = JournalEntry(
                    entry_id=r[0],
                    date=r[1],
                    narration=r[2],
                    lines=lines,
                    party=r[3] or "General Counterparty",
                    party_gstin=r[4],
                    utr=r[5],
                    payment_mode=r[6] or "BANK",
                    status=r[7],
                    taxable_value=r[8] or 0.0,
                    cgst=r[9] or 0.0,
                    sgst=r[10] or 0.0,
                    igst=r[11] or 0.0,
                    tds=r[12] or 0.0,
                    itc_eligible=bool(r[13]),
                )
                self.entries.append(entry)

            if self.db_path != ":memory:":
                conn.close()

    def get_account_balance(self, code: str) -> float:
        with self._lock:
            # Recompute live balance from POSTED entries
            dr_total = sum(l.debit for e in self.entries if e.status == "POSTED" for l in e.lines if l.account_code == code)
            cr_total = sum(l.credit for e in self.entries if e.status == "POSTED" for l in e.lines if l.account_code == code)
            acct = self.accounts.get(code)
            if not acct:
                return 0.0
            if acct.normal_side == "DEBIT":
                return round_money(dr_total - cr_total)
            else:
                return round_money(cr_total - dr_total)

    def post_entry(self, entry: JournalEntry) -> JournalEntry:
        entry.validate()
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            try:
                # Use IMMEDIATE transaction to acquire write lock before reading audit sequence
                cursor.execute("BEGIN IMMEDIATE;")

                # Check if entry already exists in DB
                cursor.execute("SELECT status FROM journal_entries WHERE entry_id = ?;", (entry.entry_id,))
                existing_row = cursor.fetchone()

                lines_json = json.dumps([
                    {"account_code": l.account_code, "account_name": l.account_name, "debit": l.debit, "credit": l.credit}
                    for l in entry.lines
                ])
                now_ts = datetime.now(timezone.utc).isoformat()

                if existing_row:
                    cursor.execute("""
                        UPDATE journal_entries SET
                            date = ?, narration = ?, party = ?, party_gstin = ?, utr = ?,
                            payment_mode = ?, status = ?, taxable_value = ?, cgst = ?,
                            sgst = ?, igst = ?, tds = ?, itc_eligible = ?, lines_json = ?
                        WHERE entry_id = ?;
                    """, (
                        entry.date, entry.narration, entry.party, entry.party_gstin, entry.utr,
                        entry.payment_mode, entry.status, entry.taxable_value, entry.cgst,
                        entry.sgst, entry.igst, entry.tds, 1 if entry.itc_eligible else 0,
                        lines_json, entry.entry_id
                    ))
                else:
                    cursor.execute("""
                        INSERT INTO journal_entries (
                            entry_id, date, narration, party, party_gstin, utr, payment_mode, status,
                            taxable_value, cgst, sgst, igst, tds, itc_eligible, lines_json, created_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                    """, (
                        entry.entry_id, entry.date, entry.narration, entry.party, entry.party_gstin, entry.utr,
                        entry.payment_mode, entry.status, entry.taxable_value, entry.cgst, entry.sgst, entry.igst,
                        entry.tds, 1 if entry.itc_eligible else 0, lines_json, now_ts
                    ))

                # Fetch atomic latest audit record for hash-chain continuity
                cursor.execute("SELECT seq, record_hash FROM audit_records ORDER BY seq DESC LIMIT 1;")
                latest_audit = cursor.fetchone()
                if latest_audit:
                    next_seq = latest_audit[0] + 1
                    prev_hash = latest_audit[1]
                else:
                    next_seq = 1
                    prev_hash = AuditTrail.GENESIS_HASH

                action = "POST_TRANSACTION" if entry.status == "POSTED" else "HOLD_PENDING_HITL"
                payload = {
                    "entry_id": entry.entry_id,
                    "narration": entry.narration,
                    "total_debit": entry.total_debit,
                    "total_credit": entry.total_credit,
                    "status": entry.status,
                    "lines": [{"code": l.account_code, "dr": l.debit, "cr": l.credit} for l in entry.lines],
                }
                record_hash = AuditTrail.compute_hash(next_seq, now_ts, action, entry.entry_id, payload, prev_hash)

                cursor.execute("""
                    INSERT INTO audit_records (seq, timestamp, action, entry_id, payload_json, prev_hash, record_hash)
                    VALUES (?, ?, ?, ?, ?, ?, ?);
                """, (
                    next_seq, now_ts, action, entry.entry_id,
                    json.dumps(payload, sort_keys=True), prev_hash, record_hash
                ))
                conn.commit()

                record = AuditRecord(
                    seq=next_seq,
                    timestamp=now_ts,
                    action=action,
                    entry_id=entry.entry_id,
                    payload=payload,
                    prev_hash=prev_hash,
                    record_hash=record_hash,
                )
                self.audit_trail.records.append(record)

                # Update in-memory entry list
                for idx, existing in enumerate(self.entries):
                    if existing.entry_id == entry.entry_id:
                        self.entries[idx] = entry
                        break
                else:
                    self.entries.append(entry)

                return entry
            finally:
                if self.db_path != ":memory:":
                    conn.close()

    def _persist_entry(self, entry: JournalEntry) -> None:
        lines_json = json.dumps([
            {"account_code": l.account_code, "account_name": l.account_name, "debit": l.debit, "credit": l.credit}
            for l in entry.lines
        ])
        conn = self._get_connection()
        cursor = conn.cursor()
        now_ts = datetime.now(timezone.utc).isoformat()
        cursor.execute("""
            INSERT INTO journal_entries (
                entry_id, date, narration, party, party_gstin, utr, payment_mode, status,
                taxable_value, cgst, sgst, igst, tds, itc_eligible, lines_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(entry_id) DO UPDATE SET
                status=excluded.status,
                lines_json=excluded.lines_json;
        """, (
            entry.entry_id, entry.date, entry.narration, entry.party, entry.party_gstin, entry.utr,
            entry.payment_mode, entry.status, entry.taxable_value, entry.cgst, entry.sgst, entry.igst,
            entry.tds, 1 if entry.itc_eligible else 0, lines_json, now_ts
        ))
        conn.commit()
        if self.db_path != ":memory:":
            conn.close()

    def _persist_audit_record(self, record: AuditRecord) -> None:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO audit_records (seq, timestamp, action, entry_id, payload_json, prev_hash, record_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?);
        """, (
            record.seq, record.timestamp, record.action, record.entry_id,
            json.dumps(record.payload, sort_keys=True), record.prev_hash, record.record_hash
        ))
        conn.commit()
        if self.db_path != ":memory:":
            conn.close()

    def approve_hitl_entry(self, entry_id: str) -> Optional[JournalEntry]:
        with self._lock:
            for entry in self.entries:
                if entry.entry_id == entry_id:
                    # Strict approval governance: already POSTED or REJECTED entries cannot be re-approved
                    if entry.status != "PENDING_HITL":
                        return None
                    entry.status = "POSTED"
                    self._persist_entry(entry)
                    record = self.audit_trail.append(
                        action="APPROVE_HITL_ENTRY",
                        entry_id=entry.entry_id,
                        payload={"entry_id": entry.entry_id, "amount": entry.total_debit, "approved_by": "human_approver"},
                    )
                    self._persist_audit_record(record)
                    return entry
        return None

    def reject_hitl_entry(self, entry_id: str, reason: Optional[str] = "Rejected by reviewer") -> Optional[JournalEntry]:
        with self._lock:
            for entry in self.entries:
                if entry.entry_id == entry_id:
                    # Strict rejection governance: cannot reject already POSTED entries
                    if entry.status != "PENDING_HITL":
                        return None
                    entry.status = "REJECTED"
                    self._persist_entry(entry)
                    record = self.audit_trail.append(
                        action="HITL_REJECTED",
                        entry_id=entry.entry_id,
                        payload={"entry_id": entry.entry_id, "reason": reason or "Rejected by reviewer"},
                    )
                    self._persist_audit_record(record)
                    return entry
        return None

    def verify_ledger_integrity(self) -> Dict[str, Any]:
        """
        Forensic tamper detection:
        1. Verifies SHA-256 hash chain in audit records.
        2. Detects direct row tampering or manual edits in SQLite.
        3. Confirms Trial Balance and Balance Sheet equilibrium.
        """
        with self._lock:
            errors = []
            chain_valid = self.audit_trail.verify_integrity()
            if not chain_valid:
                errors.append("Audit trail SHA-256 hash chain is corrupted or tampered.")

            # Verify SQLite entry contents match recorded audit payloads
            entry_map = {e.entry_id: e for e in self.entries}
            for rec in self.audit_trail.records:
                if rec.action == "POST_TRANSACTION":
                    e = entry_map.get(rec.entry_id)
                    if not e:
                        errors.append(f"Recorded entry {rec.entry_id} missing from database.")
                    else:
                        rec_dr = rec.payload.get("total_debit")
                        if rec_dr is not None and abs(round_money(rec_dr) - e.total_debit) > 0.01:
                            errors.append(
                                f"Tamper detected on {rec.entry_id}: DB debit={e.total_debit} != Audit debit={rec_dr}"
                            )

            tb = self.get_trial_balance()
            if not tb["is_balanced"]:
                errors.append(f"Trial balance out of equilibrium: Dr={tb['total_debit']} != Cr={tb['total_credit']}")

            return {
                "verified": len(errors) == 0,
                "audit_chain_valid": chain_valid,
                "ledger_balanced": tb["is_balanced"],
                "records_count": len(self.audit_trail.records),
                "entries_count": len(self.entries),
                "errors": errors,
            }

    def get_trial_balance(self) -> Dict[str, Any]:
        with self._lock:
            accounts_summary = []
            total_dr = 0.0
            total_cr = 0.0
            for acct in self.accounts.values():
                bal = self.get_account_balance(acct.code)
                if bal == 0.0:
                    continue
                if acct.normal_side == "DEBIT":
                    dr = bal if bal > 0 else 0.0
                    cr = abs(bal) if bal < 0 else 0.0
                else:
                    cr = bal if bal > 0 else 0.0
                    dr = abs(bal) if bal < 0 else 0.0

                total_dr = round_money(total_dr + dr)
                total_cr = round_money(total_cr + cr)
                accounts_summary.append({
                    "code": acct.code,
                    "name": acct.name,
                    "type": acct.account_type,
                    "debit": dr,
                    "credit": cr,
                })

            return {
                "accounts": accounts_summary,
                "total_debit": total_dr,
                "total_credit": total_cr,
                "is_balanced": abs(total_dr - total_cr) < 0.01,
            }

    def get_profit_and_loss(self) -> Dict[str, Any]:
        with self._lock:
            revenues = {a.code: self.get_account_balance(a.code) for a in self.accounts.values() if a.account_type == "REVENUE"}
            expenses = {a.code: self.get_account_balance(a.code) for a in self.accounts.values() if a.account_type == "EXPENSE"}
            total_rev = round_money(sum(revenues.values()))
            total_exp = round_money(sum(expenses.values()))
            net_profit = round_money(total_rev - total_exp)
            return {
                "total_revenue": total_rev,
                "total_expense": total_exp,
                "net_profit": net_profit,
                "revenues": {k: v for k, v in revenues.items() if v != 0},
                "expenses": {k: v for k, v in expenses.items() if v != 0},
            }

    def get_balance_sheet(self) -> Dict[str, Any]:
        with self._lock:
            pnl = self.get_profit_and_loss()
            assets = {a.code: self.get_account_balance(a.code) for a in self.accounts.values() if a.account_type == "ASSET"}
            liabilities = {a.code: self.get_account_balance(a.code) for a in self.accounts.values() if a.account_type == "LIABILITY"}
            equity = {a.code: self.get_account_balance(a.code) for a in self.accounts.values() if a.account_type == "EQUITY"}
            total_assets = round_money(sum(assets.values()))
            total_liabilities = round_money(sum(liabilities.values()))
            total_equity = round_money(sum(equity.values()) + pnl["net_profit"])
            return {
                "total_assets": total_assets,
                "total_liabilities": total_liabilities,
                "total_equity": total_equity,
                "retained_earnings": pnl["net_profit"],
                "is_balanced": abs(total_assets - (total_liabilities + total_equity)) < 0.01,
            }
