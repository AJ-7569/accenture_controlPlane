from enum import Enum
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
import time
import uuid

class UseCaseType(str, Enum):
    CUSTOMER_SUPPORT = "customer_support"
    INTERNAL_COPILOT = "internal_copilot"
    REGULATED_DECISION = "regulated_decision"

class InterventionAction(str, Enum):
    ALLOW = "ALLOW"
    REDACT_AND_MUTATE = "REDACT_AND_MUTATE"
    INTERCEPT_FALLBACK = "INTERCEPT_FALLBACK"
    FLAG_ASYNC = "FLAG_ASYNC"
    ESCALATE_HITL = "ESCALATE_HITL"

class RiskCategory(str, Enum):
    PII_PRIVACY = "PII_PRIVACY"
    SECRET_LEAKAGE = "SECRET_LEAKAGE"
    HALLUCINATION_UNGROUNDED = "HALLUCINATION_UNGROUNDED"
    BIAS_DEMOGRAPHIC = "BIAS_DEMOGRAPHIC"
    PROMPT_INJECTION_SECURITY = "PROMPT_INJECTION_SECURITY"
    AGENT_TOOL_VIOLATION = "AGENT_TOOL_VIOLATION"

class RiskSeverity(str, Enum):
    NONE = "NONE"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

class RiskFinding(BaseModel):
    category: RiskCategory
    severity: RiskSeverity
    confidence: float = Field(ge=0.0, le=1.0, description="Model confidence score 0.0 - 1.0")
    rule_id: str
    tier: str  # Tier 0, Tier 1, Tier 2, Tier 3
    description: str
    target_snippet: Optional[str] = None
    suggested_replacement: Optional[str] = None

class TierLatency(BaseModel):
    tier0_ms: float = 0.0
    tier1_ms: float = 0.0
    tier2_ms: float = 0.0
    tier3_ms: float = 0.0
    total_ms: float = 0.0

class EvaluationResult(BaseModel):
    eval_id: str = Field(default_factory=lambda: f"eval_{uuid.uuid4().hex[:8]}")
    timestamp: float = Field(default_factory=time.time)
    use_case: UseCaseType
    composite_risk_score: float = Field(ge=0.0, le=1.0)
    action: InterventionAction
    original_text: str
    sanitized_text: str
    findings: List[RiskFinding] = []
    latencies: TierLatency
    decision_rationale: str
    audit_hash: Optional[str] = None
    session_id: Optional[str] = None
    requires_hitl: bool = False

class PolicyConfig(BaseModel):
    use_case: UseCaseType
    name: str
    description: str
    latency_budget_ms: float
    f_beta: float = Field(default=1.0, description="0.5=precision focus, 1.0=balanced, 2.0=recall focus")
    pii_auto_redact: bool = True
    secret_blocking: bool = True
    grounding_required: bool = True
    grounding_min_entailment: float = 0.70
    bias_tolerance: float = 0.20  # Max permitted demographic disparity
    prompt_injection_action: InterventionAction = InterventionAction.INTERCEPT_FALLBACK
    hitl_escalation_threshold: float = 0.65  # CRI score to trigger human queue
    prohibited_tools: List[str] = []
    required_diagnostic_tools: Dict[str, List[str]] = {}

class ChatMessage(BaseModel):
    role: str  # system, user, assistant, tool
    content: str
    name: Optional[str] = None
    tool_call_id: Optional[str] = None

class ToolCallRequest(BaseModel):
    tool_name: str
    arguments: Dict[str, Any] = {}

class GatewayRequest(BaseModel):
    session_id: Optional[str] = None
    use_case: UseCaseType = UseCaseType.CUSTOMER_SUPPORT
    prompt: str
    proposed_response: Optional[str] = None
    rag_context_chunks: List[str] = []
    requested_tool: Optional[ToolCallRequest] = None
    demographic_attribute: Optional[str] = None  # for counterfactual testing

class GatewayResponse(BaseModel):
    eval_id: str
    session_id: str
    use_case: UseCaseType
    action: InterventionAction
    final_output: str
    original_output: str
    composite_risk_score: float
    findings: List[RiskFinding]
    latencies: TierLatency
    decision_rationale: str
    audit_hash: str
    hitl_ticket_id: Optional[str] = None

class HITLReviewItem(BaseModel):
    item_id: str = Field(default_factory=lambda: f"hitl_{uuid.uuid4().hex[:8]}")
    eval_id: str
    timestamp: float = Field(default_factory=time.time)
    use_case: UseCaseType
    session_id: str
    prompt: str
    proposed_response: str
    composite_risk_score: float
    findings: List[RiskFinding]
    status: str = "PENDING"  # PENDING, APPROVED, OVERRIDDEN, REJECTED
    reviewer_notes: Optional[str] = None
    final_dispatched_response: Optional[str] = None

class AuditLogEntry(BaseModel):
    entry_id: str
    prev_hash: str
    current_hash: str
    timestamp: float
    use_case: UseCaseType
    session_id: str
    action: InterventionAction
    composite_risk: float
    findings_count: int
    rule_ids: List[str]
    total_latency_ms: float

class SystemMetrics(BaseModel):
    total_requests: int = 0
    action_counts: Dict[str, int] = {}
    use_case_counts: Dict[str, int] = {}
    risk_category_counts: Dict[str, int] = {}
    avg_latency_ms: float = 0.0
    tier_latencies_avg: Dict[str, float] = {}
    estimated_precision: float = 0.94
    estimated_recall: float = 0.98
    active_hitl_pending: int = 0
    total_hitl_reviewed: int = 0
