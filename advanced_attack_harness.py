import os
import time
import uuid
import jwt
import requests
from dotenv import load_dotenv
from identity_provider import mint_entra_agent_token

load_dotenv()

MS_BASELINE_URL = "http://127.0.0.1:8001/ms-baseline/mcp/v1/tools/call"
AEGIS_URL = "http://127.0.0.1:8080/mcp/v1/tools/call"
DIRECT_BACKEND_URL = "http://127.0.0.1:8001/mcp/v1/tools/call"
CONTROL_PLANE_URL = "https://aegis-live-node.onrender.com/mint"
AEGIS_API_KEY = os.environ.get("AEGIS_API_KEY", "aegis_live_902d386204adbe439d4582d7cc8db2ba")

# Master private key for local offline token minting fallback
AEGIS_PRIVATE_KEY = """-----BEGIN PRIVATE KEY-----
MC4CAQAwBQYDK2VwBCIEIBLLVAvwTiVMFvP861egAMSzht3h94NZww/QvpXV9+54
-----END PRIVATE KEY-----"""

# Exact Plansom HR schema bounds
PLANSOM_SCHEMA_BOUNDS = {
    "fetch_planning_data": {
        "type": "object",
        "properties": {
            "department": {
                "type": "string",
                "pattern": "^hr_department$"
            },
            "data_type": {
                "type": "string",
                "pattern": "^goals$"
            }
        },
        "required": ["department"],
        "additionalProperties": False
    }
}

def mint_local_ibct(agent_sub, jti=None, expires_in=3600):
    """Mints an authentic Ed25519 IBCT with exact exp, jti, and sub claims."""
    now = int(time.time())
    payload = {
        "user_id": "user_3HpFKDdcq9f8D1Q5eYbG2dT1jaq",
        "agent_id": agent_sub,
        "sub": agent_sub,
        "jti": jti or uuid.uuid4().hex,
        "iat": now,
        "nbf": now - 60,  # 60s backdate for clock drift safety
        "exp": now + expires_in,
        "allowed_scopes": ["fetch_planning_data"],
        "schema_bounds": PLANSOM_SCHEMA_BOUNDS
    }
    return jwt.encode(payload, AEGIS_PRIVATE_KEY, algorithm="EdDSA")

def get_aegis_ibct(agent_sub, jti=None, expires_in=3600):
    """Attempts cloud minting; falls back to local minting if cloud omits exp/jti."""
    try:
        payload = {
            "api_key": AEGIS_API_KEY,
            "agent_sub": agent_sub,
            "jti": jti or uuid.uuid4().hex,
            "expires_in": expires_in
        }
        res = requests.post(CONTROL_PLANE_URL, json=payload, timeout=3)
        if res.status_code == 200:
            token = res.json().get("token")
            unverified = jwt.decode(token, options={"verify_signature": False})
            if "exp" in unverified and "jti" in unverified:
                return token
    except Exception:
        pass
    return mint_local_ibct(agent_sub, jti=jti, expires_in=expires_in)

def fire_request(url, headers, payload):
    start = time.time()
    try:
        res = requests.post(url, json=payload, headers=headers, timeout=3)
        latency = (time.time() - start) * 1000
        return res.status_code, res.json() if res.content else {}, latency
    except requests.exceptions.ConnectionError:
        return "CONN_REFUSED", {}, 0
    except requests.exceptions.RequestException as e:
        return "ERROR", {"error": str(e)}, 0

def build_mcp_payload(tool_name, department, data_type="goals"):
    return {
        "name": tool_name,
        "arguments": {"department": department, "data_type": data_type}
    }

def run_advanced_harness():
    print("\n" + "=" * 114)
    print(f"{'PLANSOM CISO VALIDATION: ADVANCED 14-POINT SECURITY HARNESS':^114}")
    print("=" * 114)

    entra_agent_a = mint_entra_agent_token(agent_id="plansom-hr-agent", roles=["Agent.Planning.Read"])
    entra_agent_b = mint_entra_agent_token(agent_id="plansom-marketing-agent", roles=["Agent.Planning.Read"])
    entra_no_role = mint_entra_agent_token(agent_id="plansom-hr-agent", roles=[])

    # Replay token specifically for T13
    replay_jti = uuid.uuid4().hex
    aegis_replay_token = get_aegis_ibct("plansom-hr-agent", jti=replay_jti)

    # Scenarios: helper lambda or dynamic generator supplies fresh tokens where appropriate
    scenarios = [
        {"id": "T01", "name": "Legitimate HR Read", "payload": build_mcp_payload("fetch_planning_data", "hr_department"), "ms_auth": entra_agent_a, "agent_sub": "plansom-hr-agent", "exp_ms": 200, "exp_aegis": 200},
        {"id": "T02", "name": "Missing Identity Token", "payload": build_mcp_payload("fetch_planning_data", "hr_department"), "ms_auth": None, "agent_sub": "plansom-hr-agent", "exp_ms": 401, "exp_aegis": 401},
        {"id": "T03", "name": "Corrupted Identity JWT", "payload": build_mcp_payload("fetch_planning_data", "hr_department"), "ms_auth": "invalid.jwt.token", "agent_sub": "plansom-hr-agent", "exp_ms": 401, "exp_aegis": 401},
        {"id": "T04", "name": "Insufficient Entra Role", "payload": build_mcp_payload("fetch_planning_data", "hr_department"), "ms_auth": entra_no_role, "agent_sub": "plansom-hr-agent", "exp_ms": 403, "exp_aegis": 403},
        {"id": "T05", "name": "Invalid Static Schema Enum", "payload": build_mcp_payload("fetch_planning_data", "invalid_dept"), "ms_auth": entra_agent_a, "agent_sub": "plansom-hr-agent", "exp_ms": 400, "exp_aegis": 422},
        # The Contextual Execution Gap: Allowed by MS APIM enum, blocked by Aegis dynamic regex
        {"id": "T06", "name": "Confused Deputy (Exec Board)", "payload": build_mcp_payload("fetch_planning_data", "executive_board"), "ms_auth": entra_agent_a, "agent_sub": "plansom-hr-agent", "exp_ms": 200, "exp_aegis": 422},
        {"id": "T07", "name": "Context Tampering", "payload": build_mcp_payload("fetch_planning_data", "executive_board"), "ms_auth": entra_agent_a, "agent_sub": "plansom-hr-agent", "exp_ms": 200, "exp_aegis": 422},
        {"id": "T08", "name": "Capability Theft (Agent B steals A)", "payload": build_mcp_payload("fetch_planning_data", "hr_department"), "ms_auth": entra_agent_b, "agent_sub": "plansom-hr-agent", "exp_ms": 200, "exp_aegis": 403},
        {"id": "T09", "name": "Tool Substitution", "payload": build_mcp_payload("delete_all_planning_data", "hr_department"), "ms_auth": entra_agent_a, "agent_sub": "plansom-hr-agent", "exp_ms": 200, "exp_aegis": 403},
        {"id": "T10", "name": "Data Type Mutation", "payload": build_mcp_payload("fetch_planning_data", "hr_department", "confidential_salaries"), "ms_auth": entra_agent_a, "agent_sub": "plansom-hr-agent", "exp_ms": 200, "exp_aegis": 422},
        {"id": "T11", "name": "Capability Token Tampering", "payload": build_mcp_payload("fetch_planning_data", "hr_department"), "ms_auth": entra_agent_a, "custom_ibct": lambda: get_aegis_ibct("plansom-hr-agent")[:-5] + "XyZ12", "exp_ms": 200, "exp_aegis": 403},
        {"id": "T12", "name": "Direct Backend Network Bypass", "payload": build_mcp_payload("fetch_planning_data", "hr_department"), "ms_auth": entra_agent_a, "agent_sub": "plansom-hr-agent", "force_direct": True, "exp_ms": 200, "exp_aegis": 401},
        {"id": "T13", "name": "Exact Capability Replay (JTI)", "payload": build_mcp_payload("fetch_planning_data", "hr_department"), "ms_auth": entra_agent_a, "custom_ibct": lambda: aegis_replay_token, "is_replay": True, "exp_ms": 200, "exp_aegis": 409},
        {"id": "T14", "name": "Expired Capability Token", "payload": build_mcp_payload("fetch_planning_data", "hr_department"), "ms_auth": entra_agent_a, "custom_ibct": lambda: get_aegis_ibct("plansom-hr-agent", expires_in=-3600), "exp_ms": 200, "exp_aegis": 401}
    ]

    print(f"{'ID':<4} | {'Test Scenario':<38} | {'MS Baseline (APIM)':<26} | {'Aegis L7 Proxy':<26} | {'Status'}")
    print("-" * 114)

    for s in scenarios:
        corr_id = f"req_{s['id']}_{uuid.uuid4().hex[:4]}"
        
        # 1. Evaluate Microsoft Baseline Path
        ms_url = MS_BASELINE_URL
        ms_hdrs = {"Content-Type": "application/json", "x-correlation-id": corr_id}
        if s["ms_auth"]:
            ms_hdrs["Authorization"] = f"Bearer {s['ms_auth']}"
        ms_status, ms_json, ms_lat = fire_request(ms_url, ms_hdrs, s["payload"])
        
        # 2. Evaluate Aegis Path (Mint a fresh capability token with a unique JTI per test)
        if "custom_ibct" in s:
            ibct_token = s["custom_ibct"]()
        elif s.get("agent_sub"):
            ibct_token = get_aegis_ibct(s["agent_sub"])
        else:
            ibct_token = None

        aegis_url = DIRECT_BACKEND_URL if s.get("force_direct") else AEGIS_URL
        aegis_hdrs = {"Content-Type": "application/json", "x-correlation-id": corr_id}
        if s["ms_auth"]:
            aegis_hdrs["Authorization"] = f"Bearer {s['ms_auth']}"
        if ibct_token:
            aegis_hdrs["X-Aegis-IBCT"] = ibct_token

        if s.get("is_replay"):
            # First execution: consumes the JTI (200)
            fire_request(aegis_url, aegis_hdrs, s["payload"])
            # Second execution: attempts replay of the exact same JTI (expected 409)
            aegis_status, aegis_json, aegis_lat = fire_request(aegis_url, aegis_hdrs, s["payload"])
        else:
            aegis_status, aegis_json, aegis_lat = fire_request(aegis_url, aegis_hdrs, s["payload"])

        ms_disp = f"{ms_status}" if ms_status != "CONN_REFUSED" else "CONN_REFUSED"
        aegis_disp = f"{aegis_status} ({aegis_lat:.1f}ms)" if aegis_status != "CONN_REFUSED" else "BLOCKED (Drop)"
        
        passed = (aegis_status == s["exp_aegis"])
        result_flag = "[PASS]" if passed else "[FAIL]"

        print(f"{s['id']:<4} | {s['name']:<38} | {ms_disp:<26} | {aegis_disp:<26} | {result_flag}")

if __name__ == "__main__":
    run_advanced_harness()