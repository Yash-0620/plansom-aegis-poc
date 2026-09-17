# Plansom + Aegis Defense-in-Depth Proof of Concept

## Value Objective

This Proof of Concept (PoC) is a controlled, comparative security evaluation. It benchmarks a **Microsoft Security Baseline (Microsoft Entra ID + Azure API Management)** against an architecture augmented with the **Aegis Layer 7 Zero-Trust Sidecar**.

The central hypothesis evaluates whether static identity, API-gateway schemas, and agent-governance controls remain sufficient when authorization must be **cryptographically bound to an individual tool invocation, its dynamic parameters, resource scope, and validity window**.

The goal is **not** to replace Microsoft's identity or API security controls. Instead, this PoC demonstrates how Aegis can add an independent, invocation-bound enforcement layer to an existing Microsoft stack.

While Entra ID and APIM govern:

* **Who is calling the API**
* **Whether the request is structurally valid**

a **Contextual Execution Gap** can remain at runtime.

Aegis addresses this gap by enforcing dynamic, stateless **Invocation-Bound Capability Tokens (IBCTs)** at the network edge. This constrains an agent's execution to the resources and operations delegated for that specific invocation and helps mitigate the **Confused Deputy Problem**.

---

## Architecture Flow

The PoC runs a localized, containerized pipeline that simulates Plansom's delegation engine and directly compares the Microsoft Baseline against the Aegis Layer 7 proxy.

The architecture strictly isolates the protected upstream:

* The **Microsoft Baseline** is exposed on port `8001`.
* The **Aegis-protected upstream** is completely unmapped from the host.
* The protected upstream can only be reached through the stateless Aegis proxy on port `8080`.
* An independent PostgreSQL database operates under a highly restricted `NOSUPERUSER` role with strict **Row-Level Security (RLS)**.
* The database provides programmatic evidence of whether a request actually reached the database execution engine.

```text
                               MCP / Tool Invocation Attempt
                                             │
             ┌───────────────────────────────┴───────────────────────────────┐
             ▼                                                               ▼
   Path A: Microsoft Baseline                                      Path B: Aegis Secured
         (Port 8001)                                                    (Port 8080)
             │                                                               │
             ▼                                                               ▼
      APIM Static Schema                                      Aegis L7 Sidecar Proxy (IBCT)
      Entra Role Check                                         (Ed25519 Dynamic Evaluation)
             │                                                               │
             ▼                                                               ▼
    Exposed Gateway Route                                         Isolated Upstream Route
             │                                                               │
             └───────────────────────────────┬───────────────────────────────┘
                                             ▼
                               Independent Database Layer
                                (PostgreSQL RLS + Ledger)
```

---

# The 14-Point Attack Harness

The test suite, `advanced_attack_harness.py`, evaluates **14 distinct runtime delegation scenarios** to identify where perimeter controls succeed and where contextual execution gaps remain.

The harness explicitly verifies downstream database execution using `DB:1` or `DB:0` to provide evidence of whether a request crossed the enforcement boundary.

---

## 1. Standard Perimeter Threats

### Handled by the Microsoft Baseline

The Microsoft baseline successfully blocks conventional security violations, validating its effectiveness for static identity boundaries.

| Test    | Scenario                     | Expected Result |
| ------- | ---------------------------- | --------------- |
| **T02** | Missing Entra JWT            | `401`           |
| **T03** | Corrupted Entra JWT          | `401`           |
| **T04** | Insufficient Entra Role      | `403`           |
| **T05** | Static APIM Schema Violation | `400`           |

---

## 2. The Contextual Execution Gap

### T06, T07, T10

The PoC highlights the limitations of relying exclusively on static gateways for dynamic agent execution.

In scenario **T06 (Confused Deputy)**, an agent delegates an action intended for `hr_department` but requests `executive_board` instead.

### Microsoft Baseline

The Microsoft Baseline allows the request:

```text
HTTP 200
DB:1
```

The request is permitted because:

* The APIM schema statically permits both departments.
* Entra ID grants the agent broad read access.
* The request is structurally valid.

### Aegis Proxy

The Aegis proxy rejects the request:

```text
HTTP 422
DB:0
```

The Aegis IBCT is dynamically scoped specifically to:

```text
^hr_department$
```

for that individual execution.

This demonstrates the distinction between **static authorization** and **invocation-specific contextual authorization**.

---

## 3. Advanced Capability Theft & Replay Defenses

### T08 — Capability Theft

Aegis explicitly binds the IBCT to the Entra JWT `sub` claim.

If Agent B obtains Agent A's capability token and attempts to use it, Aegis rejects the transaction:

```text
HTTP 403
DB:0
```

This prevents a capability issued to one agent identity from being reused by another identity.

---

### T13 — Exact Capability Replay

Aegis stores the unique `jti` nonce associated with the capability.

The first use of a valid capability can reach the downstream execution path:

```text
HTTP 409
DB:1
```

A subsequent replay of the same capability is detected and blocked:

```text
HTTP 409
DB:0
```

This provides replay protection by tracking the unique invocation identifier.

---

### T14 — Expired Capability

Each capability contains an expiration (`exp`) claim defining its execution window.

Once the capability expires, the Aegis sidecar rejects the invocation:

```text
HTTP 401
DB:0
```

This constrains authorization to the capability's defined validity period.

---

# Independent Downstream Evidence

To demonstrate that Aegis operates as a **verifiable network enforcement boundary**, the test harness queries the PostgreSQL execution ledger:

```text
database_audit_log
```

via the:

```text
sys/audit
```

endpoint before and after every scenario.

The harness dual-validates:

1. The expected HTTP response status.
2. The expected downstream database execution count.

### Database Evidence

| Result | Meaning                                                                            |
| ------ | ---------------------------------------------------------------------------------- |
| `DB:1` | The request crossed the network gateway and reached the database execution engine. |
| `DB:0` | The request was neutralized at the edge, resulting in zero SQL queries executed.   |

This independent downstream evidence allows the PoC to distinguish between:

* A request being rejected by an application.
* A request actually being stopped before reaching the protected execution layer.

---

# How to Reproduce

## Prerequisites

The following are required to run the PoC:

* Docker
* Docker Compose
* Python 3.10+
* Python packages:

  * `requests`
  * `pyjwt`
  * `python-dotenv`
* An **Aegis Cloud Console** account for telemetry visualization

---

## 1. Configure Environment Variables

Create a `.env` file in the repository root:

```dotenv
AEGIS_API_KEY=your_aegis_ciso_key
```

> **Important:** Do not commit `.env` or API keys to source control. Add `.env` to `.gitignore`.

---

## 2. Deploy the Execution Perimeter

Start the PostgreSQL target, Microsoft baseline gateway, isolated upstream gateway, and stateless Aegis sidecar:

```bash
docker-compose up -d --build
```

> **Note:** The Aegis sidecar pulls directly from the public GitHub Container Registry (`ghcr.io/...:latest`), demonstrating a zero-code, drop-in enterprise integration.

---

## 3. Execute the 14-Point Attack Harness

Run the deterministic benchmark simulation:

```bash
python advanced_attack_harness.py
```

Upon execution, the harness produces a **14/14 `[PASS]` matrix** in the terminal when all configured scenarios meet their expected results.

Comprehensive telemetry is also synchronized with the configured Aegis Cloud Console dashboard.

---

# Expected Test Coverage

The 14-point harness covers multiple classes of security scenarios, including:

| Security Category        | Coverage                           |
| ------------------------ | ---------------------------------- |
| Identity validation      | Entra JWT presence and integrity   |
| Role authorization       | Entra role enforcement             |
| Schema validation        | Static APIM-style JSON validation  |
| Contextual authorization | Invocation-specific resource scope |
| Confused Deputy          | Out-of-scope resource execution    |
| Capability theft         | Agent identity binding             |
| Token replay             | `jti`-based replay protection      |
| Capability expiration    | `exp`-based validity enforcement   |
| Direct network access    | Protected upstream isolation       |
| Database containment     | `DB:0` execution verification      |
| Downstream evidence      | PostgreSQL execution ledger        |
| Runtime enforcement      | Layer 7 Aegis sidecar              |

---

# Security Model

The PoC demonstrates a defense-in-depth model in which each layer addresses a different security concern:

```text
┌──────────────────────────────────────────────────────────────┐
│                         Agent / MCP                          │
│                                                              │
│                 Tool Invocation Attempt                      │
└──────────────────────────────┬───────────────────────────────┘
                               │
                 ┌─────────────┴─────────────┐
                 │                           │
                 ▼                           ▼
       Microsoft Baseline             Aegis Secured Path
       Port 8001                       Port 8080
                 │                           │
                 ▼                           ▼
          Entra ID + APIM          IBCT + Ed25519 + L7
                 │                           │
                 │                    Contextual Scope
                 │                    Identity Binding
                 │                    Expiration
                 │                    Replay Protection
                 │                           │
                 └─────────────┬─────────────┘
                               │
                               ▼
                    Protected Database Layer
                               │
                               ▼
                   PostgreSQL RLS + Ledger
```

---

## Layer Responsibilities

| Layer                        | Primary Responsibility                      | Mechanism            |
| ---------------------------- | ------------------------------------------- | -------------------- |
| **Identity**                 | Establish the requesting agent's identity   | Microsoft Entra ID   |
| **Role Authorization**       | Establish permitted API roles               | Entra ID roles       |
| **Static Validation**        | Validate request structure                  | Azure API Management |
| **Contextual Authorization** | Authorize the exact invocation              | Aegis IBCT           |
| **Cryptographic Binding**    | Bind authorization to invocation attributes | Ed25519              |
| **Replay Protection**        | Prevent capability reuse                    | `jti` nonce          |
| **Temporal Enforcement**     | Limit execution validity                    | `exp`                |
| **Database Security**        | Restrict database access                    | PostgreSQL RLS       |
| **Execution Evidence**       | Verify downstream execution                 | `database_audit_log` |

---

# Core Security Property

The key security property demonstrated by the PoC is:

> **Authorization decisions are cryptographically bound to the specific tool invocation, dynamic parameters, resource scope, agent identity, and validity window.**

The Aegis layer is intended to **complement rather than replace** Microsoft Entra ID, Azure API Management, or agent governance controls.

The resulting architecture separates:

```text
Identity
   +
Static Request Validation
   +
Invocation-Bound Authorization
   +
Downstream Database Controls
   +
Independent Execution Evidence
```

This provides multiple enforcement and verification points across the request lifecycle.

---

# Repository Components

| File / Component             | Purpose                                                       |
| ---------------------------- | ------------------------------------------------------------- |
| `advanced_attack_harness.py` | Executes the 14-point security benchmark                      |
| `docker-compose.yml`         | Defines the local PoC infrastructure                          |
| `MICROSOFT_CONTROLS.md`      | Documents the Microsoft controls modeled by the PoC           |
| `LIMITATIONS.md`             | Documents technical limitations and assumptions               |
| `THREAT_MODEL.md`            | Documents threats, attack scenarios, and security assumptions |
| `.env`                       | Local environment configuration and secrets                   |

---

# Important Security Considerations

This PoC is intended for controlled evaluation and should not be interpreted as a production security assessment.

In particular:

* Keep all credentials and API keys outside source control.
* Do not use production credentials in the PoC environment.
* Review the threat model before exposing any component beyond the local test environment.
* Validate container image provenance and pin production image versions rather than relying on `latest`.
* Treat benchmark results as environment-dependent measurements.
* Independently validate cryptographic, network, and database controls before production deployment.

---

# Related Documentation

For additional details, see:

* [`MICROSOFT_CONTROLS.md`](MICROSOFT_CONTROLS.md) — Microsoft security controls modeled by the PoC
* [`LIMITATIONS.md`](LIMITATIONS.md) — Technical limitations and assumptions
* [`THREAT_MODEL.md`](THREAT_MODEL.md) — Threat model and attack scenarios

---

# Summary

This PoC evaluates whether authorization for autonomous agent execution can be constrained to the **specific operation that was delegated**, rather than relying exclusively on the agent's identity and static permissions.

The architecture combines:

**Microsoft Entra ID**

→ identity and role authorization

**Azure API Management**

→ static API/schema validation

**Aegis Layer 7 Sidecar**

→ invocation-bound contextual authorization

**PostgreSQL RLS + Execution Ledger**

→ downstream protection and independent execution evidence

The resulting defense-in-depth architecture provides distinct controls for **identity, structural validity, contextual execution authorization, replay protection, expiration, network isolation, and downstream verification**.