import time
import requests
from identity_provider import mint_entra_agent_token

MS_BASELINE_URL = "http://127.0.0.1:8000/ms-baseline/mcp/v1/tools/call"
AEGIS_URL = "http://127.0.0.1:8080/mcp/v1/tools/call"
CONTROL_PLANE_URL = "https://aegis-live-node.onrender.com/mint"
AEGIS_API_KEY = "aegis_live_902d386204adbe439d4582d7cc8db2ba"

def get_aegis_ibct():
    res = requests.post(CONTROL_PLANE_URL, json={"api_key": AEGIS_API_KEY})
    return res.json().get("token")

def fire_request(url, headers, payload):
    start = time.time()
    try:
        res = requests.post(url, json=payload, headers=headers, timeout=5)
        latency = (time.time() - start) * 1000
        return res.status_code, res.json(), latency
    except Exception as e:
        return 0, str(e), 0

def build_mcp_payload(tool_name, arguments):
    return {
        "name": tool_name,
        "arguments": arguments,
        "params": {
            "name": tool_name,
            "arguments": arguments
        }
    }

def run_benchmark():
    entra_token = mint_entra_agent_token()
    aegis_token = get_aegis_ibct()

    ms_headers = {"Authorization": f"Bearer {entra_token}", "Content-Type": "application/json"}
    aegis_headers = {"X-Aegis-IBCT": aegis_token, "Content-Type": "application/json"}

    scenarios = [
        {
            "name": "1. Legitimate HR Read",
            "payload": build_mcp_payload("fetch_planning_data", {"department": "hr_department", "data_type": "goals"}),
            "expected_ms": 200,
            "expected_aegis": 200
        },
        {
            "name": "2. Confused Deputy (Cross-Department Exfiltration)",
            "payload": build_mcp_payload("fetch_planning_data", {"department": "executive_board", "data_type": "goals"}),
            "expected_ms": 200,
            "expected_aegis": 422
        },
        {
            "name": "3. Unauthorized Parameter (Direct Schema Breach)",
            "payload": build_mcp_payload("fetch_planning_data", {"department": "finance_treasury", "data_type": "goals"}),
            "expected_ms": 400,
            "expected_aegis": 422
        },
        {
            "name": "4. Direct Authentication Bypass (No Tokens)",
            "payload": build_mcp_payload("fetch_planning_data", {"department": "hr_department", "data_type": "goals"}),
            "expected_ms": 401,
            "expected_aegis": 401
        },
        {
            "name": "5. Valid Capability Token / Out-of-Scope Invocation",
            "payload": build_mcp_payload("fetch_planning_data", {"department": "executive_board", "data_type": "goals"}),
            "expected_ms": 200,
            "expected_aegis": 422
        },
        {
            "name": "6. Cryptographic Replay / Tampered Capability",
            "payload": build_mcp_payload("fetch_planning_data", {"department": "hr_department", "data_type": "goals"}),
            "custom_aegis_token": aegis_token[:-5] + "invalid", # Simulates a tampered/invalidated token signature
            "expected_ms": 200,
            "expected_aegis": 401
        }
    ]

    print(f"\n{'Test Scenario':<55} | {'MS Baseline (APIM + Entra)':<28} | {'Aegis L7 Proxy'}")
    print("-" * 108)

    for s in scenarios:
        payload = s["payload"]
        
        # Test MS Baseline
        ms_hdrs = ms_headers if "Bypass" not in s["name"] else {"Content-Type": "application/json"}
        ms_status, ms_res, ms_lat = fire_request(MS_BASELINE_URL, ms_hdrs, payload)
        
        if ms_status == 200 and ("Confused Deputy" in s["name"] or "Out-of-Scope" in s["name"]):
            ms_display = f"VULNERABLE (200 - Leaked)"
        elif ms_status == 200:
            ms_display = f"ALLOW ({ms_status})"
        else:
            ms_display = f"SECURE ({ms_status})"

        # Test Aegis
        aegis_hdrs = aegis_headers if "Bypass" not in s["name"] else {"Content-Type": "application/json"}
        
        # Inject the tampered token for Scenario 6
        if "custom_aegis_token" in s:
            aegis_hdrs["X-Aegis-IBCT"] = s["custom_aegis_token"]

        aegis_status, aegis_res, aegis_lat = fire_request(AEGIS_URL, aegis_hdrs, payload)
        
        if aegis_status == 200:
            aegis_display = f"ALLOW (200) [{aegis_lat:.1f}ms]"
        elif aegis_status in [422, 401, 403]:
            aegis_display = f"SECURE ({aegis_status}) [{aegis_lat:.1f}ms]"
        else:
            aegis_display = f"ERROR ({aegis_status})"

        print(f"{s['name']:<55} | {ms_display:<28} | {aegis_display}")

if __name__ == "__main__":
    run_benchmark()