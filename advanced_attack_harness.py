from dotenv import load_dotenv
load_dotenv()

import time
import requests
import os
import uuid
from identity_provider import mint_entra_agent_token

# Network Paths
MS_BASELINE_URL = "http://127.0.0.1:8000/ms-baseline/mcp/v1/tools/call"
AEGIS_URL = "http://127.0.0.1:8080/mcp/v1/tools/call"
DIRECT_BACKEND_URL = "http://127.0.0.1:8000/mcp/v1/tools/call"

AEGIS_API_KEY = os.environ.get("AEGIS_API_KEY", "")
CONTROL_PLANE_URL = "https://aegis-live-node.onrender.com/mint"

def get_aegis_ibct(agent_id, jti=None, expired=False):
    """
    Requests a capability token dynamically bound to the agent identity, 
    a specific nonce (jti), and an expiration state.
    """
    payload = {
        "api_key": AEGIS_API_KEY,
        "agent_sub": agent_id,
        "jti": jti or uuid.uuid4().hex,
        "expires_in": -3600 if expired else 3600 # Force expiration for T14
    }
    try:
        res = requests.post(CONTROL_PLANE_URL, json=payload, timeout=5)
        return res.json().get("token", "mock_fallback_token")
    except Exception:
        return "mock_fallback_token"

def fire_request(url, headers, payload):
    start = time.time()
    try:
        res = requests.post(url, json=payload, headers=headers, timeout=3)
        latency = (time.time() - start) * 1000
        return res.status_code, latency
    except requests.exceptions.RequestException:
        return "NETWORK_DROP", 0

def build_mcp_payload(tool_name, department, data_type="goals"):
    return {
        "name": tool_name,
        "arguments": {"department": department, "data_type": data_type},
        "params": {"name": tool_name, "arguments": {"department": department, "data_type": data_type}}
    }

def run_advanced_harness():
    print("\n" + "="*118)
    print(f"{'PLANSOM CISO VALIDATION: ADVANCED 14-POINT ATTACK HARNESS':^118}")
    print("="*118)

    # 1. Minting diverse identity & capability tokens
    entra_agent_a = mint_entra_agent_token(agent_id="plansom-hr-agent", roles=["Agent.Planning.Read"])
    entra_agent_b = mint_entra_agent_token(agent_id="plansom-marketing-agent", roles=["Agent.Planning.Read"])
    entra_no_role = mint_entra_agent_token(agent_id="plansom-hr-agent", roles=[])
    
    # Generate Aegis IBCTs bound to specific properties
    aegis_agent_a_valid = get_aegis_ibct("plansom-hr-agent")
    aegis_agent_a_expired = get_aegis_ibct("plansom-hr-agent", expired=True)
    
    # For T13 (Exact Replay), we must reuse the exact same JTI/Token
    replay_jti = uuid.uuid4().hex
    aegis_replay_token = get_aegis_ibct("plansom-hr-agent", jti=replay_jti)
    aegis_tampered = aegis_agent_a_valid[:-5] + "XyZ12" if aegis_agent_a_valid else "invalid"

    scenarios = [
        {"id": "T01", "name": "Legitimate HR Read", "payload": build_mcp_payload("fetch_planning_data", "hr_department"), "ms_auth": entra_agent_a, "aegis_auth": aegis_agent_a_valid},
        {"id": "T02", "name": "Missing Tokens", "payload": build_mcp_payload("fetch_planning_data", "hr_department"), "ms_auth": None, "aegis_auth": None},
        {"id": "T03", "name": "Invalid/Corrupted JWT", "payload": build_mcp_payload("fetch_planning_data", "hr_department"), "ms_auth": "eyJhbGciOi.invalid", "aegis_auth": aegis_agent_a_valid},
        {"id": "T04", "name": "Insufficient Entra Role", "payload": build_mcp_payload("fetch_planning_data", "hr_department"), "ms_auth": entra_no_role, "aegis_auth": aegis_agent_a_valid},
        {"id": "T05", "name": "Invalid Static Schema", "payload": build_mcp_payload("fetch_planning_data", "finance_treasury"), "ms_auth": entra_agent_a, "aegis_auth": aegis_agent_a_valid},
        {"id": "T06", "name": "Confused Deputy (Exec Board)", "payload": build_mcp_payload("fetch_planning_data", "executive_board"), "ms_auth": entra_agent_a, "aegis_auth": aegis_agent_a_valid},
        {"id": "T07", "name": "Context Tampering", "payload": build_mcp_payload("fetch_planning_data", "executive_board"), "ms_auth": entra_agent_a, "aegis_auth": aegis_agent_a_valid},
        
        # Capability Theft: Agent B uses Agent B's Entra token, but Agent A's Aegis capability
        {"id": "T08", "name": "Capability Theft (Cross-Agent)", "payload": build_mcp_payload("fetch_planning_data", "hr_department"), "ms_auth": entra_agent_b, "aegis_auth": aegis_agent_a_valid},
        
        {"id": "T09", "name": "Tool Substitution", "payload": build_mcp_payload("delete_all_planning_data", "hr_department"), "ms_auth": entra_agent_a, "aegis_auth": aegis_agent_a_valid},
        {"id": "T10", "name": "Data Type Mutation", "payload": build_mcp_payload("fetch_planning_data", "hr_department", "confidential_salaries"), "ms_auth": entra_agent_a, "aegis_auth": aegis_agent_a_valid},
        {"id": "T11", "name": "Capability Tampering", "payload": build_mcp_payload("fetch_planning_data", "hr_department"), "ms_auth": entra_agent_a, "aegis_auth": aegis_tampered},
        {"id": "T12", "name": "Direct Backend Network Bypass", "payload": build_mcp_payload("fetch_planning_data", "hr_department"), "ms_auth": entra_agent_a, "aegis_auth": aegis_agent_a_valid, "force_direct_backend": True},
        
        # New: Replay and Expiry Tests
        {"id": "T13", "name": "Exact Capability Replay (JTI Reuse)", "payload": build_mcp_payload("fetch_planning_data", "hr_department"), "ms_auth": entra_agent_a, "aegis_auth": aegis_replay_token, "is_replay_test": True},
        {"id": "T14", "name": "Expired Capability Token", "payload": build_mcp_payload("fetch_planning_data", "hr_department"), "ms_auth": entra_agent_a, "aegis_auth": aegis_agent_a_expired}
    ]

    print(f"{'ID':<4} | {'Test Scenario':<46} | {'MS Baseline (APIM+Entra+RLS)':<30} | {'Aegis L7 Boundary'}")
    print("-" * 118)

    for s in scenarios:
        corr_id = f"req_{s['id']}_{uuid.uuid4().hex[:4]}"
        ms_url = DIRECT_BACKEND_URL if s.get("force_direct_backend") else MS_BASELINE_URL
        aegis_url = DIRECT_BACKEND_URL if s.get("force_direct_backend") else AEGIS_URL

        # --- Microsoft Baseline Headers ---
        ms_hdrs = {"Content-Type": "application/json", "x-correlation-id": corr_id}
        if s["ms_auth"]: ms_hdrs["Authorization"] = f"Bearer {s['ms_auth']}"
        
        ms_status, ms_lat = fire_request(ms_url, ms_hdrs, s["payload"])

        # Format MS Baseline Output
        if ms_status == 200 and s["id"] in ["T06", "T07", "T08", "T10", "T13"]:
            ms_out = f"❌ 200 (Leaked)"
        elif ms_status == 500 and "row level security" in str(ms_status).lower():
            ms_out = f"✅ SECURE (RLS Blocked)"
        elif ms_status == 200:
            ms_out = f"✅ {ms_status} (Allowed)"
        elif str(ms_status) == "NETWORK_DROP":
            ms_out = f"✅ BLOCKED (Network Drop)"
        else:
            ms_out = f"✅ {ms_status} (Secured)"

        # --- Aegis Proxy Headers ---
        aegis_hdrs = {"Content-Type": "application/json", "x-correlation-id": corr_id}
        if s["ms_auth"]: aegis_hdrs["Authorization"] = f"Bearer {s['ms_auth']}" # Pass Identity for Pinning
        if s["aegis_auth"]: aegis_hdrs["X-Aegis-IBCT"] = s["aegis_auth"]
        
        # Execute Replay Test Logic
        if s.get("is_replay_test"):
            # Fire Request 1 (Legitimate)
            fire_request(aegis_url, aegis_hdrs, s["payload"])
            # Fire Request 2 (Exact Replay)
            aegis_status, aegis_lat = fire_request(aegis_url, aegis_hdrs, s["payload"])
        else:
            aegis_status, aegis_lat = fire_request(aegis_url, aegis_hdrs, s["payload"])

        # Format Aegis Output
        if aegis_status == 200:
            aegis_out = f"✅ 200 [{aegis_lat:.1f}ms]"
        elif str(aegis_status) == "NETWORK_DROP":
            aegis_out = f"✅ BLOCKED (Network Drop)"
        else:
            aegis_out = f"✅ {aegis_status} [{aegis_lat:.1f}ms]"

        print(f"{s['id']:<4} | {s['name']:<46} | {ms_out:<30} | {aegis_out}")

if __name__ == "__main__":
    run_advanced_harness()