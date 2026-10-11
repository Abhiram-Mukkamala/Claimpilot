"""ClaimPilot Local Smoke Test
Validates the complete demo path:
Customer Login -> Submit Claim -> Upload Image -> Poll AI Analysis -> Agent Review

Usage:
  python smoke_test.py

Required Environment Variables:
  CUSTOMER_EMAIL
  CUSTOMER_PASSWORD
  AGENT_EMAIL
  AGENT_PASSWORD

Optional Environment Variables:
  BASE_URL        (default: http://localhost:8000/api/v1)
  POLICY_NUMBER   (default: DEMO-POL-001)
  IMAGE_PATH      (default: frontend/ClaimPilot/src/assets/hero.png)
  OTP_CODE        (if provided, bypasses interactive stdin prompt)
"""

import os
import sys
import time
from pathlib import Path
from typing import Dict, Any, Optional

import httpx

# -----------------------------------------------------------------------------
# 1. Configuration & Argument Extraction
# -----------------------------------------------------------------------------
BASE_URL = os.getenv("BASE_URL", "http://localhost:8000/api/v1").rstrip("/")
CUSTOMER_EMAIL = os.getenv("CUSTOMER_EMAIL")
CUSTOMER_PASSWORD = os.getenv("CUSTOMER_PASSWORD")
AGENT_EMAIL = os.getenv("AGENT_EMAIL")
AGENT_PASSWORD = os.getenv("AGENT_PASSWORD")
POLICY_NUMBER = os.getenv("POLICY_NUMBER", "DEMO-POL-001")
IMAGE_PATH_ENV = os.getenv("IMAGE_PATH")
OTP_CODE_ENV = os.getenv("OTP_CODE")

missing_vars = []
if not CUSTOMER_EMAIL:
    missing_vars.append("CUSTOMER_EMAIL")
if not CUSTOMER_PASSWORD:
    missing_vars.append("CUSTOMER_PASSWORD")
if not AGENT_EMAIL:
    missing_vars.append("AGENT_EMAIL")
if not AGENT_PASSWORD:
    missing_vars.append("AGENT_PASSWORD")

if missing_vars:
    print(f"[ERROR] Missing required environment variable(s): {', '.join(missing_vars)}")
    print("Please set them before executing smoke_test.py. Example:")
    print("  $env:CUSTOMER_EMAIL='customer@example.com'")
    print("  $env:CUSTOMER_PASSWORD='...'")
    print("  $env:AGENT_EMAIL='agent@claimpilot.ai'")
    print("  $env:AGENT_PASSWORD='...'")
    sys.exit(1)


# -----------------------------------------------------------------------------
# 2. Helpers (Secrets Rule Compliant: prints KEYS and status codes only)
# -----------------------------------------------------------------------------
def log_response(stage: str, resp: httpx.Response, extra: Optional[str] = None):
    try:
        data = resp.json()
        keys = list(data.keys()) if isinstance(data, dict) else [f"array_len_{len(data)}"]
    except Exception:
        keys = ["<non-json response>"]

    extra_str = f" | {extra}" if extra else ""
    print(f"[{stage}] HTTP {resp.status_code} | Keys: {keys}{extra_str}")


def login_flow(client: httpx.Client, email: str, password: str, role_name: str) -> str:
    """Executes Step 1 password verification and Step 2 OTP verification if mandated."""
    print(f"\n--- Logging in {role_name} ---")
    login_resp = client.post(
        f"{BASE_URL}/auth/login",
        json={"email": email, "password": password},
    )
    log_response(f"{role_name} Step 1 Login", login_resp)

    if login_resp.status_code >= 400:
        print(f"[FAIL] {role_name} login failed with status {login_resp.status_code}")
        sys.exit(1)

    login_data = login_resp.json()
    if login_data.get("requires_otp"):
        otp = OTP_CODE_ENV or input(f"Enter 6-digit OTP received for {email}: ").strip()
        verify_resp = client.post(
            f"{BASE_URL}/auth/otp/verify",
            json={"identifier": email, "otp_code": otp, "channel": "email"},
        )
        log_response(f"{role_name} Step 2 OTP Verify", verify_resp)
        if verify_resp.status_code >= 400:
            print(f"[FAIL] {role_name} OTP verification failed.")
            sys.exit(1)
        token = verify_resp.json().get("access_token")
    else:
        token = login_data.get("access_token")

    if not token:
        print(f"[FAIL] No access token received for {role_name}.")
        sys.exit(1)

    return token


def resolve_image_file() -> tuple[bytes, str, str]:
    """Resolves test image bytes, filename, and mime type."""
    candidate_paths = []
    if IMAGE_PATH_ENV:
        candidate_paths.append(Path(IMAGE_PATH_ENV))

    backend_dir = Path(__file__).resolve().parent
    repo_root = backend_dir.parent.parent

    candidate_paths.extend([
        backend_dir.parent / "frontend" / "ClaimPilot" / "src" / "assets" / "hero.png",
        repo_root / "frontend" / "ClaimPilot" / "src" / "assets" / "hero.png",
    ])

    for p in candidate_paths:
        if p.exists() and p.is_file():
            mime = "image/png" if p.suffix.lower() == ".png" else "image/jpeg"
            return p.read_bytes(), p.name, mime

    # Fallback minimal 1x1 PNG bytes if no file found on disk
    dummy_png = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDAT\x08\x99c`\x00\x00"
        b"\x00\x02\x00\x01\xe5w$o\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    return dummy_png, "smoke_test_image.png", "image/png"


# -----------------------------------------------------------------------------
# 3. Main End-to-End Execution
# -----------------------------------------------------------------------------
def main():
    print(f"============================================================")
    print(f"ClaimPilot End-to-End Smoke Test")
    print(f"Target Base URL: {BASE_URL}")
    print(f"Target Policy  : {POLICY_NUMBER}")
    print(f"============================================================")

    with httpx.Client(timeout=30.0) as client:
        # Step 1: Customer Login
        customer_token = login_flow(client, CUSTOMER_EMAIL, CUSTOMER_PASSWORD, "Customer")
        cust_headers = {"Authorization": f"Bearer {customer_token}"}

        # Step 2: Create Claim
        print("\n--- Submitting Claim ---")
        claim_payload = {
            "policy_number": POLICY_NUMBER,
            "incident_type": "Accident",
            "vehicle_name": "Honda City 2022",
            "hsrp_number": "MH12AB1234",
            "engine_number": "ENG123456",
            "chassis_number": "CHS123456",
            "incident_date": "2026-10-10",
            "location_address": "Western Express Highway, Mumbai",
            "description": "Front collision causing bumper dent and headlight crack.",
            "driver_name": "Demo Policyholder",
            "driver_dl_number": "MH1220110012345",
            "claimed_amount": 0.0,
        }

        create_resp = client.post(f"{BASE_URL}/claims", json=claim_payload, headers=cust_headers)
        log_response("Create Claim", create_resp)
        if create_resp.status_code >= 400:
            print(f"[FAIL] Claim creation rejected: HTTP {create_resp.status_code}")
            sys.exit(1)

        create_data = create_resp.json()
        claim_id = create_data.get("claim_id") or (create_data.get("claim") or {}).get("id")
        if not claim_id:
            print("[FAIL] Response missing claim_id primary key.")
            sys.exit(1)

        # Step 3: Upload Evidence Image
        print("\n--- Uploading Evidence Image ---")
        image_bytes, image_name, image_mime = resolve_image_file()

        presign_resp = client.post(
            f"{BASE_URL}/storage/presigned-url",
            json={
                "file_name": image_name,
                "file_type": image_mime,
                "category": "photo",
                "file_size_bytes": len(image_bytes),
            },
            headers=cust_headers,
        )
        log_response("Presigned URL", presign_resp)
        if presign_resp.status_code >= 400:
            print(f"[FAIL] Could not generate presigned upload URL.")
            sys.exit(1)

        presign_data = presign_resp.json()
        upload_url = presign_data.get("upload_url")
        public_url = presign_data.get("public_url")
        storage_path = presign_data.get("file_path", "")

        # Binary upload to destination URL
        try:
            put_resp = httpx.put(upload_url, content=image_bytes, headers={"Content-Type": image_mime}, timeout=20.0)
            print(f"[Storage Upload] HTTP {put_resp.status_code}")
        except Exception as upload_err:
            print(f"[WARN] Direct storage upload encountered error: {upload_err}. Proceeding with evidence catalog.")

        # Catalog evidence in database
        catalog_resp = client.post(
            f"{BASE_URL}/storage/evidence",
            json={
                "claim_id": claim_id,
                "file_url": public_url,
                "storage_path": storage_path,
                "file_type": image_mime,
                "category": "photo",
            },
            headers=cust_headers,
        )
        log_response("Catalog Evidence", catalog_resp)

        # Step 4: Poll until AI Analysis finishes (Timeout: 120s)
        print("\n--- Polling AI Damage & Fraud Analysis (Max 120s) ---")
        start_time = time.time()
        timeout_seconds = 120
        analysis_finished = False
        final_claim_data: Dict[str, Any] = {}

        while time.time() - start_time < timeout_seconds:
            poll_resp = client.get(f"{BASE_URL}/claims/{claim_id}", headers=cust_headers)
            if poll_resp.status_code == 200:
                body = poll_resp.json()
                claim_obj = body.get("claim", {})
                claim_status = claim_obj.get("status")
                ai_analysis = body.get("ai_analysis")

                log_response(
                    f"Poll +{int(time.time() - start_time)}s",
                    poll_resp,
                    extra=f"Status: '{claim_status}' | AI Analysis Attached: {bool(ai_analysis)}",
                )

                if ai_analysis and ai_analysis.get("detected_damages") is not None:
                    analysis_finished = True
                    final_claim_data = body
                    break

            time.sleep(3)

        if not analysis_finished:
            print("[FAIL] AI analysis timed out after 120 seconds.")
            sys.exit(1)

        print("[SUCCESS] Customer flow completed. AI analysis attached.")

        # Step 5: Agent Login & Adjudication Verification
        agent_token = login_flow(client, AGENT_EMAIL, AGENT_PASSWORD, "Agent")
        agent_headers = {"Authorization": f"Bearer {agent_token}"}

        print("\n--- Agent Fetching Adjudication Record ---")
        agent_claim_resp = client.get(f"{BASE_URL}/agent/claims/{claim_id}", headers=agent_headers)
        log_response("Agent Claim Detail", agent_claim_resp)

        if agent_claim_resp.status_code != 200:
            print(f"[FAIL] Agent could not fetch claim: HTTP {agent_claim_resp.status_code}")
            sys.exit(1)

        agent_data = agent_claim_resp.json()
        claim_record = agent_data.get("claim", {})
        ai_record = agent_data.get("ai_analysis", {})

        # Assertions
        print("\n--- Verifying Contract Assertions ---")
        assert "claim" in agent_data, "Assertion failed: 'claim' missing from agent response"
        assert "ai_analysis" in agent_data, "Assertion failed: 'ai_analysis' missing from agent response"
        assert ai_record is not None, "Assertion failed: 'ai_analysis' is null"
        assert "detected_damages" in ai_record, "Assertion failed: 'detected_damages' missing from ai_analysis"
        assert "fraud_score" in claim_record or "fraud_score" in ai_record, "Assertion failed: 'fraud_score' missing"
        assert "risk_level" in claim_record or "risk_level" in ai_record, "Assertion failed: 'risk_level' missing"

        print("[ASSERTION PASS] 'claim' and 'ai_analysis' records confirmed.")
        print("[ASSERTION PASS] 'detected_damages' present in AI analysis.")
        print("[ASSERTION PASS] 'fraud_score' and 'risk_level' present.")
        print("\n============================================================")
        print("🎉 ALL SMOKE TEST ASSERTIONS PASSED SUCCESSFULLY!")
        print("============================================================")


if __name__ == "__main__":
    main()
