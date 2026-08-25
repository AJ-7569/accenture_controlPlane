from typing import Dict, Any, Optional
from .models import PolicyConfig, UseCaseType, InterventionAction

class PolicyEngine:
    """
    Dynamic Policy Engine:
    Configures and enforces use-case-specific policies, latency budgets,
    F-beta alert fatigue curves, and intervention actions.
    """

    def __init__(self):
        self.policies: Dict[UseCaseType, PolicyConfig] = {
            UseCaseType.CUSTOMER_SUPPORT: PolicyConfig(
                use_case=UseCaseType.CUSTOMER_SUPPORT,
                name="Customer Support Chatbot Policy",
                description="High-volume, ultra-low latency guardrails. Prioritizes real-time PII sanitization, toxicity blocking, and deterministic safe fallbacks.",
                latency_budget_ms=80.0,
                f_beta=1.0,  # Balanced F1
                pii_auto_redact=True,
                secret_blocking=True,
                grounding_required=True,
                grounding_min_entailment=0.60,
                bias_tolerance=0.15,
                prompt_injection_action=InterventionAction.INTERCEPT_FALLBACK,
                hitl_escalation_threshold=0.85,  # Avoid blocking live chat users unless extreme
                prohibited_tools=["terminate_instance", "drop_database_table", "modify_iam_roles"]
            ),
            UseCaseType.INTERNAL_COPILOT: PolicyConfig(
                use_case=UseCaseType.INTERNAL_COPILOT,
                name="Internal Engineering & HR Copilot Policy",
                description="Developer & employee assistant guardrails. Tuned for precision (F-0.5) to prevent alert fatigue, with zero tolerance for secret/IP leakage.",
                latency_budget_ms=250.0,
                f_beta=0.5,  # Precision focus (low false positive rate)
                pii_auto_redact=True,
                secret_blocking=True,
                grounding_required=False,
                grounding_min_entailment=0.50,
                bias_tolerance=0.25,
                prompt_injection_action=InterventionAction.INTERCEPT_FALLBACK,
                hitl_escalation_threshold=0.75,
                prohibited_tools=["drop_database_table"],
                required_diagnostic_tools={
                    "terminate_instance": ["get_instance_health"]
                }
            ),
            UseCaseType.REGULATED_DECISION: PolicyConfig(
                use_case=UseCaseType.REGULATED_DECISION,
                name="Regulated Decision Support (Credit & Clinical) Policy",
                description="Mission-critical regulatory compliance (EU AI Act / HIPAA). Recall-heavy (F-2.0), requiring strict citation entailment and mandatory HITL escalations.",
                latency_budget_ms=1200.0,
                f_beta=2.0,  # Recall focus (catches all potential non-compliance)
                pii_auto_redact=True,
                secret_blocking=True,
                grounding_required=True,
                grounding_min_entailment=0.85,
                bias_tolerance=0.05,  # Minimal permitted demographic divergence
                prompt_injection_action=InterventionAction.ESCALATE_HITL,
                hitl_escalation_threshold=0.40,  # Proactively routes borderline cases to human compliance
                prohibited_tools=["execute_financial_transfer", "override_credit_limit"],
                required_diagnostic_tools={
                    "execute_financial_transfer": ["verify_compliance_clearance"]
                }
            )
        }

    def get_policy(self, use_case: UseCaseType) -> PolicyConfig:
        """Retrieves policy for a given use case, falling back to Customer Support default."""
        return self.policies.get(use_case, self.policies[UseCaseType.CUSTOMER_SUPPORT])

    def update_policy(self, use_case: UseCaseType, updates: Dict[str, Any]) -> PolicyConfig:
        """Updates policy parameters in real time."""
        current_policy = self.get_policy(use_case)
        policy_data = current_policy.model_dump()
        policy_data.update(updates)
        updated_policy = PolicyConfig(**policy_data)
        self.policies[use_case] = updated_policy
        return updated_policy

    def get_all_policies(self) -> Dict[str, PolicyConfig]:
        """Returns all configured policies."""
        return {k.value: v for k, v in self.policies.items()}
