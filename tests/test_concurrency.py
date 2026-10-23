# tests/test_concurrency.py
import pytest
import concurrent.futures
from pathlib import Path
from munshi.ledger.engine import LedgerEngine
from munshi.ledger.models import JournalEntry, JournalLine

def test_concurrent_load_40_parallel_requests(tmp_path):
    """
    Stress test verifying SQLite concurrency under load.
    40 parallel threads post vouchers concurrently.
    Verifies that all 40 entries are recorded with zero data-loss race conditions,
    and the SHA-256 audit hash chain remains strictly sequential and intact.
    """
    db_file = tmp_path / "concurrent_munshi.db"
    engine = LedgerEngine(db_path=str(db_file))

    # Pre-seed 2 entries
    e1 = JournalEntry(
        entry_id="JE-PRE-01",
        date="2026-10-10",
        narration="Initial capital",
        lines=[
            JournalLine("1010", "HDFC Bank Current A/c", debit=10000.0, credit=0.0),
            JournalLine("3000", "Owner Capital Account", debit=0.0, credit=10000.0),
        ],
    )
    e2 = JournalEntry(
        entry_id="JE-PRE-02",
        date="2026-10-11",
        narration="Consulting revenue",
        lines=[
            JournalLine("1010", "HDFC Bank Current A/c", debit=5000.0, credit=0.0),
            JournalLine("4100", "SaaS & Consulting Revenue", debit=0.0, credit=5000.0),
        ],
    )
    engine.post_entry(e1)
    engine.post_entry(e2)

    def post_worker(idx: int):
        # Create a fresh engine instance connecting to the same SQLite database file to simulate concurrent processes
        worker_engine = LedgerEngine(db_path=str(db_file))
        entry = JournalEntry(
            entry_id=f"JE-CONC-{idx:03d}",
            date="2026-10-16",
            narration=f"Concurrent expense voucher #{idx}",
            lines=[
                JournalLine("5200", "Cloud & Software Subscriptions", debit=100.0, credit=0.0),
                JournalLine("1010", "HDFC Bank Current A/c", debit=0.0, credit=100.0),
            ],
        )
        return worker_engine.post_entry(entry)

    # Execute 40 parallel requests
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(post_worker, i) for i in range(1, 41)]
        results = [f.result() for f in concurrent.futures.as_completed(futures)]

    assert len(results) == 40

    # Load fresh verification engine
    verifier = LedgerEngine(db_path=str(db_file))
    # Must record exactly 42 entries (2 pre-seed + 40 concurrent)
    assert len(verifier.entries) == 42

    integrity = verifier.verify_ledger_integrity()
    assert integrity["verified"] is True
    assert integrity["audit_chain_valid"] is True
    assert integrity["ledger_balanced"] is True
    assert integrity["records_count"] == 42
