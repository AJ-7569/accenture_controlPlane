import time
from typing import Dict, List, Any, Optional
from pydantic import BaseModel, Field

class SessionState(BaseModel):
    session_id: str
    created_at: float = Field(default_factory=time.time)
    last_activity: float = Field(default_factory=time.time)
    turn_count: int = 0
    cumulative_risk_score: float = 0.0
    injection_priming_score: float = 0.0
    tool_execution_history: List[str] = []
    detected_violations: List[str] = []
    messages_history: List[Dict[str, str]] = []

class SessionTracker:
    """
    Tracks multi-turn conversational state and agent memory.
    Detects compounding risk patterns:
    - Multi-turn progressive jailbreak / context priming
    - Repetitive probing for secrets
    - Cumulative blast-radius expansion
    """

    def __init__(self):
        self.sessions: Dict[str, SessionState] = {}

    def get_or_create_session(self, session_id: Optional[str] = None) -> SessionState:
        """Retrieves an existing session or creates a new one."""
        if not session_id:
            import uuid
            session_id = f"sess_{uuid.uuid4().hex[:10]}"
        
        if session_id not in self.sessions:
            self.sessions[session_id] = SessionState(session_id=session_id)
        
        session = self.sessions[session_id]
        session.last_activity = time.time()
        return session

    def update_session(
        self,
        session_id: str,
        prompt: str,
        response: str,
        turn_risk_score: float,
        tool_call_signature: Optional[str] = None,
        violation_tags: Optional[List[str]] = None
    ) -> SessionState:
        """Updates session state with new interaction data."""
        session = self.get_or_create_session(session_id)
        session.turn_count += 1
        
        # Exponential moving average for cumulative risk
        session.cumulative_risk_score = round(
            0.6 * session.cumulative_risk_score + 0.4 * turn_risk_score, 3
        )

        # Detect progressive prompt injection priming across multiple turns
        prompt_lower = prompt.lower()
        if any(term in prompt_lower for term in ["hypothetically", "for a story", "fictional universe", "forget"]):
            session.injection_priming_score = min(1.0, session.injection_priming_score + 0.35)
        else:
            session.injection_priming_score = max(0.0, session.injection_priming_score - 0.1)

        if tool_call_signature:
            session.tool_execution_history.append(tool_call_signature)

        if violation_tags:
            session.detected_violations.extend(violation_tags)

        session.messages_history.append({"role": "user", "content": prompt})
        session.messages_history.append({"role": "assistant", "content": response})

        # Cap memory to last 20 turns
        if len(session.messages_history) > 40:
            session.messages_history = session.messages_history[-40:]

        return session

    def check_compounding_risk(self, session_id: str) -> float:
        """
        Returns compounding risk multiplier based on multi-turn priming
        and prior session violations.
        """
        if session_id not in self.sessions:
            return 0.0
        session = self.sessions[session_id]
        
        # If user has been priming over multiple turns, escalate risk
        compounding = session.injection_priming_score * 0.4
        if len(session.detected_violations) > 2:
            compounding += 0.3
        return min(1.0, round(compounding, 3))
