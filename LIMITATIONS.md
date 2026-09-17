# Proof of Concept Limitations & Scope

## Objective
To ensure a rigorous and transparent security evaluation, this document explicitly separates production Microsoft and Aegis capabilities from their simulated representations within this local Proof of Concept (PoC) environment[cite: 1].

## Architectural Simulation Scope

| Component | PoC Representation | Known Limitation |
| :--- | :--- | :--- |
| **Entra Agent ID** | Local identity simulator (`identity_provider.py`) | Mints structurally valid JWTs signed via HS256, but does not connect to a live Azure tenant for dynamic token minting. |
| **Azure APIM** | Express/AJV Gateway (`server.js`) | Evaluates standard APIM `validate-content` JSON schemas strictly, but operates as an Express middleware rather than a dedicated cloud gateway instance. |
| **Aegis Sidecar** | Direct public Docker Image | Uses the production `ghcr.io` image, meaning the sidecar execution accurately reflects live product performance (< 20ms overhead). |
| **Downstream Execution** | PostgreSQL + Audit Ledger | The audit log is a standard relational table. While effective for PoC observability `(DB:0 / DB:1)`, it does not constitute a mathematically immutable ledger (e.g., blockchain or WORM storage)[cite: 1]. |

## Specific Test Artifacts & Boundary Definitions

### 1. Network Topology & Isolation (T12)
To prove network-level enforcement, the PoC splits the gateway into two explicit routes[cite: 1]:
* **Port 8001 (Baseline Gateway):** Exposed to the host to simulate a traditional cloud APIM topology.
* **Port 8080 (Aegis Proxy):** The only ingress point to the `protected-gateway`, which has no exposed ports and resides strictly on an internal Docker bridge network. 

### 2. Dual-Validation Scoring
The 14-point test harness enforces a strict scoring mechanism. A scenario is only marked as `[PASS]` if **both** the Microsoft Baseline and the Aegis Proxy return their exact expected HTTP statuses and database execution counts[cite: 1]. 

### 3. JTI Nonce Caching & Clock Drift
The Aegis Sidecar implements an in-memory `NONCE_CACHE` with TTL eviction to enforce exact token replay protection (T13). To account for local Docker clock skew (which commonly triggers immature signature errors during testing), a 60-second cryptographic leeway is applied to `nbf` claims during local testing.

### 4. Cross-Agent Authorization Material
Aegis extracts the `sub` claim from the Microsoft Entra JWT and pins it against the `sub` claim embedded within the Ed25519 Invocation-Bound Capability Token (IBCT). The PoC tests this using two distinct identities (`plansom-hr-agent` and `plansom-marketing-agent`) to prove cross-agent capability token usage is actively prevented[cite: 1].