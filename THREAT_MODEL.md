# Aegis + Plansom Defense-in-Depth Threat Model

## Objective
This document outlines the formal threat model and the 12-point attack matrix used to benchmark the Microsoft security baseline (Entra ID + Azure APIM) against an architecture augmented with the Aegis Layer 7 Zero-Trust Sidecar[cite: 2]. The objective is to identify residual execution risks when authorization must be contextually bound to an individual tool invocation rather than broadly assigned via identity roles[cite: 2].

## Threat Matrix

| ID | Threat Vector | MS Baseline (APIM + Entra) | Aegis L7 Boundary | Security Property Evaluated |
| :--- | :--- | :--- | :--- | :--- |
| **T01** | Legitimate HR Read | ALLOW (200) | ALLOW (200) | Valid capability execution |
| **T02** | Missing Tokens | SECURE (401) | SECURE (401) | Baseline identity boundary[cite: 1, 2] |
| **T03** | Invalid/Corrupted JWT | SECURE (401) | ALLOW (200)* | Baseline cryptographic validation |
| **T04** | Insufficient Entra Role | SECURE (403) | ALLOW (200)* | Baseline RBAC enforcement |
| **T05** | Invalid Static Schema | SECURE (400) | SECURE (422) | Baseline APIM validation[cite: 1, 2] |
| **T06** | Confused Deputy | **VULNERABLE (200)** | **SECURE (422)** | Cross-department resource bounds[cite: 2] |
| **T07** | Out-of-Scope Invocation | **VULNERABLE (200)** | **SECURE (422)** | Valid capability context tampering[cite: 2] |
| **T08** | Capability Theft | **VULNERABLE (200)** | ALLOW (200)** | Identity-to-token pinning[cite: 2] |
| **T09** | Tool Substitution | ALLOW (200) | SECURE (403) | Malicious action prevention[cite: 2] |
| **T10** | Data Type Mutation | **VULNERABLE (200)** | **SECURE (422)** | Parameter constraint binding[cite: 2] |
| **T11** | Capability Tampering | ALLOW (200) | SECURE (403) | IBCT cryptographic integrity[cite: 2] |
| **T12** | Direct Backend Bypass | VULNERABLE (200)*** | SECURE (Drop) | Network isolation enforcement[cite: 2] |

## Key Findings & Residual Risk Analysis

### 1. The Contextual Execution Gap (T06, T07, T10)
The Microsoft baseline successfully blocks malformed requests (T05) and unauthenticated access (T02)[cite: 2]. However, it permits structurally valid payloads that violate the agent's contextual delegation (T07). Aegis enforces Invocation-Bound Capability Tokens (IBCT) at Layer 7, shredding out-of-scope executions before downstream transmission[cite: 1, 2].

### 2. Independent Enforcement Evidence
The PoC database features an immutable execution ledger (`database_audit_log`)[cite: 2]. For all vectors marked `SECURE` by Aegis, the database ledger confirms **0 execution events and 0 bytes transferred**, proving Aegis operates as an active network boundary rather than a passive observer[cite: 2].

---
*Note on T03/T04: Aegis explicitly delegates identity/RBAC checks to Entra and the downstream gateway. It strictly evaluates the IBCT cryptographic payload, demonstrating a decoupled defense-in-depth architecture.*

**Note on T08: See `LIMITATIONS.md` regarding subject (`sub`) binding.*

***Note on T12: See `LIMITATIONS.md` regarding local Docker port mappings.*