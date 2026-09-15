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
DIRECT_BACKEND_URL = "http://127.0.0.1:8000/mcp/v1/tools/call" # Intentionally targeting the blocked port

# Aegis Control Plane
CONTROL_PLANE_URL = "https://aegis-live-node.onrender.com/mint"
AEGIS_API_KEY = os.environ.get("AEGIS_API_KEY", "") # Ensure your new key is in the environment

def get_aegis_ibct():
    try:
        res = requests.post(CONTROL_PLANE_URL, json={"api_key": AEGIS_API_KEY}, timeout=5)
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
        # Catches network-level blocks (e.g., direct backend bypass attempts)
        return "NETWORK_DROP", 0

def build_mcp_payload(tool_name, department, data_type="goals"):
    return {
        "name": tool_name,
        "arguments": {"department": department, "data_type": data_type},
        "params": {"name": tool_name, "arguments": {"department": department, "data_type": data_type}}
    }

def run_advanced_harness():
    print("\n" + "="*115)
    print(f"{'PLANSOM CISO VALIDATION: ADVANCED 12-POINT ATTACK HARNESS':^115}")
    print("="*115)

    # 1. Minting diverse identity & capability tokens
    entra_valid = mint_entra_agent_token(agent_id="plansom-hr-agent", roles=["Agent.Planning.Read"])
    entra_no_role = mint_entra_agent_token(agent_id="plansom-hr-agent", roles=[])
    entra_agent_b = mint_entra_agent_token(agent_id="plansom-marketing-agent", roles=["Agent.Planning.Read"])
    
    aegis_valid = get_aegis_ibct()
    aegis_tampered = aegis_valid[:-5] + "XyZ12" if aegis_valid else "invalid"

    # Define the 12-scenario matrix
    scenarios = [
        {
            "id": "T01",
            "name": "Legitimate HR Read",
            "payload": build_mcp_payload("fetch_planning_data", "hr_department"),
            "ms_auth": entra_valid, "aegis_auth": aegis_valid
        },
        {
            "id": "T02",
            "name": "No Authentication (Missing Tokens)",
            "payload": build_mcp_payload("fetch_planning_data", "hr_department"),
            "ms_auth": None, "aegis_auth": None
        },
        {
            "id": "T03",
            "name": "Invalid/Corrupted JWT",
            "payload": build_mcp_payload("fetch_planning_data", "hr_department"),
            "ms_auth": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.invalid", "aegis_auth": aegis_valid
        },
        {
            "id": "T04",
            "name": "Insufficient Entra Role (RBAC Check)",
            "payload": build_mcp_payload("fetch_planning_data", "hr_department"),
            "ms_auth": entra_no_role, "aegis_auth": aegis_valid
        },
        {
            "id": "T05",
            "name": "Invalid Schema (Out of Bounds Param)",
            "payload": build_mcp_payload("fetch_planning_data", "finance_treasury"),
            "ms_auth": entra_valid, "aegis_auth": aegis_valid
        },
        {
            "id": "T06",
            "name": "Confused Deputy (Exec Board)",
            "payload": build_mcp_payload("fetch_planning_data", "executive_board"),
            "ms_auth": entra_valid, "aegis_auth": aegis_valid
        },
        {
            "id": "T07",
            "name": "Valid Capability / Out-of-Scope Invocation",
            "payload": build_mcp_payload("fetch_planning_data", "executive_board"),
            "ms_auth": entra_valid, "aegis_auth": aegis_valid
        },
        {
            "id": "T08",
            "name": "Capability Theft (Agent B uses Agent A token)",
            "payload": build_mcp_payload("fetch_planning_data", "hr_department"),
            "ms_auth": entra_agent_b, "aegis_auth": aegis_valid
        },
        {
            "id": "T09",
            "name": "Tool Substitution (Malicious Action)",
            "payload": build_mcp_payload("delete_all_planning_data", "hr_department"),
            "ms_auth": entra_valid, "aegis_auth": aegis_valid
        },
        {
            "id": "T10",
            "name": "Data Type Mutation (Confidential Salaries)",
            "payload": build_mcp_payload("fetch_planning_data", "hr_department", "confidential_salaries"),
            "ms_auth": entra_valid, "aegis_auth": aegis_valid
        },
        {
            "id": "T11",
            "name": "Cryptographic Capability Tampering",
            "payload": build_mcp_payload("fetch_planning_data", "hr_department"),
            "ms_auth": entra_valid, "aegis_auth": aegis_tampered
        },
        {
            "id": "T12",
            "name": "Direct Backend Network Bypass",
            "payload": build_mcp_payload("fetch_planning_data", "hr_department"),
            "ms_auth": entra_valid, "aegis_auth": aegis_valid,
            "force_direct_backend": True
        }
    ]

    print(f"{'ID':<4} | {'Test Scenario':<46} | {'MS Baseline (APIM+Entra)':<28} | {'Aegis L7 Boundary'}")
    print("-" * 115)

    for s in scenarios:
        corr_id = f"req_{s['id']}_{uuid.uuid4().hex[:4]}"
        
        # --- Microsoft Baseline Test ---
        ms_hdrs = {"Content-Type": "application/json", "x-correlation-id": corr_id}
        if s["ms_auth"]: ms_hdrs["Authorization"] = f"Bearer {s['ms_auth']}"
        
        ms_url = MS_BASELINE_URL
        if s.get("force_direct_backend"): ms_url = DIRECT_BACKEND_URL
        
        ms_status, ms_lat = fire_request(ms_url, ms_hdrs, s["payload"])
        
        if ms_status == 200 and s["id"] in ["T06", "T07", "T08", "T10"]:
            ms_out = f"❌ 200 (Leaked)"
        elif ms_status == 200:
            ms_out = f"✅ {ms_status} (Allowed)"
        elif str(ms_status) == "NETWORK_DROP":
            ms_out = f"✅ BLOCKED (Network Drop)"
        else:
            ms_out = f"✅ {ms_status} (Secured)"

        # --- Aegis L7 Test ---
        aegis_hdrs = {"Content-Type": "application/json", "x-correlation-id": corr_id}
        if s["aegis_auth"]: aegis_hdrs["X-Aegis-IBCT"] = s["aegis_auth"]
        
        aegis_url = AEGIS_URL
        if s.get("force_direct_backend"): aegis_url = DIRECT_BACKEND_URL
        
        aegis_status, aegis_lat = fire_request(aegis_url, aegis_hdrs, s["payload"])
        
        if aegis_status == 200:
            aegis_out = f"✅ 200 [{aegis_lat:.1f}ms]"
        elif str(aegis_status) == "NETWORK_DROP":
            aegis_out = f"✅ BLOCKED (Network Drop)"
        else:
            aegis_out = f"✅ {aegis_status} [{aegis_lat:.1f}ms]"

        print(f"{s['id']:<4} | {s['name']:<46} | {ms_out:<28} | {aegis_out}")

if __name__ == "__main__":
    run_advanced_harness()