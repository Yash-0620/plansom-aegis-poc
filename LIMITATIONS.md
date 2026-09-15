# Proof of Concept Limitations & Technical Scope

## Objective
To ensure a rigorous and transparent security evaluation, this document explicitly separates production Microsoft capabilities from their simulated representations within this local Proof of Concept (PoC) environment[cite: 2]. 

## Capability Simulation Mapping

| Microsoft Capability | PoC Representation | Known Limitation[cite: 2] |
| :--- | :--- | :--- |
| **Entra Agent ID** | Local identity simulator (`identity_provider.py`)[cite: 1] | Mints valid JWTs but does not connect to a live Azure tenant[cite: 2]. |
| **Entra Authorization** | Mock Express.js claims validation[cite: 1] | Models RBAC properties but lacks production IAM propagation[cite: 2]. |
| **Azure APIM** | Express/AJV APIM-equivalent gateway[cite: 1, 2] | Evaluates JSON schemas strictly, but is not a live APIM instance[cite: 2]. |
| **Agent Governance Toolkit** | Not implemented | Microsoft's pre-execution policy engine is acknowledged but excluded to test network-edge enforcement decoupling[cite: 2]. |
| **Downstream DB Auth** | PostgreSQL execution ledger[cite: 2] | Enforces audit trails but relies on gateway application logic for query scoping[cite: 2]. |
| **Prompt Shields** | Explicitly out of scope[cite: 2] | This experiment measures execution boundaries *after* an agent has hallucinated or been manipulated into generating a tool call[cite: 2]. |

## Specific Test Artifacts

### 1. Network Isolation (T12: Direct Backend Bypass)
In a production Azure Virtual Network, the downstream gateway would be completely isolated from external internet traffic, relying entirely on the Aegis reverse proxy[cite: 2]. For this local Docker benchmarking script to reach both paths, host port `8000` was intentionally exposed. Consequently, the Microsoft baseline permitted the T12 direct backend bypass, whereas a production VNET configuration would successfully drop it.

### 2. Capability Theft / Subject Binding (T08)
During scenario T08 (Capability Theft), Agent B successfully executed a capability token intended for Agent A. The current PoC generation of the Aegis Invocation-Bound Capability Token (IBCT) cryptographically binds the *tool*, *resource*, and *parameters*[cite: 2], but the PoC rule engine was not yet configured to strictly pin the Entra Subject (`sub`) claim to the IBCT[cite: 2]. In production, Aegis correlates the Entra JWT `sub` with the IBCT to prevent cross-agent token theft.

### 3. Pre-Execution vs. Runtime Boundary
This PoC acknowledges that Microsoft's Agent Governance Toolkit and rigorous Downstream Row-Level Security (RLS) can be mapped to achieve similar contextual controls[cite: 2]. The demonstrated value of Aegis is not that Microsoft is fundamentally incapable of this mapping, but rather that Aegis provides an **independent, cryptographically bound proxy** at the execution boundary, decoupling AI authorization from complex downstream IAM configurations[cite: 2].