# Aegis + Plansom Defense-in-Depth Threat Model

## Objective
This document outlines the formal threat model and the 14-point attack matrix used to benchmark the Microsoft security baseline against an architecture augmented with the Aegis Layer 7 Zero-Trust Sidecar. 

The threat matrix relies on **independent downstream execution evidence** `(DB:1 or DB:0)`. By querying a restricted PostgreSQL audit table before and after each scenario, we programmatically verify whether a threat was neutralized at the network edge or if it breached the database engine[cite: 1].

## Threat Matrix & Measured Evidence

| ID | Threat Vector | MS Baseline Result | Aegis Proxy Result | Security Property Evaluated |
| :--- | :--- | :--- | :--- | :--- |
| **T01** | Legitimate In-Scope Execution | ALLOW `200 (DB:1)` | ALLOW `200 (DB:1)` | Valid capability execution |
| **T02** | Missing Tokens | SECURE `401 (DB:0)` | SECURE `401 (DB:0)` | Baseline identity boundary |
| **T03** | Invalid/Corrupted JWT | SECURE `401 (DB:0)` | SECURE `401 (DB:0)` | Baseline cryptographic validation |
| **T04** | Insufficient Entra Role | SECURE `403 (DB:0)` | SECURE `403 (DB:0)` | Baseline RBAC enforcement |
| **T05** | Invalid Static Schema Enum | SECURE `400 (DB:0)` | SECURE `422 (DB:0)` | Baseline APIM validation |
| **T06** | Confused Deputy | **VULNERABLE `200 (DB:1)`** | **SECURE `422 (DB:0)`** | Invocation / resource binding |
| **T07** | Context Tampering | **VULNERABLE `200 (DB:1)`** | **SECURE `422 (DB:0)`** | Parameter modification post-auth |
| **T08** | Cross-Agent Usage | **VULNERABLE `200 (DB:1)`** | **SECURE `403 (DB:0)`** | Identity-to-capability subject pinning |
| **T09** | Tool Substitution | SECURE `404 (DB:0)` | SECURE `403 (DB:0)` | Explicit tool/action allowlisting |
| **T10** | Data Type Mutation | **VULNERABLE `200 (DB:1)`** | **SECURE `422 (DB:0)`** | Parameter constraint boundary |
| **T11** | Capability Tampering | **VULNERABLE `200 (DB:1)`** | **SECURE `403 (DB:0)`** | IBCT cryptographic integrity |
| **T12** | Direct Backend Bypass | VULNERABLE `(Exposed)` | **SECURE `(Drop)`** | Network isolation enforcement |
| **T13** | Exact Capability Replay (JTI) | **VULNERABLE `200 (DB:1)`** | **SECURE `409 (DB:0)`** | Nonce state & replay prevention |
| **T14** | Expired Capability Token | **VULNERABLE `200 (DB:1)`** | **SECURE `401 (DB:0)`** | Cryptographic validity window (`exp`) |

## Key Findings & Boundary Analysis

### 1. The Contextual Execution Gap (T06, T07, T10)
The Microsoft baseline successfully blocks malformed requests and unauthenticated access, yielding `(DB:0)`. However, it permits structurally valid payloads that violate the agent's contextual delegation. In T06, the MS Baseline processed the request all the way to the database `(DB:1)`. Aegis dynamically scoped the IBCT bounds using strict regex, neutralizing the threat at the proxy edge `(DB:0)`[cite: 1].

### 2. Baseline Configuration Strengths (T09)
The Microsoft Baseline proved effective at preventing Tool Substitution (T09). Because the baseline gateway was configured with explicit tool allowlisting, it successfully dropped unauthorized API calls `(DB:0)` before reaching the database, independently matching Aegis's containment properties[cite: 1].

### 3. State & Replay Vulnerabilities (T13, T14)
Static gateways evaluate structure, not execution state. The MS Baseline allowed the exact same authorized payload to be replayed, generating multiple execution records `(DB:1)`. Aegis utilizes a JTI nonce cache and strict TTL expirations, ensuring the payload is neutralized on the second attempt `(DB:0)`[cite: 1].

### 4. Cross-Agent Use of Authorization Material (T08)
If an attacker compromises Agent B and attempts to submit a valid capability token assigned to Agent A, a gateway strictly evaluating structural validity will process it `(DB:1)`. Aegis pins the `sub` claim of the Entra JWT to the `sub` claim of the capability token, blocking cross-agent misuse at the network edge `(DB:0)`[cite: 1].