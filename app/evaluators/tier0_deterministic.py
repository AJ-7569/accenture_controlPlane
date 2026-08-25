import re
import hashlib
import time
from typing import List, Tuple, Dict, Any, Optional
from ..models import (
    RiskFinding, RiskCategory, RiskSeverity, UseCaseType
)

def luhn_checksum_valid(card_number_str: str) -> bool:
    """Validate credit card number using the Luhn algorithm."""
    digits = [int(c) for c in card_number_str if c.isdigit()]
    if len(digits) < 13 or len(digits) > 19:
        return False
    checksum = 0
    reverse_digits = digits[::-1]
    for i, digit in enumerate(reverse_digits):
        if i % 2 == 1:
            doubled = digit * 2
            checksum += doubled - 9 if doubled > 9 else doubled
        else:
            checksum += digit
    return checksum % 10 == 0

class Tier0Evaluator:
    """
    Tier 0: Deterministic & Heuristic Evaluation (<5ms)
    Operates without neural models, scanning for exact-match regex patterns,
    secrets, PII, destructive tool arguments, loop iterations, and structural AST syntax.
    """

    def __init__(self):
        # Compiled regex patterns for PII
        self.email_pattern = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b')
        self.phone_pattern = re.compile(r'\b(?:\+?(\d{1,3}))?[-. (]*(\d{3})[-. )]*(\d{3})[-. ]*(\d{4})\b')
        self.ssn_pattern = re.compile(r'\b(?!000|666|9\d{2})\d{3}-(?!00)\d{2}-(?!0000)\d{4}\b')
        self.card_candidate_pattern = re.compile(r'\b(?:\d[ -]*?){13,19}\b')

        # Compiled regex patterns for secrets and credentials
        self.secret_patterns = {
            "AWS_ACCESS_KEY": re.compile(r'\b(?:AKIA|ABIA|ACCA|ASIA)[0-9A-Z]{16}\b'),
            "OPENAI_API_KEY": re.compile(r'\bsk-[a-zA-Z0-9]{32,48}\b'),
            "GENERIC_BEARER_JWT": re.compile(r'\beyJ[A-Za-z0-9-_]+\.eyJ[A-Za-z0-9-_]+\.[A-Za-z0-9-_]+\b'),
            "DATABASE_URI": re.compile(r'\b(?:postgres|postgresql|mysql|mongodb|redis):\/\/[a-zA-Z0-9_-]+:[^@\s]+@[a-zA-Z0-9.-]+(?::\d+)?\/[a-zA-Z0-9_-]+\b'),
            "PRIVATE_KEY_HEADER": re.compile(r'-----BEGIN (?:RSA|OPENSSH|EC|DSA)? PRIVATE KEY-----')
        }

        # Protected environments for privilege escalation guardrails
        self.protected_environments = {"prod", "production", "live", "main"}
        
        # Diagnostic before action matrix (from MCP router architecture)
        self.diagnostic_prerequisites = {
            "terminate_instance": ["get_instance_health", "check_cluster_metrics"],
            "drop_database_table": ["verify_backup_status", "check_read_replicas"],
            "revoke_user_access": ["get_user_audit_log"],
            "execute_financial_transfer": ["verify_compliance_clearance", "check_account_balance"]
        }

    def scan_pii(self, text: str) -> List[RiskFinding]:
        """Scans for PII like Credit Cards, SSNs, Emails, and Phone Numbers."""
        findings: List[RiskFinding] = []

        # 1. Credit Card Check (with Luhn validation to avoid false positives)
        for match in self.card_candidate_pattern.finditer(text):
            candidate = match.group(0).replace(" ", "").replace("-", "")
            if luhn_checksum_valid(candidate):
                findings.append(RiskFinding(
                    category=RiskCategory.PII_PRIVACY,
                    severity=RiskSeverity.HIGH,
                    confidence=0.99,
                    rule_id="PII_CARD_LUHN_001",
                    tier="Tier 0 (<2ms)",
                    description=f"Valid payment card detected ({candidate[:4]}...{candidate[-4:]}) violating PCI-DSS.",
                    target_snippet=match.group(0),
                    suggested_replacement="[REDACTED_PAYMENT_CARD]"
                ))

        # 2. SSN Check
        for match in self.ssn_pattern.finditer(text):
            findings.append(RiskFinding(
                category=RiskCategory.PII_PRIVACY,
                severity=RiskSeverity.CRITICAL,
                confidence=0.98,
                rule_id="PII_SSN_002",
                tier="Tier 0 (<2ms)",
                description="Social Security Number (SSN) detected violating privacy policy.",
                target_snippet=match.group(0),
                suggested_replacement="[REDACTED_SSN]"
            ))

        # 3. Email Check
        for match in self.email_pattern.finditer(text):
            findings.append(RiskFinding(
                category=RiskCategory.PII_PRIVACY,
                severity=RiskSeverity.MEDIUM,
                confidence=0.95,
                rule_id="PII_EMAIL_003",
                tier="Tier 0 (<2ms)",
                description=f"Personal identifiable email address found: {match.group(0)}",
                target_snippet=match.group(0),
                suggested_replacement="[REDACTED_EMAIL]"
            ))

        # 4. Phone Number Check
        for match in self.phone_pattern.finditer(text):
            # Exclude false positives like dates or short sequences
            clean_digits = re.sub(r'\D', '', match.group(0))
            if len(clean_digits) in (10, 11):
                findings.append(RiskFinding(
                    category=RiskCategory.PII_PRIVACY,
                    severity=RiskSeverity.MEDIUM,
                    confidence=0.92,
                    rule_id="PII_PHONE_004",
                    tier="Tier 0 (<2ms)",
                    description=f"Direct phone contact info detected: {match.group(0)}",
                    target_snippet=match.group(0),
                    suggested_replacement="[REDACTED_PHONE]"
                ))

        return findings

    def scan_secrets(self, text: str) -> List[RiskFinding]:
        """Scans for API credentials, tokens, DB connection strings, and private keys."""
        findings: List[RiskFinding] = []

        for secret_type, pattern in self.secret_patterns.items():
            for match in pattern.finditer(text):
                findings.append(RiskFinding(
                    category=RiskCategory.SECRET_LEAKAGE,
                    severity=RiskSeverity.CRITICAL,
                    confidence=1.0,
                    rule_id=f"SECRET_{secret_type}_001",
                    tier="Tier 0 (<2ms)",
                    description=f"High-risk infrastructure secret token detected: {secret_type}",
                    target_snippet=match.group(0),
                    suggested_replacement="[REDACTED_SECRET_KEY]"
                ))

        return findings

    def redact_text(self, text: str, findings: List[RiskFinding]) -> str:
        """Applies in-flight deterministic sanitization to text based on findings."""
        redacted = text
        # Process PII and Secrets in descending order of length to prevent substring corruption
        redaction_items = [
            f for f in findings 
            if f.suggested_replacement and f.target_snippet and f.category in (RiskCategory.PII_PRIVACY, RiskCategory.SECRET_LEAKAGE)
        ]
        redaction_items.sort(key=lambda x: len(x.target_snippet or ""), reverse=True)

        for item in redaction_items:
            if item.target_snippet:
                redacted = redacted.replace(item.target_snippet, item.suggested_replacement)
        return redacted

    def evaluate_tool_call(
        self, 
        tool_name: str, 
        arguments: Dict[str, Any], 
        execution_history: List[str]
    ) -> List[RiskFinding]:
        """
        Evaluates agent tool invocations against diagnostic sequencing,
        sliding-window loop detection, and environment privilege escalation.
        """
        findings: List[RiskFinding] = []

        # 1. Loop Detection via serialized parameter MD5
        serialized = f"{tool_name}:{sorted(arguments.items())}"
        current_hash = hashlib.md5(serialized.encode()).hexdigest()
        
        # Count hash occurrences in the last 4 execution steps
        recent_hashes = [h.split(":")[-1] for h in execution_history[-4:]]
        if recent_hashes.count(current_hash) >= 2:
            findings.append(RiskFinding(
                category=RiskCategory.AGENT_TOOL_VIOLATION,
                severity=RiskSeverity.HIGH,
                confidence=0.99,
                rule_id="AGENT_LOOP_DETECTED_001",
                tier="Tier 0 (<2ms)",
                description=f"Agent stuck in execution loop with identical arguments for tool '{tool_name}'.",
                target_snippet=tool_name
            ))

        # 2. Diagnostic-Before-Action Sequencing Check
        if tool_name in self.diagnostic_prerequisites:
            required_diags = self.diagnostic_prerequisites[tool_name]
            executed_tool_names = [h.split(":")[0] for h in execution_history]
            for required in required_diags:
                if required not in executed_tool_names:
                    findings.append(RiskFinding(
                        category=RiskCategory.AGENT_TOOL_VIOLATION,
                        severity=RiskSeverity.HIGH,
                        confidence=1.0,
                        rule_id="AGENT_PREREQUISITE_MISSING_002",
                        tier="Tier 0 (<2ms)",
                        description=f"Diagnostic check '{required}' must be verified before executing mutation tool '{tool_name}'.",
                        target_snippet=tool_name
                    ))

        # 3. Privilege Escalation & Blast Radius Guard
        target_env = str(arguments.get("environment", "")).lower()
        if target_env in self.protected_environments and ("terminate" in tool_name or "drop" in tool_name or "delete" in tool_name):
            findings.append(RiskFinding(
                category=RiskCategory.AGENT_TOOL_VIOLATION,
                severity=RiskSeverity.CRITICAL,
                confidence=1.0,
                rule_id="PRIVILEGE_PROD_BLAST_RADIUS_003",
                tier="Tier 0 (<2ms)",
                description=f"Destructive mutation '{tool_name}' on protected environment '{target_env}' requires elevated human approval.",
                target_snippet=f"{tool_name}(environment={target_env})"
            ))

        return findings

    def evaluate(
        self, 
        prompt: str, 
        proposed_response: Optional[str] = None, 
        tool_name: Optional[str] = None, 
        tool_arguments: Optional[Dict[str, Any]] = None, 
        execution_history: Optional[List[str]] = None
    ) -> Tuple[List[RiskFinding], float]:
        """Main Tier 0 evaluation entrypoint returning (findings, execution_time_ms)."""
        start_time = time.perf_counter()
        findings: List[RiskFinding] = []

        # Scan Prompt (Pre-flight Gate)
        findings.extend(self.scan_secrets(prompt))
        findings.extend(self.scan_pii(prompt))

        # Scan Response (Output Gate) if present
        if proposed_response:
            findings.extend(self.scan_secrets(proposed_response))
            findings.extend(self.scan_pii(proposed_response))

        # Scan Tool Calls (MCP Action Gate)
        if tool_name:
            args = tool_arguments or {}
            history = execution_history or []
            findings.extend(self.evaluate_tool_call(tool_name, args, history))

        elapsed_ms = (time.perf_counter() - start_time) * 1000.0
        return findings, round(elapsed_ms, 2)
