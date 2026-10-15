"""Cryptographically linked, append-only immutable audit trail."""

import hashlib
import json
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class AuditEvent(BaseModel):
    """An immutable audit trail entry."""
    seq: int
    timestamp: str
    event_type: str
    actor: str
    transaction_id: Optional[str] = None
    details: Dict[str, Any] = Field(default_factory=dict)
    previous_hash: str
    entry_hash: str

    @classmethod
    def compute_hash(
        cls,
        seq: int,
        timestamp: str,
        event_type: str,
        actor: str,
        transaction_id: Optional[str],
        details: Dict[str, Any],
        previous_hash: str,
    ) -> str:
        payload = {
            "seq": seq,
            "timestamp": timestamp,
            "event_type": event_type,
            "actor": actor,
            "transaction_id": transaction_id or "",
            "details": details,
            "previous_hash": previous_hash,
        }
        encoded = json.dumps(payload, sort_keys=True).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


class AuditTrail:
    """Manages an append-only log with cryptographic hashing verification."""

    GENESIS_HASH = "0" * 64

    def __init__(self):
        self._events: List[AuditEvent] = []

    @property
    def events(self) -> List[AuditEvent]:
        return list(self._events)

    def log(
        self,
        event_type: str,
        actor: str,
        details: Dict[str, Any],
        transaction_id: Optional[str] = None,
    ) -> AuditEvent:
        """Appends a new verified event to the audit trail."""
        seq = len(self._events) + 1
        timestamp = datetime.now(timezone.utc).isoformat()
        previous_hash = self._events[-1].entry_hash if self._events else self.GENESIS_HASH
        
        entry_hash = AuditEvent.compute_hash(
            seq=seq,
            timestamp=timestamp,
            event_type=event_type,
            actor=actor,
            transaction_id=transaction_id,
            details=details,
            previous_hash=previous_hash,
        )

        event = AuditEvent(
            seq=seq,
            timestamp=timestamp,
            event_type=event_type,
            actor=actor,
            transaction_id=transaction_id,
            details=details,
            previous_hash=previous_hash,
            entry_hash=entry_hash,
        )
        self._events.append(event)
        return event

    def verify_integrity(self) -> bool:
        """Verifies that all entries in the audit trail have intact cryptographic links."""
        if not self._events:
            return True

        for i, event in enumerate(self._events):
            expected_prev = self._events[i - 1].entry_hash if i > 0 else self.GENESIS_HASH
            if event.previous_hash != expected_prev:
                return False

            recalculated_hash = AuditEvent.compute_hash(
                seq=event.seq,
                timestamp=event.timestamp,
                event_type=event.event_type,
                actor=event.actor,
                transaction_id=event.transaction_id,
                details=event.details,
                previous_hash=event.previous_hash,
            )
            if event.entry_hash != recalculated_hash:
                return False

        return True
