# OmniGuard AI: Enterprise-Grade Responsible AI Control Plane & Gateway

> **Round 2 Comprehensive Architecture & Working Prototype**  
> An inline, low-latency, multi-tier intervention gateway that evaluates AI prompts, RAG context, agent tool actions, and model generations in real time.

---

## 1. Executive Summary & Evolution from Round 1

In **Round 1**, the architecture was focused specifically on intercepting agent tool invocations through a Model Context Protocol (MCP) router (validating parameters, loop detection, and destructive actions).

**Round 2** expands this concept into a **holistic enterprise-grade Responsible AI Gateway**. It addresses the complex realities of operating generative AI at enterprise scale (tens of thousands of interactions per week across customer-facing, internal employee, and regulated decision-support workflows).

```
+---------------------------------------------------------------------------------------------------+
|                                      AI APPLICATION CLIENTS                                       |
|      (Customer Support Web Chat, Internal Dev/HR Copilot, Regulated Underwriting/Clinical App)    |
+-------------------------------------------------+-------------------------------------------------+
                                                  |
                                                  v  (JSON-RPC / REST API / OpenAI Proxy)
+---------------------------------------------------------------------------------------------------+
|                        OMNIGUARD AI: 5-STAGE INLINE INTERCEPTION GATEWAY                          |
|                                                                                                   |
|  [ Stage 1: Pre-Flight Input Gate ]   --> Prompt Injection, Jailbreak Vectors, Input Secrets/PII   |
|  [ Stage 2: Context / RAG Gate ]      --> RBAC Tenant Boundaries, Data Sensitivity Validation     |
|  [ Stage 3: Agent MCP Tool Gate ]     --> Diagnostic-Before-Action Sequencing, MD5 Loop Defense   |
|  [ Stage 4: Post-Generation Gate ]    --> NLI Entailment Grounding, In-Flight PII Redaction, Bias |
|  [ Stage 5: Telemetry & Audit Gate ]  --> SHA-256 Chained Immutable Ledger, Real-time Metrics     |
+-------------------------------------------------+-------------------------------------------------+
                                                  |
                 +--------------------------------+--------------------------------+
                 |                                |                                |
                 v                                v                                v
          [ ALLOW / PASS ]             [ REDACT_AND_MUTATE ]            [ ESCALATE_HITL / FALLBACK ]
     Forwarded to Client / Tool         In-flight PII Masking             Human Compliance Review
```

---

## 2. Solving the Real-World Complexities (Round 2 Direct Mapping)

### 2.1. Diverse Enterprise AI Use Cases & Latency Budgets
Different use cases have conflicting latency and risk constraints. OmniGuard enforces dynamic policy profiles:

| Workload Persona | Latency Budget | Operational $F_\beta$ | Primary Interventions | Verification Depth |
| :--- | :--- | :--- | :--- | :--- |
| **Customer Support Chatbot** | **Ultra-Low (<80ms)** | $F_{1.0}$ (Balanced) | Real-time PII Redaction, Instant Fallback | Tier 0 Regex + Tier 1 Fast SLM Classifier |
| **Internal Employee Copilot** | **Medium (<250ms)** | $F_{0.5}$ (Precision-Heavy) | IP/Secret Blocking, MCP Sequence Check | Tier 0 Secrets + AST Schema + Loop Defense |
| **Regulated Decision Support** | **High (<1200ms)** | $F_{2.0}$ (Recall-Heavy) | NLI Citation Entailment, Bias Escalation | Tier 2 Atomic Claim NLI + Counterfactuals + HITL |

---

### 2.2. Overlapping & Compound Risk Disambiguation
In real enterprise workflows, risks co-occur (e.g., a hallucinated response containing fabricated employee health details is simultaneously a factual error and a GDPR privacy breach).

OmniGuard computes a **Multi-Dimensional Composite Risk Index (CRI)**:
$$\text{CRI} = 1 - \prod_{f \in \text{Findings}} \left(1 - w(f) \cdot \text{Conf}(f)\right)$$
If CRI exceeds the use-case escalation threshold, the most severe regulatory violation dictates the remediation strategy (`REDACT`, `FALLBACK`, or `ESCALATE_HITL`).

---

### 2.3. Overcoming the "Zero Ground Truth" Problem in Hallucination
When external ground truth is missing, OmniGuard utilizes a multi-step verification hierarchy:
1. **Atomic Claim Extraction**: Automatically decomposes complex model responses into discrete declarative assertions.
2. **NLI (Natural Language Inference) Entailment**: Computes directional entailment probabilities $P(\text{Entailment} \mid \text{Chunk}, c_i)$ against retrieved RAG context chunks.
3. **Content-Token IDF & Stemming**: Filters stop words to evaluate factual predicate matching between generation and context.
4. **Epistemic Certainty Scoring**: Flags ungrounded high-stakes commitments (e.g. fabricated discount codes, interest rates, or clinical guarantees).

---

### 2.4. Alert Fatigue vs. Liability Calibration ($F_\beta$ Optimizer)
Over-flagging annoys developers; under-flagging causes catastrophic compliance liability. OmniGuard allows live tuning of the $F_\beta$ curve:
- **$\beta = 0.5$ (Internal Copilots)**: Weights Precision higher than Recall ($\text{Precision} \times 2$), suppressing false alarms for engineering jargon.
- **$\beta = 1.0$ (Customer Chatbots)**: Balanced harmonic mean for consumer interactions.
- **$\beta = 2.0$ (Regulated Finance/Healthcare)**: Weights Recall higher than Precision, prioritizing complete liability capture and routing edge cases to Human-in-the-Loop review.

---

### 2.5. Multi-Turn Conversational & Agentic Blast-Radius Compounding Risk
Individual turns may appear benign while progressively engineering a jailbreak or expanding agent permissions.
- **Session Memory State Machine**: Tracks cumulative toxicity, progressive prompt priming (`"hypothetically"`, `"in a story"`), and repetitive probing over turns.
- **MCP Tool Execution Gate**: Preserves the Round 1 *Diagnostic-Before-Action* requirement, ensuring diagnostic queries precede mutations and halting serialized MD5 loops.

---

### 2.6. Policy-as-Code & Cryptographic Governance
- **Hot-Reloadable Policy Engine**: Policies are defined as dynamic code configurations that can be updated live without restarting services.
- **SHA-256 Chained Immutable Audit Ledger**: Every check, payload hash, latency metric, and rule activation is cryptographically linked to the previous entry, providing mathematical proof of compliance under EU AI Act Article 12 and HIPAA.

---

## 3. Working Prototype Architecture & Code Structure

```
├── app/
│   ├── models.py                   # Pydantic v2 schemas (Requests, Actions, Findings, Policies, Metrics)
│   ├── policy_engine.py            # Dynamic multi-use-case governance profiles & F-beta curves
│   ├── session_tracker.py          # Multi-turn state tracking & compounding risk analyzer
│   ├── gateway.py                  # Central 5-Stage Interception Gateway orchestrator
│   ├── server.py                   # FastAPI server, REST API, and OpenAI Proxy
│   ├── evaluators/
│   │   ├── tier0_deterministic.py  # Luhn card check, SSN, regex secrets, MCP loops, sequencing
│   │   ├── tier1_fast_neural.py    # Fast prompt injection, toxic sentiment, entity boundary
│   │   ├── tier2_deep_grounding.py # Atomic claim extraction, NLI entailment, demographic bias
│   │   └── tier3_hitl.py           # Human-in-the-Loop review queue & active learning feedback
│   └── telemetry/
│       ├── audit_logger.py         # SHA-256 hash-chained immutable audit trail
│       └── metrics_service.py      # Real-time latency, throughput, and precision/recall stats
├── static/
│   ├── index.html                  # Bespoke Web Control Plane & Simulator UI
│   ├── css/styles.css              # Dark-mode glassmorphic design system
│   └── js/app.js                   # Interactive client-side dashboard logic
├── tests/
│   └── test_evaluators.py          # Automated verification test suite
├── requirements.txt                # Python dependencies
├── run_demo.py                     # Launcher script
└── README.md                       # Architectural documentation
```

---

## 4. Quickstart & How to Run

### Prerequisites
- Python 3.9+
- FastAPI, Uvicorn, Pydantic, HTTPX (`pip install -r requirements.txt`)

### 1. Run Automated Test Suite
```bash
python tests/test_evaluators.py
```
*Output: `All OmniGuard AI backend tests passed successfully!`*

### 2. Launch the Control Plane & Web Dashboard
```bash
python run_demo.py
```
Open your browser and navigate to:
**`http://localhost:8000`**

---

## 5. Interactive Control Plane Features

1. **Live Simulator & Multi-Persona Playground**:
   - Switch between **Customer Chatbot**, **Internal Copilot**, and **Regulated Decision Support**.
   - Preload attack scenarios (Jailbreak DAN attack, PII credit card leak, AWS secret disclosure, Demographic attribution bias, Context priming).
   - Inspect millisecond latency breakdowns for Tier 0 (<5ms), Tier 1 (<25ms), and Tier 2 (<150ms).
2. **Policy & F-β Studio**:
   - Interactive sliders to dynamically adjust F-β sensitivity, NLI entailment thresholds, and HITL escalation triggers.
3. **HITL Compliance Operations Center**:
   - Real-time queue for compliance officers to inspect flagged requests, view side-by-side diffs, and approve/reject with feedback logging.
4. **Real-Time Telemetry & KPIs**:
   - Live charts for latency distribution, action breakdown, and precision/recall estimations.
5. **Cryptographic Audit Ledger**:
   - Inspect the live SHA-256 tamper-evident hash chain.
