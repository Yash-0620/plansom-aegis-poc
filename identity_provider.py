import time
import jwt

ENTRA_SECRET = "plansom-entra-agent-mock-secret-2026"

def mint_entra_agent_token(agent_id="plansom-hr-delegation-agent", roles=None):
    if roles is None:
        roles = ["Agent.Planning.Read"]
    
    now = int(time.time())
    payload = {
        "iss": "https://login.microsoftonline.com/plansom-tenant-id/v2.0",
        "sub": agent_id,
        "aud": "api://plansom-planning-gateway",
        "appid": "00000003-0000-0000-c000-000000000000",
        "roles": roles,
        "iat": now,
        "nbf": now,
        "exp": now + 3600
    }
    # Mints a valid JWT mimicking Microsoft Entra ID
    return jwt.encode(payload, ENTRA_SECRET, algorithm="HS256")

if __name__ == "__main__":
    token = mint_entra_agent_token()
    print("[+] Generated Mock Entra ID Agent Token:")
    print(token)