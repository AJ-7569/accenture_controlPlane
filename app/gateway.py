import time
import uuid
import asyncio
from typing import List, Dict, Any, Optional, Tuple
from .models import (
    GatewayRequest, GatewayResponse, EvaluationResult, RiskFinding,
    RiskCategory, RiskSeverity, InterventionAction, UseCaseType,
    TierLatency, HITLReviewItem, PolicyConfig
)
from .evaluators.tier0_deterministic import Tier0Evaluator
from .evaluators.tier1_fast_neural import Tier1Evaluator
from .evaluators.tier2_deep_grounding import Tier2Evaluator
from .evaluators.tier3_hitl import HITLManager
from .policy_engine import PolicyEngine
from .session_tracker import SessionTracker
from .telemetry.audit_logger import AuditLogger
from .telemetry.metrics_service import MetricsService

class OmniGuardGateway:
    """
    OmniGuard AI: Central Enterprise Responsible AI Gateway & Control Plane.
    Orchestrates the 5-Stage Interception Pipeline across heterogeneous use cases.
    """

    def __init__(self):
        self.tier0 = Tier0Evaluator()
        self.tier1 = Tier1Evaluator()
        self.tier2 = Tier2Evaluator()
        self.hitl = HITLManager()
        self.policy_engine = PolicyEngine()
        self.session_tracker = SessionTracker()
        self.audit_logger = AuditLogger()
        self.metrics = MetricsService()

        # Deterministic Safe Fallbacks per use case
        self.fallbacks = {
            UseCaseType.CUSTOMER_SUPPORT: (
                "I apologize, but I am unable to fulfill this specific request as it conflicts "
                "with our customer safety and security guidelines. Please contact our support team at support@enterprise.com for direct assistance."
            ),
            UseCaseType.INTERNAL_COPILOT: (
                "[OmniGuard Interception]: Execution halted due to internal security or IP boundary policy violation. "
                "Ensure all credentials and diagnostic prerequisites are verified."
            ),
            UseCaseType.REGULATED_DECISION: (
                "[Regulatory Review Triggered]: This decision requires human compliance officer verification under Article 14 of the EU AI Act. "
                "Your request has been routed to the compliance review queue."
            )
        }

    def calculate_composite_risk(
        self, 
        findings: List[RiskFinding], 
        policy: PolicyConfig,
        compounding_multiplier: float = 0.0
    ) -> float:
        """
        Calculates unified Multi-Dimensional Risk Index (MDRI / CRI)
        incorporating severity weights, confidence, and F-beta alert fatigue curve.
        """
        if not findings:
            return round(compounding_multiplier * 0.2, 3)

        severity_weights = {
            RiskSeverity.CRITICAL: 1.0,
            RiskSeverity.HIGH: 0.75,
            RiskSeverity.MEDIUM: 0.40,
            RiskSeverity.LOW: 0.15,
            RiskSeverity.NONE: 0.0
        }

        # Multi-factor accumulation: 1 - Product(1 - w_i * c_i)
        complement_product = 1.0
        for f in findings:
            weight = severity_weights.get(f.severity, 0.2)
            # Apply F-beta adjustment: beta < 1 (precision-oriented) reduces false alarms
            if policy.f_beta < 1.0 and f.severity in (RiskSeverity.LOW, RiskSeverity.MEDIUM):
                weight *= 0.6
            elif policy.f_beta > 1.0:
                # Recall-oriented amplifies sensitivity
                weight = min(1.0, weight * 1.3)

            factor = weight * f.confidence
            complement_product *= (1.0 - factor)

        raw_cri = 1.0 - complement_product
        # Add compounding session multiplier
        final_cri = min(1.0, raw_cri + (compounding_multiplier * 0.25))
        return round(final_cri, 3)

    async def evaluate_pipeline(self, request: GatewayRequest) -> GatewayResponse:
        """
        Executes the 5-Stage Interception Pipeline asynchronously.
        """
        eval_id = f"eval_{uuid.uuid4().hex[:8]}"
        session_id = request.session_id or f"sess_{uuid.uuid4().hex[:8]}"
        session = self.session_tracker.get_or_create_session(session_id)
        policy = self.policy_engine.get_policy(request.use_case)
        
        all_findings: List[RiskFinding] = []
        latencies = TierLatency()
        overall_start = time.perf_counter()

        # Check multi-turn compounding risk from prior session context
        compounding_multiplier = self.session_tracker.check_compounding_risk(session_id)

        # ---------------------------------------------------------------------
        # STAGE 1: PRE-FLIGHT INPUT GATE (Prompt Injection, Input Secrets/PII)
        # ---------------------------------------------------------------------
        t0_findings_prompt, t0_p_lat = self.tier0.evaluate(prompt=request.prompt)
        t1_findings_prompt, t1_p_lat = self.tier1.evaluate(prompt=request.prompt)
        
        all_findings.extend(t0_findings_prompt)
        all_findings.extend(t1_findings_prompt)
        latencies.tier0_ms += t0_p_lat
        latencies.tier1_ms += t1_p_lat

        # ---------------------------------------------------------------------
        # STAGE 2 & 3: AGENT TOOL INVOCATION GATE (MCP Interceptor & Loop Defense)
        # ---------------------------------------------------------------------
        if request.requested_tool:
            tool_name = request.requested_tool.tool_name
            tool_args = request.requested_tool.arguments

            # Check if tool is explicitly prohibited by policy
            if tool_name in policy.prohibited_tools:
                all_findings.append(RiskFinding(
                    category=RiskCategory.AGENT_TOOL_VIOLATION,
                    severity=RiskSeverity.CRITICAL,
                    confidence=1.0,
                    rule_id="TOOL_PROHIBITED_BY_POLICY_001",
                    tier="Tier 0 (<2ms)",
                    description=f"Tool '{tool_name}' is strictly prohibited for persona '{request.use_case.value}'.",
                    target_snippet=tool_name
                ))

            # Run Tier 0 tool execution sequence and loop evaluation
            tool_findings, t0_tool_lat = self.tier0.evaluate(
                prompt="",
                tool_name=tool_name,
                tool_arguments=tool_args,
                execution_history=session.tool_execution_history
            )
            all_findings.extend(tool_findings)
            latencies.tier0_ms += t0_tool_lat

        # ---------------------------------------------------------------------
        # STAGE 4: POST-GENERATION OUTPUT GATE (Groundedness, PII, Bias)
        # ---------------------------------------------------------------------
        raw_output = request.proposed_response or ""
        sanitized_output = raw_output

        if raw_output:
            # Tier 0 scan on output text (Secrets and PII)
            t0_out_findings, t0_out_lat = self.tier0.evaluate(prompt="", proposed_response=raw_output)
            all_findings.extend(t0_out_findings)
            latencies.tier0_ms += t0_out_lat

            # Tier 1 scan on output text (Toxicity, entity checks)
            t1_out_findings, t1_out_lat = self.tier1.evaluate(
                prompt="", 
                proposed_response=raw_output, 
                context_chunks=request.rag_context_chunks
            )
            all_findings.extend(t1_out_findings)
            latencies.tier1_ms += t1_out_lat

            # Tier 2 Deep Grounding & Counterfactual Bias evaluation
            t2_findings, grounding_score, t2_lat = self.tier2.evaluate(
                prompt=request.prompt,
                proposed_response=raw_output,
                context_chunks=request.rag_context_chunks,
                min_entailment_threshold=policy.grounding_min_entailment,
                demographic_attr=request.demographic_attribute
            )
            all_findings.extend(t2_findings)
            latencies.tier2_ms = t2_lat

            # Perform in-flight PII redaction if enabled
            if policy.pii_auto_redact:
                sanitized_output = self.tier0.redact_text(raw_output, all_findings)

        # Total Pipeline Latency
        latencies.total_ms = round((time.perf_counter() - overall_start) * 1000.0 + latencies.tier1_ms + latencies.tier2_ms, 2)

        # ---------------------------------------------------------------------
        # DECISION MATRIX & ACTION RESOLUTION
        # ---------------------------------------------------------------------
        composite_risk = self.calculate_composite_risk(all_findings, policy, compounding_multiplier)
        
        # Determine Primary Action
        action = InterventionAction.ALLOW
        decision_rationale = "Response passed all safety, privacy, and groundedness checks."
        hitl_ticket_id = None

        has_critical_security = any(
            f.category in (RiskCategory.PROMPT_INJECTION_SECURITY, RiskCategory.SECRET_LEAKAGE) and f.severity in (RiskSeverity.HIGH, RiskSeverity.CRITICAL)
            for f in all_findings
        )
        has_tool_violation = any(f.category == RiskCategory.AGENT_TOOL_VIOLATION for f in all_findings)
        has_pii = any(f.category == RiskCategory.PII_PRIVACY for f in all_findings)
        has_hallucination = any(f.category == RiskCategory.HALLUCINATION_UNGROUNDED for f in all_findings)
        has_bias = any(f.category == RiskCategory.BIAS_DEMOGRAPHIC for f in all_findings)

        if has_critical_security or has_tool_violation:
            if request.use_case == UseCaseType.REGULATED_DECISION or composite_risk >= policy.hitl_escalation_threshold:
                action = InterventionAction.ESCALATE_HITL
                ticket = self.hitl.enqueue(
                    eval_id=eval_id,
                    use_case=request.use_case,
                    session_id=session_id,
                    prompt=request.prompt,
                    proposed_response=raw_output,
                    composite_risk_score=composite_risk,
                    findings=all_findings
                )
                hitl_ticket_id = ticket.item_id
                sanitized_output = self.fallbacks[request.use_case]
                decision_rationale = f"Critical security/tool violation detected (CRI: {composite_risk}). Escalated to Human-in-the-Loop review queue."
            else:
                action = InterventionAction.INTERCEPT_FALLBACK
                sanitized_output = self.fallbacks[request.use_case]
                decision_rationale = f"Blocked destructive action / prompt injection. Deterministic fallback dispatched."

        elif has_bias and request.use_case == UseCaseType.REGULATED_DECISION:
            action = InterventionAction.ESCALATE_HITL
            ticket = self.hitl.enqueue(
                eval_id=eval_id,
                use_case=request.use_case,
                session_id=session_id,
                prompt=request.prompt,
                proposed_response=raw_output,
                composite_risk_score=composite_risk,
                findings=all_findings
            )
            hitl_ticket_id = ticket.item_id
            sanitized_output = self.fallbacks[request.use_case]
            decision_rationale = f"Potential demographic disparity or protected class bias detected under EU AI Act. Escalated to HITL."

        elif composite_risk >= policy.hitl_escalation_threshold and request.use_case == UseCaseType.REGULATED_DECISION:
            action = InterventionAction.ESCALATE_HITL
            ticket = self.hitl.enqueue(
                eval_id=eval_id,
                use_case=request.use_case,
                session_id=session_id,
                prompt=request.prompt,
                proposed_response=raw_output,
                composite_risk_score=composite_risk,
                findings=all_findings
            )
            hitl_ticket_id = ticket.item_id
            sanitized_output = self.fallbacks[request.use_case]
            decision_rationale = f"Composite risk score ({composite_risk}) exceeded regulated threshold ({policy.hitl_escalation_threshold}). Route to Compliance Queue."

        elif has_pii and policy.pii_auto_redact:
            action = InterventionAction.REDACT_AND_MUTATE
            decision_rationale = f"Sensitive PII detected and redacted in-flight before output delivery."

        elif has_hallucination and request.use_case == UseCaseType.CUSTOMER_SUPPORT and composite_risk > 0.60:
            action = InterventionAction.INTERCEPT_FALLBACK
            sanitized_output = (
                "Thank you for contacting us. To ensure accurate details regarding this policy or offer, "
                "please refer directly to our official documentation or speak with our live agent."
            )
            decision_rationale = f"Ungrounded claim/discount hallucination intercepted to prevent company liability."

        elif len(all_findings) > 0 and policy.f_beta == 0.5:
            # Internal Copilot with precision focus: log asynchronously without blocking workflow unless critical
            action = InterventionAction.FLAG_ASYNC
            decision_rationale = f"Non-blocking telemetry flag recorded (F-0.5 precision profile; avoided developer alert fatigue)."

        # ---------------------------------------------------------------------
        # STAGE 5: TELEMETRY, AUDIT LOGGING & SESSION UPDATE
        # ---------------------------------------------------------------------
        audit_entry = self.audit_logger.record(
            eval_id=eval_id,
            use_case=request.use_case,
            session_id=session_id,
            action=action,
            composite_risk=composite_risk,
            findings_count=len(all_findings),
            rule_ids=[f.rule_id for f in all_findings],
            total_latency_ms=latencies.total_ms
        )

        self.metrics.record_transaction(
            use_case=request.use_case,
            action=action,
            risk_categories=[f.category for f in all_findings],
            latencies=latencies
        )

        tool_sig = None
        if request.requested_tool:
            tool_sig = f"{request.requested_tool.tool_name}:{sorted(request.requested_tool.arguments.items())}"

        self.session_tracker.update_session(
            session_id=session_id,
            prompt=request.prompt,
            response=sanitized_output,
            turn_risk_score=composite_risk,
            tool_call_signature=tool_sig,
            violation_tags=[f.rule_id for f in all_findings]
        )

        return GatewayResponse(
            eval_id=eval_id,
            session_id=session_id,
            use_case=request.use_case,
            action=action,
            final_output=sanitized_output,
            original_output=raw_output,
            composite_risk_score=composite_risk,
            findings=all_findings,
            latencies=latencies,
            decision_rationale=decision_rationale,
            audit_hash=audit_entry.current_hash,
            hitl_ticket_id=hitl_ticket_id
        )
