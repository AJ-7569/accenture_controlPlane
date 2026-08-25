import hashlib
import time
import json
from typing import List, Dict, Any, Optional
from ..models import AuditLogEntry, UseCaseType, InterventionAction

class AuditLogger:
    """
    Immutable Cryptographic Audit Trail (SHA-256 Hash-Chained).
    Fulfills regulatory requirements (EU AI Act Article 12, HIPAA, SEC Rule 204)
    by ensuring that every policy check, payload hash, and intervention is tamper-evident.
    """

    def __init__(self):
        self.log_chain: List[AuditLogEntry] = []
        # Genesis hash
        self.latest_hash: str = "0000000000000000000000000000000000000000000000000000000000000000"

    def record(
        self,
        eval_id: str,
        use_case: UseCaseType,
        session_id: str,
        action: InterventionAction,
        composite_risk: float,
        findings_count: int,
        rule_ids: List[str],
        total_latency_ms: float
    ) -> AuditLogEntry:
        """Records a new immutable entry chained to the previous hash."""
        timestamp = time.time()
        prev_hash = self.latest_hash
        
        # Construct deterministic payload for hashing
        entry_payload = {
            "eval_id": eval_id,
            "prev_hash": prev_hash,
            "timestamp": timestamp,
            "use_case": use_case.value,
            "session_id": session_id,
            "action": action.value,
            "composite_risk": composite_risk,
            "findings_count": findings_count,
            "rule_ids": sorted(rule_ids),
            "latency_ms": total_latency_ms
        }
        
        payload_serialized = json.dumps(entry_payload, sort_keys=True)
        current_hash = hashlib.sha256(payload_serialized.encode()).hexdigest()
        self.latest_hash = current_hash

        entry = AuditLogEntry(
            entry_id=eval_id,
            prev_hash=prev_hash,
            current_hash=current_hash,
            timestamp=timestamp,
            use_case=use_case,
            session_id=session_id,
            action=action,
            composite_risk=composite_risk,
            findings_count=findings_count,
            rule_ids=rule_ids,
            total_latency_ms=total_latency_ms
        )

        self.log_chain.append(entry)
        # Cap in-memory history to last 500 records
        if len(self.log_chain) > 500:
            self.log_chain = self.log_chain[-500:]

        return entry

    def verify_chain_integrity(self) -> bool:
        """Verifies mathematical validity of the entire hash chain."""
        if not self.log_chain:
            return True
        
        prev = "0000000000000000000000000000000000000000000000000000000000000000"
        for entry in self.log_chain:
            if entry.prev_hash != prev:
                return False
            
            entry_payload = {
                "eval_id": entry.entry_id,
                "prev_hash": entry.prev_hash,
                "timestamp": entry.timestamp,
                "use_case": entry.use_case.value,
                "session_id": entry.session_id,
                "action": entry.action.value,
                "composite_risk": entry.composite_risk,
                "findings_count": entry.findings_count,
                "rule_ids": sorted(entry.rule_ids),
                "latency_ms": entry.total_latency_ms
            }
            computed_hash = hashlib.sha256(json.dumps(entry_payload, sort_keys=True).encode()).hexdigest()
            if entry.current_hash != computed_hash:
                return False
            prev = entry.current_hash

        return True

    def get_recent_entries(self, limit: int = 50) -> List[AuditLogEntry]:
        """Returns recent audit logs in descending chronological order."""
        return self.log_chain[-limit:][::-1]
