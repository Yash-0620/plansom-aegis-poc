# Plansom Autonomous Delegation + Aegis Defense-in-Depth POC

## 🎯 Value Objective

This Proof of Concept (POC) is a controlled, comparative security evaluation. It benchmarks a Microsoft security baseline — **Microsoft Entra ID + Azure API Management (APIM)** — against an architecture augmented with the **Aegis Layer 7 Zero-Trust Sidecar**.

The central hypothesis is whether identity, API-gateway, MCP-gateway, and agent-governance controls remain sufficient when authorization must be **cryptographically bound to an individual tool invocation, its parameters, resource scope, and validity window**.

Microsoft's agentic security controls are effective at protecting cognitive, identity, and static perimeter boundaries. However, a **contextual execution gap** can remain at runtime.

For example, an agent may possess a broad downstream role but, due to hallucination, prompt manipulation, or compromised decision-making, request resources outside the scope of its intended delegation. A valid identity and a statically valid API schema do not necessarily prevent this type of **Confused Deputy** scenario.

This repository demonstrates how **Aegis closes this contextual execution gap** by enforcing dynamic, Layer 7 **Invocation-Bound Capability Tokens (IBCT)** independently of downstream database IAM.

---

## 🏗️ Architecture Flow

The POC runs a localized, containerized pipeline that simulates Plansom's delegation engine and directly compares the Microsoft Baseline against the Aegis Layer 7 proxy.

An independent PostgreSQL execution ledger provides evidence of whether a request actually reached the downstream database.

```text
                         User Delegation Prompt
                                  │
                                  ▼
              ┌─────────────────────────────────────┐
              │ Microsoft Orchestrator /            │
              │ Semantic Kernel                      │
              │                                     │
              │ Prompt → MCP / Function Invocation  │
              └──────────────────┬──────────────────┘
                                 │
                       ┌─────────┴─────────┐
                       │                   │
                       ▼                   ▼
              ┌────────────────┐   ┌────────────────┐
              │ MS Baseline    │   │ Aegis Proxy    │
              │                │   │                │
              │ APIM Schema    │   │ L7 Sidecar     │
              │ Entra Role     │   │ IBCT Evaluation│
              └───────┬────────┘   └───────┬────────┘
                      │                    │
                      ▼                    ▼
                 ┌─────────┐          ┌─────────┐
                 │ Target  │          │ Target  │
                 │   DB    │          │   DB    │
                 │         │          │         │
                 │ Audit   │          │ Audit   │
                 │ Ledger  │          │ Ledger  │
                 └─────────┘          └─────────┘
```

### Request Processing

The two paths are evaluated independently:

**Microsoft Baseline**

1. Establish caller identity through Entra ID.
2. Validate the request against the API schema.
3. Apply the configured role and gateway controls.
4. Forward the request to the downstream database if permitted.

**Aegis Path**

1. Establish caller identity.
2. Validate the request through the gateway.
3. Evaluate the Invocation-Bound Capability Token (IBCT).
4. Validate the requested tool, parameters, resource scope, and validity window.
5. Reject unauthorized invocations at Layer 7.
6. Forward only surviving requests to the downstream database.

---

## 📊 The 12-Point Attack Harness

The test suite, `advanced_attack_harness.py`, evaluates **12 distinct runtime delegation scenarios** to identify where perimeter controls succeed and where contextual execution gaps remain.

For a complete breakdown of the individual attack vectors, see [`THREAT_MODEL.md`](THREAT_MODEL.md).

### Benchmark Highlights

#### ✅ Standard Perimeter Threats

The Microsoft baseline successfully blocks several conventional security violations, including:

* **T02** — Unauthenticated requests
* **T03** — Corrupted or invalid JWTs
* **T04** — Insufficient Entra roles
* **T05** — Static API schema violations

These controls demonstrate the effectiveness of identity and traditional gateway-level enforcement.

#### ❌ Residual Runtime Threats

The POC focuses on scenarios such as **T06, T07, and T10**, where an agent possesses a valid identity and submits a syntactically valid request for a resource outside its delegated scope.

For example, an invocation may request:

```text
executive_board
```

while the agent's delegated capability is constrained to:

```regex
^hr_department$
```

Because `executive_board` is still a valid value according to the static API schema, the Microsoft baseline can allow the request to proceed when the identity and role are otherwise valid.

This creates the contextual execution gap demonstrated by the POC.

#### 🛡️ Aegis Containment

Aegis evaluates the invocation context at Layer 7.

When the requested resource violates the agent's invocation-specific capability constraint, Aegis rejects the request before it reaches the downstream database.

Example outcome:

```text
HTTP 422 / 403
Request terminated at Layer 7
0 bytes forwarded downstream
0 database queries executed
```

---

## 📋 Independent Database Execution Ledger

To demonstrate that Aegis operates as an actual **network enforcement boundary** rather than merely a passive monitoring component, the PostgreSQL database is configured with an execution ledger:

```text
database_audit_log
```

The ledger records downstream execution activity and provides an independent way to verify whether a request actually reached the database.

### Microsoft Baseline

For out-of-scope invocations such as T06 and T07, the corresponding correlation IDs appear in the database execution ledger.

This demonstrates that:

```text
Malicious / out-of-scope invocation
            ↓
Microsoft Baseline
            ↓
Database
            ↓
SQL query executed
            ↓
Rows returned
```

### Aegis Proxy

The same malicious payloads are rejected at the Layer 7 boundary:

```text
Malicious / out-of-scope invocation
            ↓
Aegis L7 Sidecar
            ↓
IBCT validation
            ↓
Request rejected
            ↓
Database never reached
```

The expected ledger evidence is:

```text
0 bytes forwarded
0 queries executed
0 rows returned
```

This provides an independent execution-level demonstration of the enforcement boundary.

---

# 🚀 How to Reproduce

## Prerequisites

Ensure the following are installed:

* [Docker](https://www.docker.com/)
* Docker Compose
* Python 3.10+
* An Aegis API key

---

## 1. Configure Environment Variables

Create a `.env` file in the repository root:

```dotenv
AEGIS_API_KEY=your_aegis_ciso_key
```

> **Security:** Do not commit `.env` or API credentials to the repository.

A corresponding `.gitignore` entry should include:

```gitignore
.env
```

---

## 2. Deploy the Execution Perimeter

Start the PostgreSQL target, mock Plansom gateway, and Aegis sidecar:

```bash
docker-compose up -d --build
```

Verify that the containers are running:

```bash
docker-compose ps
```

---

## 3. Execute the 12-Point Attack Harness

Run the benchmark simulation:

```bash
python advanced_attack_harness.py
```

The harness sends the defined test scenarios through both network paths and compares their outcomes.

The resulting output can be used to compare:

* Authentication behavior
* Role enforcement
* Schema validation
* Invocation-level authorization
* Resource-scope enforcement
* Downstream execution
* Database audit results

---

## 4. Verify the Database Execution Ledger

Extract the execution evidence directly from PostgreSQL:

```bash
docker-compose exec postgres-db \
  psql -U postgres -d plansom_db \
  -c "SELECT correlation_id, tool_invoked, target_resource, execution_status, rows_returned FROM database_audit_log ORDER BY timestamp DESC LIMIT 15;"
```

This allows the benchmark results to be independently correlated with actual downstream database execution.

---

# 🔐 Security Model

The POC demonstrates a **decoupled, defense-in-depth security model**.

| Layer                          | Security Responsibility                                | Enforcement Mechanism       |
| ------------------------------ | ------------------------------------------------------ | --------------------------- |
| **Identity**                   | Establish who is making the request                    | Microsoft Entra ID          |
| **Static Schema Verification** | Ensure JSON payloads are structurally valid            | Azure API Management (APIM) |
| **Execution Authorization**    | Enforce contextual delegation limits at runtime        | **Aegis L7 Sidecar**        |
| **Downstream Target**          | Execute surviving requests and maintain an audit trail | PostgreSQL                  |

## Core Security Property

The key security property demonstrated by the POC is:

> **Authorization decisions are cryptographically bound to the specific tool, parameters, resource scope, and validity window of an individual invocation.**

This authorization is enforced immediately before downstream execution and is independent of the downstream database's IAM configuration.

This creates a layered security model:

```text
Identity
   │
   ▼
Static API Controls
   │
   ▼
MCP / Gateway Controls
   │
   ▼
Aegis Invocation-Bound Authorization
   │
   ▼
Downstream Execution
   │
   ▼
Independent Audit Ledger
```

Each layer addresses a different part of the request lifecycle rather than relying on a single authorization mechanism.

---

# 🧪 What This POC Demonstrates

The benchmark is designed to answer a specific security question:

> **Is a valid identity + valid role + valid API schema sufficient to authorize an agent's runtime tool invocation?**

The POC demonstrates that these controls can be insufficient when authorization depends on **dynamic invocation context**.

Aegis introduces an additional authorization boundary that evaluates:

* **Who** is making the request
* **Which tool** is being invoked
* **Which parameters** are being supplied
* **Which resource** is being targeted
* **What scope** the agent has been delegated
* **How long** the authorization remains valid
* **Whether the invocation matches the cryptographically bound capability**

The result is a security boundary between an agent's decision to invoke a tool and the actual execution of that tool against a downstream resource.

---

# ⚠️ Documentation & Limitations

For the complete security analysis, review the supplementary documentation included in this repository.

### [`THREAT_MODEL.md`](THREAT_MODEL.md)

Contains the formal threat model and the 12-point attack matrix, including scenarios covering:

* Authentication failures
* JWT manipulation
* Role escalation
* Static schema violations
* Cryptographic token tampering
* Exact capability replay
* Resource-scope violations
* Cross-department data access
* Runtime delegation abuse

### [`LIMITATIONS.md`](LIMITATIONS.md)

Documents:

* The scope of the local POC
* Intentional network port mappings
* Simulated Microsoft components
* Production Azure equivalents
* Assumptions made by the benchmark
* Boundaries of the experimental environment

> **Important:** This repository is a security Proof of Concept and benchmark environment. It should not be interpreted as a production deployment blueprint without appropriate security review, threat modeling, operational hardening, and validation against the target production environment.

---

# 📁 Repository Structure

```text
plansom-aegis-poc/
│
├── advanced_attack_harness.py
│   └── 12-point side-by-side execution test suite
│
├── docker-compose.yml
│   └── Local POC infrastructure
│
├── mock-gateway/
│   └── server.js
│       └── Gateway logic and audit-routing behavior
│
├── init-db/
│   └── 01-init.sql
│       └── Database initialization and execution ledger
│
├── THREAT_MODEL.md
│   └── Formal threat model and attack definitions
│
├── LIMITATIONS.md
│   └── Technical scope and POC constraints
│
├── .env
│   └── Local credentials — not committed
│
└── README.md
    └── Project documentation
```

---

# 🔎 Expected Security Boundary

The intended architectural distinction can be summarized as follows:

```text
                 STATIC AUTHORIZATION
                 ────────────────────
                 "Who are you?"
                       │
                       ▼
                 "What role do
                  you have?"
                       │
                       ▼
                 "Is this request
                  structurally valid?"
                       │
                       ▼
              ─────────────────────
              CONTEXTUAL AUTHORIZATION
              ─────────────────────
                 "What exactly is
                  this invocation
                  authorized to do?"
                       │
                       ▼
                 Tool + Parameters
                 + Resource Scope
                 + Validity Window
                       │
                       ▼
                Downstream Execution
```

The purpose of the Aegis layer is **not to replace identity, API management, MCP security, or downstream IAM**.

Instead, it adds an independent runtime authorization boundary for the specific execution context of an individual tool invocation.

---

# 📌 Summary

This POC provides a controlled side-by-side evaluation of:

| Capability                                    | Microsoft Baseline | Aegis-Augmented Architecture |
| --------------------------------------------- | :----------------: | :--------------------------: |
| Identity validation                           |          ✅         |               ✅              |
| JWT validation                                |          ✅         |               ✅              |
| Role enforcement                              |          ✅         |               ✅              |
| Static API schema validation                  |          ✅         |               ✅              |
| Runtime resource-scope validation             |       Limited      |                ✅              |
| Invocation-bound authorization                |          —         |                ✅              |
| Parameter-level capability enforcement        |       Limited      |                ✅              |
| Cryptographically bound execution capability  |          —         |                ✅              |
| Layer 7 enforcement before database execution |       Limited      |                ✅              |
| Independent downstream execution evidence     |          ✅         |               ✅              |

**Core takeaway:** traditional identity and perimeter controls establish whether a caller is generally permitted to access an API, while the Aegis Layer 7 sidecar adds an invocation-specific authorization boundary that evaluates whether the **exact requested operation** is permitted within the agent's delegated capability.

---

## 📚 Additional Documentation

* [`THREAT_MODEL.md`](THREAT_MODEL.md) — Threat model and 12-point attack matrix
* [`LIMITATIONS.md`](LIMITATIONS.md) — POC scope, assumptions, and limitations
* `advanced_attack_harness.py` — Executable benchmark
* `docker-compose.yml` — Local infrastructure definition
* `init-db/01-init.sql` — Database execution ledger