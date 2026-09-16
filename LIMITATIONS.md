# Proof of Concept Limitations & Technical Scope

## Objective
To ensure a rigorous and transparent security evaluation, this document explicitly separates production Microsoft capabilities from their simulated representations within this local Proof of Concept (PoC) environment.

## Capability Simulation Mapping

| Microsoft Capability | PoC Representation | Known Limitation |
| :--- | :--- | :--- |
| **Entra Agent ID** | Local identity simulator (`identity_provider.py`) | Mints structurally valid JWTs signed via HS256, but does not connect to a live Azure tenant for dynamic key rotation. |
| **Entra Authorization** | Node.js Express JWT Validation | Models Role-Based Access Control (RBAC) via the `roles` claim (`Agent.Planning.Read`), but lacks production IAM propagation mechanisms. |
| **Azure APIM** | Express/AJV Gateway (`server.js`) | Evaluates standard APIM `validate-content` JSON schemas strictly, but operates as an Express middleware rather than a dedicated cloud gateway instance. |
| **Semantic Kernel** | `plansom_kernel_sim.py` | Fully implements Microsoft's `semantic-kernel` SDK and `FilterTypes.FUNCTION_INVOCATION`. It models in-process cognitive execution but replaces Microsoft's native pre-execution policy engine with Aegis to demonstrate out-of-process network enforcement. |
| **Downstream DB Auth** | PostgreSQL Row-Level Security (RLS) | Enforces rigorous audit trails (`database_audit_log`) and RLS filters. Relies on the gateway to inject the `x-aegis-identity` variable securely into the database execution context. |
| **Prompt Shields** | Explicitly out of scope | This experiment measures execution boundaries *after* an agent has hallucinated or been manipulated into generating a tool call. |

## Specific Test Artifacts & Architectural Adjustments

### 1. Network Isolation (T12: Direct Backend Bypass)
In a production Azure Virtual Network, the downstream APIM gateway would be strictly isolated from external internet traffic, relying entirely on the Aegis reverse proxy. To benchmark both paths in this local Docker environment:
* Port `8080` maps to the Aegis L7 Sidecar.
* Port `8001` maps directly to the Microsoft Baseline Gateway.
* Port `8000` remains strictly internal.

The test harness leverages Port `8001` to simulate a scenario where a central gateway is exposed, proving that an Aegis-enforced private mesh inherently drops direct backend bypass attempts (T12).

### 2. OIDC Subject Pinning (T08: Capability Theft)
In earlier iterations of this PoC, capability theft was listed as a limitation. **This has been structurally resolved.** The Aegis sidecar now dynamically extracts the `sub` claim from the Microsoft Entra JWT and pins it against the `sub` claim embedded within the Ed25519 Invocation-Bound Capability Token (IBCT). If Agent B attempts to execute a valid capability token minted for Agent A, Aegis deterministically rejects the connection with an HTTP 403 Forbidden.

### 3. JTI Nonce Caching & Clock Drift
The Aegis Sidecar implements an in-memory `NONCE_CACHE` with TTL eviction to enforce exact token replay protection (T13). To account for local Docker clock skew (which commonly triggers immature signature errors during testing), a 300-second cryptographic leeway is applied to `nbf` and `exp` claims.

### 4. Pre-Execution vs. Runtime Boundary
This PoC acknowledges that Microsoft's Agent Governance Toolkit provides robust *in-process* contextual controls. The demonstrated value of Aegis is not that Microsoft is fundamentally incapable of policy mapping, but rather that Aegis provides an **independent, cryptographically bound proxy** at the execution boundary. This decouples AI authorization from complex downstream IAM configurations and guarantees containment even if the orchestrating framework (e.g., Semantic Kernel, LangChain) crashes or is fully compromised.