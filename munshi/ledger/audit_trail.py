# munshi/ledger/audit_trail.py
import hashlib
import json
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

@dataclass
class AuditRecord:
    seq: int
    timestamp: str
    action: str
    entry_id: str
    payload: Dict[str, Any]
    prev_hash: str
    record_hash: str

class AuditTrail:
    GENESIS_HASH = "0" * 64

    def __init__(self, records: Optional[List[AuditRecord]] = None):
        self.records: List[AuditRecord] = records or []

    @staticmethod
    def compute_hash(seq: int, timestamp: str, action: str, entry_id: str, payload: Dict[str, Any], prev_hash: str) -> str:
        canonical = json.dumps(
            {
                "seq": seq,
                "timestamp": timestamp,
                "action": action,
                "entry_id": entry_id,
                "payload": payload,
                "prev_hash": prev_hash,
            },
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def append(self, action: str, entry_id: str, payload: Dict[str, Any], timestamp: Optional[str] = None) -> AuditRecord:
        seq = len(self.records) + 1
        prev_hash = self.records[-1].record_hash if self.records else self.GENESIS_HASH
        ts = timestamp or datetime.now(timezone.utc).isoformat()
        rec_hash = self.compute_hash(seq, ts, action, entry_id, payload, prev_hash)
        record = AuditRecord(
            seq=seq,
            timestamp=ts,
            action=action,
            entry_id=entry_id,
            payload=payload,
            prev_hash=prev_hash,
            record_hash=rec_hash,
        )
        self.records.append(record)
        return record

    def verify_integrity(self) -> bool:
        prev_hash = self.GENESIS_HASH
        for idx, rec in enumerate(self.records):
            if rec.seq != idx + 1:
                return False
            if rec.prev_hash != prev_hash:
                return False
            expected = self.compute_hash(rec.seq, rec.timestamp, rec.action, rec.entry_id, rec.payload, rec.prev_hash)
            if rec.record_hash != expected:
                return False
            prev_hash = rec.record_hash
        return True

    def to_dict_list(self) -> List[Dict[str, Any]]:
        return [asdict(r) for r in self.records]
