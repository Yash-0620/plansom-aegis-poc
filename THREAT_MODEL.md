# Aegis + Plansom Defense-in-Depth Threat Model

## Objective
This document outlines the formal threat model and the expanded 14-point attack matrix used to benchmark the Microsoft security baseline (Entra ID + Azure APIM) against an architecture augmented with the Aegis Layer 7 Zero-Trust Sidecar. 

The objective is to identify residual execution risks when authorization must be contextually bound to an individual tool invocation, its parameters, and its validity window, rather than broadly assigned via identity roles.

## Threat Matrix

| ID | Threat Vector | MS Baseline (APIM + Entra) | Aegis L7 Boundary | Security Property Evaluated |
| :--- | :--- | :--- | :--- | :--- |
| **T01** | Legitimate HR Read | ALLOW (200) | ALLOW (200) | Valid capability execution |
| **T02** | Missing Tokens | SECURE (401) | SECURE (401) | Baseline identity boundary |
| **T03** | Invalid/Corrupted JWT | SECURE (401) | SECURE (401) | Baseline cryptographic validation |
| **T04** | Insufficient Entra Role | SECURE (403) | SECURE (403) | Baseline RBAC enforcement |
| **T05** | Invalid Static Schema Enum | SECURE (400) | SECURE (422) | Baseline APIM validation |
| **T06** | Confused Deputy | **VULNERABLE (200)** | **SECURE (422)** | Cross-department resource bounds |
| **T07** | Context Tampering | **VULNERABLE (200)** | **SECURE (422)** | Valid capability context tampering |
| **T08** | Capability Theft | **VULNERABLE (200)** | **SECURE (403)** | Identity-to-token subject (`sub`) pinning |
| **T09** | Tool Substitution | ALLOW (200) | **SECURE (403)** | Malicious action prevention |
| **T10** | Data Type Mutation | **VULNERABLE (200)** | **SECURE (422)** | Parameter constraint binding |
| **T11** | Capability Tampering | ALLOW (200) | **SECURE (403)** | IBCT cryptographic integrity |
| **T12** | Direct Backend Bypass | VULNERABLE (200)* | **SECURE (401)** | Network isolation enforcement |
| **T13** | Exact Capability Replay (JTI) | VULNERABLE (200) | **SECURE (409)** | Nonce state & replay prevention |
| **T14** | Expired Capability Token | VULNERABLE (200) | **SECURE (401)** | Cryptographic validity window (`exp`) |

## Key Findings & Residual Risk Analysis

### 1. The Contextual Execution Gap (T06, T07, T10)
The Microsoft baseline successfully blocks malformed requests (T05), corrupted JWTs (T03), and unauthenticated access (T02). However, it permits structurally valid payloads that violate the agent's contextual delegation. Aegis enforces Invocation-Bound Capability Tokens (IBCT) at Layer 7 using strict regex and numeric bounds, shredding out-of-scope executions (HTTP 422) before downstream transmission.

### 2. State & Replay Vulnerabilities (T13, T14)
Static API gateways evaluate structure, not execution state. The Microsoft Baseline allows the exact same approved payload to be replayed infinitely (T13) or executed hours after the context window has closed (T14). Aegis implements strict TTL expirations and an in-memory JTI nonce cache, guaranteeing that a tool authorization can only be consumed exactly once.

### 3. Capability Theft & Subject Pinning (T08)
If an attacker compromises Agent B and steals a token generated for Agent A, broad network gateways often permit the execution if both agents share the same VPC or generic APIM subscription. Aegis intercepts the Entra ID identity token, extracts the `sub` claim, and ensures it perfectly matches the `sub` claim pinned inside the Ed25519 signature, entirely neutralizing token theft (HTTP 403).

### 4. Independent Enforcement Evidence
The PoC database features an immutable execution ledger (`database_audit_log`). For all 13 attack vectors neutralized by Aegis, the database ledger confirms **0 execution events, 0 SQL queries executed, and 0 bytes transferred**, proving Aegis operates as an active, impenetrable network boundary rather than a passive observer.

---
*\*Note on T12: Evaluated against the exposed baseline port (8001) to demonstrate the risks of centralized cloud gateways vs. localized private-mesh Aegis proxies.*