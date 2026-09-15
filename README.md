# Plansom Autonomous Delegation + Aegis Defense-in-Depth POC

## 🎯 Value Objective

This Proof of Concept (POC) demonstrates why **Microsoft Agentic Security** — including **Azure API Management (APIM), Prompt Shields, and Microsoft Entra ID** — and the **Aegis Zero-Trust Sidecar** are complementary layers of a defense-in-depth architecture.

Microsoft Agentic Security excels at protecting the **cognitive, identity, and static perimeter boundaries**. It can block unauthenticated access and enforce static API JSON schemas.

However, a critical **contextual execution gap** can remain at runtime.

A conventional database service account or Entra role may authenticate a request successfully, and an APIM schema may validate the payload structure, without understanding the **contextual boundaries of the agent's delegation scope**.

This creates the potential for a **Confused Deputy** scenario, where a highly privileged agent is tricked or hallucinates a request for data outside its authorized departmental scope.

This repository demonstrates how **Aegis closes this contextual execution gap** by enforcing dynamic, Layer 7 **Invocation-Bound Capability Tokens (IBCT)** at the point of execution.

### Core Principle

> **Microsoft protects the cognitive, identity, and static perimeter boundaries. Aegis protects the contextual runtime execution boundary.**

---

## 🏗️ Architecture Flow

The POC runs a localized, containerized pipeline simulating Plansom's delegation engine and directly compares:

1. A **Microsoft Baseline** using Entra ID + Azure API Management
2. The **Aegis L7 Zero-Trust Proxy** using contextual IBCT enforcement

```text
                         User Delegation Prompt
                                  │
                                  ▼
             ┌──────────────────────────────────────────┐
             │ Microsoft Orchestrator                  │
             │ Semantic Kernel                          │
             │                                          │
             │ Prompt → MCP / Function Invocation      │
             └────────────────────┬─────────────────────┘
                                  │
                       ┌──────────┴──────────┐
                       │                     │
                       ▼                     ▼
             ┌─────────────────┐   ┌─────────────────┐
             │ Microsoft       │   │ Aegis           │
             │ Baseline        │   │ Zero-Trust      │
             │                 │   │ Sidecar         │
             │ • Entra Role    │   │                 │
             │ • APIM Schema   │   │ • L7 Policy     │
             │ • Static Checks │   │ • IBCT Eval     │
             └────────┬────────┘   └────────┬────────┘
                      │                     │
                      ▼                     ▼
                  Target DB             Target DB
```

### Enforcement Boundary

The key difference is **what each layer understands**:

```text
Microsoft Baseline
──────────────────
Identity ──► "Is this caller authenticated?"
Schema  ──► "Is this payload structurally valid?"

Aegis
─────
Identity + Invocation Context
        │
        ├── Who is calling?
        ├── What tool is being invoked?
        ├── What resource is being requested?
        └── Is this invocation within the agent's
            delegated capability boundary?
```

---

## 📊 Matrix Benchmark Scenarios & Outcomes

The test suite, [`run_matrix_benchmark.py`](./run_matrix_benchmark.py), evaluates four runtime delegation scenarios to establish where baseline perimeter defenses succeed and where contextual runtime authorization is required.

### Benchmark Summary

| Scenario | Attack / Request      | Microsoft Baseline |         Aegis L7 Proxy | Result             |
| -------- | --------------------- | -----------------: | ---------------------: | ------------------ |
| 1        | Legitimate HR Read    |      ✅ ALLOW (200) |  ✅ ALLOW (200) ~39.6ms | Both secure        |
| 2        | Confused Deputy       | ❌ VULNERABLE (200) | ✅ SECURE (422) ~14.8ms | **Aegis contains** |
| 3        | Direct Schema Breach  |     ✅ SECURE (400) | ✅ SECURE (422) ~13.7ms | Both secure        |
| 4        | Authentication Bypass |     ✅ SECURE (401) | ✅ SECURE (401) ~11.0ms | Both secure        |

> **Key finding:** The benchmark isolates a class of runtime authorization failure that can occur even when authentication and static payload validation succeed.

---

## Scenario 1: Legitimate HR Read

### Objective

The agent requests authorized HR planning data within its delegated scope.

**Request context:**

```json
{
  "department": "hr_department",
  "data_type": "goals"
}
```

Both platforms successfully validate the request and permit execution.

| System             | Decision      | Latency |
| ------------------ | ------------- | ------: |
| Microsoft Baseline | ✅ ALLOW (200) |       — |
| Aegis L7 Proxy     | ✅ ALLOW (200) | ~39.6ms |

### Outcome

The request is authorized and reaches the target database.

This demonstrates that Aegis does **not** interfere with legitimate delegated operations.

---

## Scenario 2: Confused Deputy — The Residual Execution Gap

### Objective

The agent requests data belonging to another department:

```json
{
  "department": "executive_board",
  "data_type": "goals"
}
```

### Microsoft Baseline

The value `executive_board` is structurally valid according to the APIM JSON schema.

The agent also possesses a broad `Agent.Planning.Read` Entra role.

As a result, the baseline gateway can authenticate the request and validate its structure without evaluating whether the requested department falls within the agent's **contextual delegation scope**.

**Baseline result:**

```text
VULNERABLE
HTTP 200
Data leaked
```

### Aegis Containment

Aegis evaluates the invocation against the agent's Invocation-Bound Capability Token.

The capability restricts the department to:

```regex
^hr_department$
```

The request therefore fails contextual authorization:

```text
'executive_board' does not match '^hr_department$'
```

**Aegis result:**

```text
SECURE
HTTP 422 Unprocessable Entity
```

The packet is rejected at Layer 7 before reaching the database.

### Outcome

| System             | Decision   | Result                         |
| ------------------ | ---------- | ------------------------------ |
| Microsoft Baseline | ❌ HTTP 200 | **VULNERABLE — Data leaked**   |
| Aegis L7 Proxy     | ✅ HTTP 422 | **SECURE — Request contained** |

> **This is the central execution-gap scenario demonstrated by the POC.**

---

## Scenario 3: Unauthorized Parameter — Direct Schema Breach

### Objective

The agent attempts to submit an out-of-bounds parameter:

```json
{
  "department": "finance_treasury",
  "data_type": "goals"
}
```

Unlike Scenario 2, this value violates the **static API schema**.

Azure API Management correctly detects and rejects the structurally invalid request.

### Outcome

| System             | Decision       | Latency |
| ------------------ | -------------- | ------: |
| Microsoft Baseline | ✅ SECURE (400) |       — |
| Aegis L7 Proxy     | ✅ SECURE (422) | ~13.7ms |

### Security Significance

This scenario demonstrates that the Microsoft baseline controls **work as intended** for static schema violations.

Aegis is therefore not positioned as a replacement for APIM validation. It provides an additional contextual authorization layer.

---

## Scenario 4: Direct Authentication Bypass

### Objective

An unauthenticated request is sent without a valid Entra token or IBCT.

Microsoft Entra ID correctly rejects the request.

### Outcome

| System             | Decision       | Latency |
| ------------------ | -------------- | ------: |
| Microsoft Baseline | ✅ SECURE (401) |       — |
| Aegis L7 Proxy     | ✅ SECURE (401) | ~11.0ms |

### Security Significance

This confirms that the **identity boundary remains effective**.

Aegis complements identity enforcement rather than replacing it.

---

# 📋 Observed Telemetry

Aegis emits structured stdout audit logs capturing runtime execution decisions for security observability and audit workflows.

## Permitted Invocation — Scenario 1

```json
{
  "correlation_id": "req_e8f1ba8d",
  "requesting_identity": "plansom-hr-delegation-agent",
  "tool_action": "fetch_planning_data",
  "resource_context": {
    "raw_target": "{\"department\": \"hr_department\", \"data_type\": \"goals\"}"
  },
  "policy_decision": "PERMIT",
  "reason": "Mathematical bounds verified"
}
```

## Denied Invocation — Confused Deputy / Scenario 2

```json
{
  "correlation_id": "req_7b88b28d",
  "requesting_identity": "plansom-hr-delegation-agent",
  "tool_action": "fetch_planning_data",
  "resource_context": {
    "raw_target": "{\"department\": \"executive_board\", \"data_type\": \"goals\"}"
  },
  "policy_decision": "DENY",
  "reason": "Schema breach: 'executive_board' does not match '^hr_department$'"
}
```

These events provide a machine-readable audit trail for downstream security monitoring, incident investigation, and compliance workflows.

---

# 🚀 How to Reproduce

## Prerequisites

Install the following:

* Docker
* Docker Compose
* Python 3.10+
* A valid Aegis API key

---

## 1. Clone the Repository

```bash
git clone https://github.com/your-org/plansom-aegis-poc.git
cd plansom-aegis-poc
```

---

## 2. Configure Environment Variables

Create a `.env` file in the repository root:

```env
AEGIS_API_KEY=your_aegis_ciso_key
```

> ⚠️ **Do not commit `.env` or API credentials to Git.**

Make sure `.env` is included in `.gitignore`:

```gitignore
.env
```

---

## 3. Deploy the Execution Perimeter

Start the PostgreSQL target, mock Plansom gateway, Microsoft baseline components, and Aegis sidecar:

```bash
docker-compose up -d --build
```

Verify that the containers are running:

```bash
docker-compose ps
```

---

## 4. Execute the Defense-in-Depth Matrix Benchmark

Run the benchmark simulation:

```bash
python run_matrix_benchmark.py
```

The benchmark executes all four scenarios and compares the Microsoft baseline against the Aegis L7 execution boundary.

---

## 5. Inspect the Aegis Audit Stream

View the Aegis sidecar logs:

```bash
docker-compose logs aegis-sidecar
```

For live streaming:

```bash
docker-compose logs -f aegis-sidecar
```

---

# 🔐 Security Model

The POC demonstrates a layered security architecture:

| Layer                                  | Security Responsibility                                        | Example                     |
| -------------------------------------- | -------------------------------------------------------------- | --------------------------- |
| **Identity**                           | Establish who is making the request                            | Microsoft Entra ID          |
| **Static Schema Verification**         | Ensure JSON payload structures are valid                       | Azure API Management (APIM) |
| **Contextual Execution Authorization** | Enforce agent-specific delegation limits at runtime            | **Aegis L7 Sidecar**        |
| **Capability Binding**                 | Bind permitted actions and resources to the invocation context | **IBCT**                    |
| **Downstream Target**                  | Execute requests that survive the policy boundary              | PostgreSQL                  |

### Static vs. Contextual Authorization

The distinction demonstrated by this POC is:

```text
STATIC AUTHORIZATION
────────────────────

"Is this request structurally valid?"

        │
        ▼
   APIM Schema
        │
        ├── Valid ──────► Continue
        └── Invalid ────► Reject


CONTEXTUAL AUTHORIZATION
────────────────────────

"Is this specific action authorized
for this specific agent in this
specific delegation context?"

        │
        ▼
   Aegis IBCT
        │
        ├── Authorized ─► Continue
        └── Unauthorized ► Reject
```

The key security property is that **authorization is enforced contextually on the actual runtime invocation**, preventing the Confused Deputy problem even when broad identity roles and static schemas are satisfied.

---

# 🛡️ Defense-in-Depth Positioning

The POC is intended to demonstrate complementary controls rather than competing security products.

```text
┌──────────────────────────────────────────────────┐
│                    USER / AGENT                  │
└────────────────────────┬─────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────┐
│ Microsoft Entra ID                              │
│ Identity & Authentication                        │
└────────────────────────┬─────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────┐
│ Azure Prompt Shields / Cognitive Controls        │
│ Prompt & Intent Safety                           │
└────────────────────────┬─────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────┐
│ Azure API Management                             │
│ Static API / JSON Schema Validation              │
└────────────────────────┬─────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────┐
│ Semantic Kernel                                  │
│ Agent Orchestration / Function Invocation       │
└────────────────────────┬─────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────┐
│ Aegis Zero-Trust Sidecar                        │
│ Dynamic Contextual Execution Authorization      │
│                                                  │
│ IBCT + Tool + Resource + Parameter Constraints  │
└────────────────────────┬─────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────┐
│ Downstream Database / Service                    │
└──────────────────────────────────────────────────┘
```

---

# ⚠️ Disclaimer

## Defense-in-Depth, Not a Replacement

This POC does **not** suggest that Microsoft Agentic Security is broken or ineffective.

As demonstrated by Scenarios 3 and 4:

* **Microsoft Entra ID** effectively enforces identity boundaries.
* **Azure API Management** effectively enforces static API/schema constraints.
* **Prompt Shields and related cognitive controls** provide important protection at the cognitive boundary.

Aegis provides a **complementary runtime execution boundary** for contextual authorization of autonomous agent actions.

The purpose of this POC is to demonstrate that **authentication and static schema validation do not necessarily establish contextual authorization for every autonomous agent action**.

---

## Simulated Target

The downstream database is an **isolated local PostgreSQL container**, and the MCP gateway is a mock implementation.

This POC does **not** connect to Plansom's live Azure production virtual network or production databases.

---

## POC Scope

This demonstration focuses specifically on the distinction between:

* Authentication
* Static schema validation
* Contextual runtime authorization
* Agent-specific delegation boundaries

A production deployment would require additional defense-in-depth controls covering areas such as:

* Prompt injection
* Jailbreaks
* Identity and access management
* Agent memory poisoning
* Tool poisoning
* Supply-chain security
* Untrusted external data
* Output validation
* Data exfiltration
* Secrets management
* Network security
* Downstream service authorization
* Monitoring and incident response

---

# 📁 Repository Structure

```text
plansom-aegis-poc/
│
├── run_matrix_benchmark.py     # Side-by-side execution benchmark
│
├── docker-compose.yml          # Local POC infrastructure
│
├── mock-gateway/               # Microsoft baseline and upstream endpoints
│
├── init-db/                    # PostgreSQL schema and initialization
│
├── .env                        # Local credentials (not committed)
│
├── .gitignore
│
└── README.md
```

---

# 🧪 Expected Result

When the benchmark is executed, the key security distinction should look like this:

```text
                     Agent Invocation
                            │
                            ▼
                 ┌────────────────────┐
                 │ Is caller valid?   │
                 └─────────┬──────────┘
                           │
                           ▼
                    Entra / Identity
                           │
                           ▼
                 ┌────────────────────┐
                 │ Is payload valid?  │
                 └─────────┬──────────┘
                           │
                           ▼
                      APIM Schema
                           │
                           ▼
              ┌───────────────────────────┐
              │ Is THIS action authorized │
              │ for THIS agent/context?   │
              └─────────────┬─────────────┘
                            │
                            ▼
                       Aegis IBCT
                       /        \
                      /          \
                   DENY          PERMIT
                    │              │
                    ▼              ▼
                 HTTP 422       HTTP 200
                    │              │
                    ▼              ▼
              No DB Request    Target DB
```

## Key Takeaway

The POC demonstrates a fundamental distinction in autonomous-agent security:

> **"Is the request authenticated and structurally valid?" is not always equivalent to "Is this specific runtime action authorized for this agent?"**

Microsoft's identity, cognitive, and API perimeter controls address important parts of the security boundary.

**Aegis adds contextual, invocation-level authorization at the execution boundary.**

Together, these layers provide a stronger **defense-in-depth architecture for autonomous agent execution**.