# Microsoft Controls & Evidence Matrix

## Objective
A fair security comparison must evaluate Aegis against the strongest applicable controls of the baseline platform. This document outlines which Microsoft security capabilities (Entra ID, API Management, Downstream Authorization) are modeled in this PoC, which are simulated, and how Aegis provides an additive, independent security property[cite: 1].

The core thesis is not that Microsoft's controls are ineffective, but rather that **identity authorization** ("this agent may use this API") is distinct from **invocation authorization** ("this agent may perform this exact operation, on this specific resource, within this exact time window").

## Modeled Control Matrix

| Microsoft Control | PoC Implementation | Test Scenarios Addressed | Residual Risk (Addressed by Aegis) |
| :--- | :--- | :--- | :--- |
| **Entra Agent ID & JWT Validation** | Simulated via `identity_provider.py` and Node.js JWT verification. | **T02, T03** | Standard JWTs prove identity, but do not cryptographically bind identity to specific execution parameters. |
| **Role-Based Access Control (RBAC)** | Gateway enforces the `Agent.Planning.Read` role claim. | **T04** | Coarse roles grant broad access (e.g., all planning data) rather than task-scoped least privilege. |
| **API Tool / Action Allowlisting** | Gateway explicitly rejects unsupported tools (returning HTTP 404). | **T09** | While explicit allowlists prevent invoking wrong APIs, they do not restrict the *context* inside a permitted API. |
| **Azure APIM Schema Validation** | Modeled via `AJV` strict JSON Schema validation (`validate-content` policy equivalent). | **T05** | APIM validates structure (e.g., ensuring `department` is a string matching a static enum), but cannot dynamically restrict bounds per-invocation. |
| **Downstream DB Authorization** | PostgreSQL Row-Level Security (RLS) under a restricted `NOSUPERUSER` runtime role. | **T06, T07, T10** | RLS protects the DB, but relies on the gateway properly asserting the identity. It is a last line of defense, whereas Aegis drops unauthorized context at the network edge (`DB:0`). |

## Out of Scope Controls
* **Microsoft Agent Governance Toolkit / Semantic Kernel:** While previous iterations of this PoC tested in-process orchestration, this benchmark strictly measures **out-of-process network boundary enforcement**. In-process runtime governance is highly effective but vulnerable if the orchestrator process itself is compromised.
* **Live Azure Key Rotation:** Local Entra ID tokens use static symmetric keys (HS256) for simulation simplicity, rather than live JWKS endpoints.
* **Token Revocation (CAE):** Continuous Access Evaluation is not modeled. Aegis addresses token lifecycle strictly via exact JTI nonce consumption and short-lived expiration claims (`exp`).

## The Incremental Aegis Value
The PoC proves that a valid agent identity and a valid API request are not sufficient to authorize every possible invocation[cite: 1]. Aegis adds an independent enforcement point that binds authorization to the individual tool execution without altering the underlying Microsoft identity topology[cite: 1].