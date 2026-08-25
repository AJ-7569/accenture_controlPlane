import time
import uuid
from typing import List, Dict, Any, Optional
from ..models import HITLReviewItem, UseCaseType, RiskFinding, InterventionAction

class HITLManager:
    """
    Tier 3: Human-In-The-Loop (HITL) Queue & Governance Feedback Loop.
    Enqueues borderline or high-risk decisions for compliance officer review
    and captures feedback data to tune policy thresholds and active learning pools.
    """

    def __init__(self):
        self.queue: Dict[str, HITLReviewItem] = {}
        self.feedback_history: List[Dict[str, Any]] = []

    def enqueue(
        self,
        eval_id: str,
        use_case: UseCaseType,
        session_id: str,
        prompt: str,
        proposed_response: str,
        composite_risk_score: float,
        findings: List[RiskFinding]
    ) -> HITLReviewItem:
        """Adds a high-risk transaction to the human review queue."""
        item = HITLReviewItem(
            eval_id=eval_id,
            use_case=use_case,
            session_id=session_id,
            prompt=prompt,
            proposed_response=proposed_response,
            composite_risk_score=composite_risk_score,
            findings=findings,
            status="PENDING"
        )
        self.queue[item.item_id] = item
        return item

    def get_pending_items(self) -> List[HITLReviewItem]:
        """Returns all unresolved review items sorted by recency."""
        pending = [item for item in self.queue.values() if item.status == "PENDING"]
        pending.sort(key=lambda x: x.timestamp, reverse=True)
        return pending

    def get_all_items(self) -> List[HITLReviewItem]:
        """Returns all review items (pending and resolved)."""
        items = list(self.queue.values())
        items.sort(key=lambda x: x.timestamp, reverse=True)
        return items

    def resolve_item(
        self,
        item_id: str,
        decision: str,  # "APPROVED", "OVERRIDDEN", "REJECTED"
        reviewer_notes: str,
        custom_response: Optional[str] = None
    ) -> Optional[HITLReviewItem]:
        """Resolves an escalation ticket and records feedback."""
        if item_id not in self.queue:
            return None

        item = self.queue[item_id]
        item.status = decision
        item.reviewer_notes = reviewer_notes

        if decision == "APPROVED":
            item.final_dispatched_response = item.proposed_response
        elif decision == "OVERRIDDEN":
            item.final_dispatched_response = custom_response or "[Sanitized by Compliance Officer]"
        elif decision == "REJECTED":
            item.final_dispatched_response = "Request blocked: Failed Responsible AI Compliance Review."

        # Record feedback for threshold calibration
        self.feedback_history.append({
            "timestamp": time.time(),
            "item_id": item_id,
            "use_case": item.use_case.value,
            "original_risk_score": item.composite_risk_score,
            "reviewer_decision": decision,
            "findings_count": len(item.findings),
            "rule_ids": [f.rule_id for f in item.findings]
        })

        return item

    def get_feedback_summary(self) -> Dict[str, Any]:
        """Returns statistics on reviewer decisions to power continuous learning."""
        total = len(self.feedback_history)
        if total == 0:
            return {
                "total_reviews": 0,
                "approved_rate": 0.0,
                "overridden_rate": 0.0,
                "rejected_rate": 0.0
            }

        approved = sum(1 for f in self.feedback_history if f["reviewer_decision"] == "APPROVED")
        overridden = sum(1 for f in self.feedback_history if f["reviewer_decision"] == "OVERRIDDEN")
        rejected = sum(1 for f in self.feedback_history if f["reviewer_decision"] == "REJECTED")

        return {
            "total_reviews": total,
            "approved_rate": round(approved / total, 2),
            "overridden_rate": round(overridden / total, 2),
            "rejected_rate": round(rejected / total, 2)
        }
