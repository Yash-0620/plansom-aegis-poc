# Plansom Autonomous Delegation + Aegis Defense-in-Depth POC

## Value Objective

This Proof of Concept (POC) is a controlled, comparative security evaluation. It benchmarks the **Microsoft Security Baseline (Microsoft Entra ID + Azure API Management)** against an architecture augmented with the **Aegis Layer 7 Zero-Trust Sidecar**.

The central hypothesis evaluates whether static identity, API-gateway schemas, and agent-governance controls remain sufficient when authorization must be **cryptographically bound to an individual tool invocation, its dynamic parameters, resource scope, and validity window**.

Microsoft's agentic security controls — Entra ID, Azure API Management, and Agent Governance Toolkit — are highly effective at protecting identity and static perimeter boundaries. However, a **Contextual Execution Gap** can remain at runtime.

If an agent with a broadly permissive downstream role hallucinates or is compromised through prompt injection, it may execute syntactically valid requests against out-of-scope resources, creating a potential **Confused Deputy** scenario.

This repository demonstrates how **Aegis closes this contextual execution gap** by enforcing dynamic, stateless **Invocation-Bound Capability Tokens (IBCTs)** at the network edge.

---

## Addressing the Microsoft Agentic Governance Architecture

This upgraded 14-point POC was specifically engineered to address the relevant Microsoft ecosystem capabilities:

1. **Microsoft Agent Governance Toolkit & Semantic Kernel**

   The POC includes `plansom_kernel_sim.py`, demonstrating native integration with Microsoft Semantic Kernel via `FilterTypes.FUNCTION_INVOCATION`.

   Microsoft's toolkit evaluates policy *in-process*, while Aegis enforces authorization *out-of-process* at the TCP/HTTP network layer. This provides an independent enforcement boundary intended to contain requests even if the Python/Node agent runtime is compromised.

2. **Entra Agent ID Authorization**

   The mock gateway natively validates Entra JWTs and strictly enforces the `Agent.Planning.Read` role.

3. **Azure API Management (APIM)**

   The gateway enforces a strict, static JSON Schema using behavior equivalent to APIM `validate-content`.

   The POC demonstrates that while APIM-style schema validation can block malformed requests, static structural validation alone cannot determine whether an otherwise valid request targets the resource authorized for a particular delegation.

4. **Direct Bypass, Token Replay & Expiration**

   The harness explicitly tests:

   * Direct Network Bypass (`T12`)
   * JTI Nonce Replay (`T13`)
   * Expired Capability Execution (`T14`)

5. **Latency & Operational Cost**

   The Aegis sidecar evaluates Ed25519 cryptography, checks memory-cached nonces, and validates schemas locally in **< 20 ms** in the POC environment.

   This demonstrates a decentralized, vendor-agnostic runtime enforcement approach without requiring every authorization decision to traverse a centralized cloud API-management layer.

---

## Architecture Flow

The POC runs a localized, containerized pipeline that simulates Plansom's delegation engine and directly compares the Microsoft Baseline against the Aegis Layer 7 proxy.

An independent PostgreSQL execution ledger provides evidence of whether a request actually reached the downstream database.

```text
                         User Delegation Prompt
                                   │
                                   ▼
                   Microsoft Semantic Kernel Orchestrator
                                   │
                    MCP / Function Invocation Attempt
                                   │
        ┌──────────────────────────┴──────────────────────────┐
        ▼                                                     ▼
  MS Baseline (Port 8001)                          Aegis Proxy (Port 8080)
        │                                                     │
        ▼                                                     ▼
   APIM Static Schema                                   L7 Sidecar Ed25519
   Entra Role Check                                     IBCT Dynamic Evaluation
        │                                                     │
        ▼                                                     ▼
  Target Downstream                                     Target Downstream
        │                                                     │
        ▼                                                     ▼
   DB Audit Ledger                                       DB Audit Ledger
```

---

# The 14-Point Attack Harness

The test suite, `advanced_attack_harness.py`, evaluates **14 distinct runtime delegation scenarios** to identify where perimeter controls succeed and where contextual execution gaps remain.

## 1. Standard Perimeter Threats

### Handled by the Microsoft Baseline

The Microsoft baseline successfully blocks conventional security violations, validating its effectiveness for static identity boundaries.

| Test  | Scenario                     | Expected Result |
| ----- | ---------------------------- | --------------- |
| `T02` | Missing Entra JWT            | HTTP `401`      |
| `T03` | Corrupted Entra JWT          | HTTP `401`      |
| `T04` | Insufficient Entra Role      | HTTP `403`      |
| `T05` | Static APIM Schema Violation | HTTP `400`      |

---

## 2. The Contextual Execution Gap

### T06, T07, T10

The POC highlights the limitation of relying exclusively on static gateway controls for dynamic agent execution.

In scenario **T06 (Confused Deputy)**, an agent delegates an action intended for `hr_department` but requests `executive_board` instead.

### Microsoft Baseline

The request is allowed (`HTTP 200`) because:

* The APIM schema statically permits both departments.
* Entra ID grants the agent broad read access.
* The request is structurally valid.

### Aegis Proxy

The request is rejected (`HTTP 422`) because the Aegis IBCT is dynamically scoped specifically to:

```text
^hr_department$
```

for that individual execution.

This demonstrates the distinction between:

* **Identity authorization** — who is allowed to invoke the API.
* **Structural validation** — whether the request conforms to the expected schema.
* **Contextual execution authorization** — whether this exact invocation is permitted within the delegated scope.

---

## 3. Advanced Capability Theft & Replay Defenses

### T08 — Capability Theft

Aegis binds the IBCT to the Entra JWT `sub` claim.

If Agent B obtains Agent A's capability token and attempts to use it, Aegis rejects the transaction with:

```text
HTTP 403
```

This prevents a capability issued to one agent identity from being reused by another identity.

---

### T13 — Exact Capability Replay

Aegis stores the unique `jti` nonce associated with an invocation.

If an intercepted capability token is replayed, the previously consumed `jti` is detected and the request is rejected:

```text
HTTP 409
```

This provides protection against exact-token replay within the configured execution window.

---

### T14 — Expired Capability

Each capability contains an expiration (`exp`) claim defining its execution window.

Once the capability expires, the sidecar rejects the invocation:

```text
HTTP 401
```

This ensures that authorization is constrained not only by identity and resource scope, but also by time.

---

# Independent Database Execution Ledger

To demonstrate that Aegis operates as an actual **network enforcement boundary** rather than merely a passive monitoring component, the PostgreSQL database is configured with an execution ledger:

```text
database_audit_log
```

The ledger records downstream execution activity and provides an independent way to verify whether a request actually reached the database.

## Aegis Proxy Containment Results

For out-of-scope invocations intercepted by Aegis, the expected ledger evidence is:

```text
0 bytes forwarded
0 queries executed
0 rows returned
```

This provides an independent verification point outside the proxy itself.

---

# How to Reproduce

## Prerequisites

* Docker & Docker Compose
* Python 3.10+
* An Aegis Cloud Console account for telemetry

---

## 1. Configure Environment Variables

Create a `.env` file in the repository root:

```dotenv
AEGIS_API_KEY=your_aegis_ciso_key
AZURE_OPENAI_API_KEY=your_optional_azure_key
```

> `AZURE_OPENAI_API_KEY` is optional and is used for Semantic Kernel testing.

---

## 2. Deploy the Execution Perimeter

Start the PostgreSQL target, mock Plansom gateway, and Aegis sidecar:

```bash
docker-compose up -d --build
```

---

## 3. Execute the 14-Point Attack Harness

Run the benchmark simulation:

```bash
python advanced_attack_harness.py
```

The harness executes the configured attack scenarios and reports the resulting HTTP status and enforcement behavior.

---

## 4. Execute the Semantic Kernel Integration

Run the Microsoft Agent Governance simulator:

```bash
python plansom_kernel_sim.py
```

This demonstrates the Semantic Kernel function-invocation integration and the relationship between in-process governance and the independent Aegis network enforcement boundary.

---

## 5. Verify the Database Execution Ledger

Extract execution evidence directly from PostgreSQL:

```bash
docker-compose exec postgres-db \
  psql -U postgres -d plansom_db \
  -c "SELECT correlation_id, tool_invoked, target_resource, execution_status, rows_returned FROM database_audit_log ORDER BY timestamp DESC LIMIT 15;"
```

This allows the test results to be correlated with actual downstream database activity.

---

# Security Model

The POC demonstrates a **decoupled, defense-in-depth security model**.

| Layer                          | Security Responsibility                                | Enforcement Mechanism       |
| ------------------------------ | ------------------------------------------------------ | --------------------------- |
| **Identity**                   | Establish who is making the request                    | Microsoft Entra ID          |
| **Static Schema Verification** | Ensure JSON payloads are structurally valid            | Azure API Management (APIM) |
| **Execution Authorization**    | Enforce contextual delegation limits at runtime        | **Aegis L7 Sidecar**        |
| **Downstream Target**          | Execute surviving requests and maintain an audit trail | PostgreSQL                  |

---

## Core Security Property

The key security property demonstrated by the POC is:

> **Authorization decisions are cryptographically bound to the specific tool, parameters, resource scope, and validity window of an individual invocation.**

The purpose of the Aegis layer is **not to replace identity, Azure API Management, or Semantic Kernel**.

Instead, it adds an independent, high-speed runtime authorization boundary that evaluates whether the **exact requested operation** is permitted within the agent's delegated capability, independently of the LLM's current state.

---

# Defense-in-Depth Model

The resulting architecture can be viewed as four complementary security boundaries:

```text
┌─────────────────────────────────────────────────────────────┐
│                         Identity                            │
│                      Microsoft Entra ID                     │
│                                                             │
│  Who is the requesting agent?                               │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                    Structural Validation                    │
│                  Azure API Management                       │
│                                                             │
│  Is the request structurally valid?                         │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                 Contextual Authorization                    │
│                    Aegis L7 Sidecar                         │
│                                                             │
│  Is THIS exact operation authorized for THIS invocation?    │
│                                                             │
│  • Tool                                                     │
│  • Parameters                                               │
│  • Resource scope                                           │
│  • Agent identity                                           │
│  • Expiration                                               │
│  • Replay protection                                        │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                     Downstream Target                       │
│                        PostgreSQL                            │
│                                                             │
│  Execute request + record independent audit evidence        │
└─────────────────────────────────────────────────────────────┘
```

---

# Key Takeaways

The POC is designed to demonstrate the complementary roles of identity, gateway validation, agent governance, and runtime execution authorization.

### Microsoft Baseline

The baseline provides controls for:

* Agent identity
* JWT validation
* Role-based authorization
* API request structure
* In-process agent governance
* Static perimeter enforcement

### Aegis Runtime Layer

The Aegis layer adds controls for:

* Invocation-specific authorization
* Dynamic resource scoping
* Cryptographic capability binding
* Agent identity binding
* Expiration enforcement
* JTI-based replay prevention
* Network-level enforcement
* Independent downstream containment

The resulting security model is therefore **defense in depth**, rather than a replacement of the existing Microsoft security stack.

---

# Repository Components

| File                         | Purpose                                                       |
| ---------------------------- | ------------------------------------------------------------- |
| `advanced_attack_harness.py` | Executes the 14-point security benchmark                      |
| `plansom_kernel_sim.py`      | Simulates Semantic Kernel function-invocation governance      |
| `docker-compose.yml`         | Defines the local POC infrastructure                          |
| `LIMITATIONS.md`             | Documents technical limitations and assumptions               |
| `THREAT_MODEL.md`            | Documents threats, attack scenarios, and security assumptions |
| `.env`                       | Local environment configuration and secrets                   |

---

# Scope & Disclaimer

This repository represents a **controlled Proof of Concept** rather than a production security assessment.

Performance figures, enforcement behavior, and attack outcomes are dependent on the implementation and local test environment.

The POC is intended to demonstrate architectural security properties and provide a reproducible framework for comparing static gateway controls with invocation-level runtime authorization.

For a complete breakdown of technical limitations, port configurations, assumptions, and threat vectors, see:

* [`LIMITATIONS.md`](LIMITATIONS.md)
* [`THREAT_MODEL.md`](THREAT_MODEL.md)

---

## Summary

The POC evaluates a specific security question:

> **Can an authorization decision be constrained to the exact operation an agent was delegated to perform, rather than relying solely on the identity and static permissions associated with that agent?**

The Aegis architecture addresses this question by introducing **Invocation-Bound Capability Tokens (IBCTs)** enforced at the Layer 7 network boundary.

The resulting model combines:

**Entra ID identity + APIM schema validation + Semantic Kernel governance + Aegis contextual authorization + independent database auditing**

to provide multiple, independently enforceable layers of protection for autonomous agent execution.