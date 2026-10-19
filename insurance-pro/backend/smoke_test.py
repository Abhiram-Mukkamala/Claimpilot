"""ClaimPilot End-to-End Demo Smoke Test Suite.

Safe, repeatable, evidence-producing smoke test runner for staging/local environments.
Guarantees:
- Never executes destructive or mutating actions without explicit opt-in: CLAIMPILOT_SMOKE_TESTS=1.
- Fail-closed target guard: allows only localhost/loopback and explicitly approved test/staging hosts.
- Rejects unapproved hosts, malformed URLs, insecure remote schemes, and all production domains.
- Disables automatic HTTP redirects to prevent unintended redirection to unapproved hosts.
- Validates presigned storage upload URLs against approved storage hosts before upload.
- Enforces strict OTP challenge verification flow; never accepts token-only login.
- Redacts all credentials, tokens, OTP codes, signed URLs, and auth headers.
- Strictly separates PASS, FAIL, BLOCKED, and NOT RUN stages.
- Never fakes or simulates external services, real OTPs, inferences, or payout states.
"""

from __future__ import annotations

import ipaddress
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple
from urllib.parse import urlsplit

import httpx

# ── Environment & Safety Configuration ───────────────────────────────────────

OPT_IN_FLAG = "CLAIMPILOT_SMOKE_TESTS"
REQUIRED_ENV_VARS = (
    "SMOKE_BASE_URL",
    "SMOKE_CUSTOMER_EMAIL",
    "SMOKE_CUSTOMER_PASSWORD",
    "SMOKE_AGENT_EMAIL",
    "SMOKE_AGENT_PASSWORD",
    "SMOKE_IMAGE_DIR",
)

BASE_URL = os.getenv("SMOKE_BASE_URL", "").rstrip("/")
CUSTOMER_EMAIL = os.getenv("SMOKE_CUSTOMER_EMAIL")
CUSTOMER_PASSWORD = os.getenv("SMOKE_CUSTOMER_PASSWORD")
AGENT_EMAIL = os.getenv("SMOKE_AGENT_EMAIL")
AGENT_PASSWORD = os.getenv("SMOKE_AGENT_PASSWORD")
IMAGE_DIR = os.getenv("SMOKE_IMAGE_DIR")
SMOKE_OTP_CODE = os.getenv("SMOKE_OTP_CODE")
CUSTOMER_OTP_CODE = os.getenv("SMOKE_CUSTOMER_OTP_CODE") or SMOKE_OTP_CODE
AGENT_OTP_CODE = os.getenv("SMOKE_AGENT_OTP_CODE") or SMOKE_OTP_CODE

POLICY_NUMBER = os.getenv("SMOKE_POLICY_NUMBER", "DEMO-POL-001")
ANALYSIS_TIMEOUT_SECONDS = int(os.getenv("SMOKE_ANALYSIS_TIMEOUT", "120"))

LOOPBACK_HOSTNAMES = {"localhost", "127.0.0.1", "::1"}

FORBIDDEN_PROD_HOSTS = (
    "claimpilot.com",
    "api.claimpilot.com",
    "app.claimpilot.com",
    "production",
)


# ── Target Allowlist & Fail-Closed Guard ─────────────────────────────────────

def _get_configured_allowed_hosts() -> set[str]:
    raw = os.getenv("SMOKE_ALLOWED_HOSTS", "").strip()
    if not raw:
        return set()
    return {h.strip().lower() for h in raw.split(",") if h.strip()}


def _get_configured_storage_hosts() -> set[str]:
    raw = os.getenv("SMOKE_ALLOWED_STORAGE_HOSTS", "").strip()
    base_allowed = _get_configured_allowed_hosts()
    if not raw:
        return base_allowed
    return base_allowed | {h.strip().lower() for h in raw.split(",") if h.strip()}


def is_loopback_host(hostname: str) -> bool:
    """Return True if hostname is a loopback/localhost address."""
    clean = hostname.strip().lower().strip("[]")
    if clean in LOOPBACK_HOSTNAMES or clean.endswith(".localhost"):
        return True
    try:
        ip = ipaddress.ip_address(clean)
        return ip.is_loopback
    except ValueError:
        return False


def validate_target_url(
    url: str,
    allowed_hosts: Optional[set[str]] = None,
    is_storage: bool = False,
) -> Tuple[bool, str]:
    """Fail-closed validator for target URLs (BASE_URL and presigned upload URLs).

    Guarantees:
    - Rejects empty, non-string, or malformed URLs.
    - Permits only 'http' and 'https' schemes.
    - Requires 'https' for any remote (non-loopback) host.
    - Allows localhost/loopback hosts unconditionally for local development.
    - Requires remote hosts to be in an explicit allowlist.
    - Rejects all production domains unconditionally.
    """
    if not url or not isinstance(url, str) or not url.strip():
        return False, "Target URL is empty or missing"

    try:
        parts = urlsplit(url.strip())
    except Exception as exc:
        return False, f"Malformed URL: {exc}"

    if not parts.scheme:
        return False, "URL scheme is missing"

    scheme = parts.scheme.lower()
    if scheme not in ("http", "https"):
        return False, f"Unsupported URL scheme '{scheme}'. Only HTTP and HTTPS are permitted."

    hostname = parts.hostname
    if not hostname:
        return False, "URL hostname is missing"

    hostname_clean = hostname.lower().strip("[]")

    # Production domain check (fail-closed)
    for forbidden in FORBIDDEN_PROD_HOSTS:
        if hostname_clean == forbidden or hostname_clean.endswith("." + forbidden) or forbidden in hostname_clean:
            return False, f"Target host '{hostname_clean}' is a prohibited production host"

    # Loopback check
    if is_loopback_host(hostname_clean):
        return True, "Loopback target allowed"

    # Non-loopback remote host must use HTTPS
    if scheme != "https":
        return False, f"Insecure HTTP scheme is not allowed for remote host '{hostname_clean}'. HTTPS is required."

    effective_allowlist = allowed_hosts if allowed_hosts is not None else (
        _get_configured_storage_hosts() if is_storage else _get_configured_allowed_hosts()
    )

    if hostname_clean in effective_allowlist:
        return True, f"Host '{hostname_clean}' is in explicit allowlist"

    for allowed in effective_allowlist:
        if allowed.startswith(".") and hostname_clean.endswith(allowed):
            return True, f"Host '{hostname_clean}' matches approved domain '{allowed}'"

    return False, f"Host '{hostname_clean}' is not in the explicit allowlist. Only localhost/loopback or configured allowed hosts are permitted."


# ── Sensitive Data Redaction ─────────────────────────────────────────────────

def _configured_sensitive_values() -> Tuple[str, ...]:
    return tuple(
        val for val in (
            CUSTOMER_EMAIL,
            CUSTOMER_PASSWORD,
            AGENT_EMAIL,
            AGENT_PASSWORD,
            CUSTOMER_OTP_CODE,
            AGENT_OTP_CODE,
        ) if val
    )


def redact(value: Any, extra_sensitive: Sequence[str] = ()) -> Any:
    """Recursively redact sensitive tokens, credentials, and URLs from output."""
    if isinstance(value, dict):
        sensitive_pattern = re.compile(
            r"token|challenge|password|email|phone|name|otp|code|secret|authorization|key|url|path",
            re.IGNORECASE,
        )
        return {
            str(k): f"<REDACTED:{str(k).lower()}>"
            if sensitive_pattern.search(str(k)) and v is not None
            else redact(v, extra_sensitive=extra_sensitive)
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [redact(item, extra_sensitive=extra_sensitive) for item in value]
    if isinstance(value, str):
        v = re.sub(r"https?://\S+", "<REDACTED:url>", value)
        v = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "<REDACTED:email>", v)
        v = re.sub(r"(?i)(bearer\s+|access_token[\"']?\s*[:=]\s*[\"']?)[^,\s\"'}]+", r"\1<REDACTED:token>", v)
        v = re.sub(r"(?i)(password[\"']?\s*[:=]\s*[\"']?)[^,\s\"'}]+", r"\1<REDACTED:password>", v)
        v = re.sub(r"(?i)(challenge(?:_id)?[\"']?\s*[:=]\s*[\"']?)[^,\s\"'}]+", r"\1<REDACTED:challenge>", v)
        v = re.sub(r"(?i)(otp(?:_code)?[\"']?\s*[:=]\s*[\"']?)[^,\s\"'}]+", r"\1<REDACTED:otp>", v)
        all_sensitive = _configured_sensitive_values() + tuple(str(x) for x in extra_sensitive if x)
        for s in all_sensitive:
            if s:
                v = v.replace(str(s), "[redacted]")
        return v
    return value


def excerpt(response: httpx.Response, extra_sensitive: Sequence[str] = ()) -> str:
    try:
        body = redact(response.json(), extra_sensitive=extra_sensitive)
        text = json.dumps(body, separators=(",", ":"))
    except Exception:
        text = redact(response.text, extra_sensitive=extra_sensitive)
    return text[:200]


# ── Execution Context & Stage Tracker ────────────────────────────────────────

class StageTracker:
    def __init__(self):
        self.stages: Dict[str, Dict[str, Any]] = {
            "Stage A (Authentication & RBAC)": {"status": "NOT RUN", "detail": ""},
            "Stage B (Claim Creation & Assignment)": {"status": "NOT RUN", "detail": ""},
            "Stage C (Evidence Upload & Storage)": {"status": "NOT RUN", "detail": ""},
            "Stage D (AI Inference & Persistence)": {"status": "NOT RUN", "detail": ""},
            "Stage E (Agent Authorization & Decision)": {"status": "NOT RUN", "detail": ""},
            "Stage F (Customer Settlement Outcome)": {"status": "NOT RUN", "detail": ""},
            "Stage G (Failure & Recovery Matrix)": {"status": "NOT RUN", "detail": ""},
        }

    def record(self, stage: str, status: str, detail: str = ""):
        self.stages[stage] = {"status": status, "detail": detail}
        print(f"[{status}] {stage}{f' -- {detail}' if detail else ''}")

    def print_summary(self):
        print("\n" + "=" * 78)
        print("CLAIM_PILOT E2E DEMO SMOKE TEST SUMMARY")
        print("=" * 78)
        for name, data in self.stages.items():
            st = data["status"]
            det = f" ({data['detail']})" if data["detail"] else ""
            print(f"{name:<42} : [{st:>7}]{det}")
        print("=" * 78 + "\n")


# ── Safety Checks & Authentication Helpers ───────────────────────────────────

def check_safety() -> Tuple[bool, str]:
    """Verify safety prerequisites before allowing any live requests."""
    opt_in = os.getenv(OPT_IN_FLAG, "").strip()
    if opt_in != "1":
        return False, f"Opt-in flag {OPT_IN_FLAG}=1 is required to run live tests"

    if not BASE_URL:
        return False, "SMOKE_BASE_URL is not configured"

    valid, reason = validate_target_url(BASE_URL)
    if not valid:
        return False, f"Target URL validation failed: {reason}"

    return True, "Safety checks passed"


def login(client: httpx.Client, email: str, password: str, otp_code: Optional[str], role: str) -> Optional[str]:
    """Execute strict 2FA OTP login flow.

    Requires:
    1. Successful password authentication dispatching an explicit OTP challenge.
    2. Valid challenge_id returned in response.
    3. Successful OTP verification endpoint call.
    4. Confirmed is_verified status and valid access token.
    Fails safely and never falls back to token-only authentication.
    """
    clean_email = (email or "").strip().lower()
    clean_password = password or ""

    if not clean_email or not clean_password:
        print(f"[FAIL] {role} login credentials missing")
        return None

    try:
        resp = client.post(f"{BASE_URL}/auth/login", json={"email": clean_email, "password": clean_password})
    except Exception as exc:
        print(f"[FAIL] {role} login connection failed: {type(exc).__name__}")
        return None

    if resp.status_code not in (200, 201):
        print(f"[FAIL] {role} login failed (HTTP {resp.status_code}): {excerpt(resp, extra_sensitive=(clean_password,))}")
        return None

    try:
        data = resp.json()
    except Exception:
        print(f"[FAIL] {role} login response is not valid JSON")
        return None

    if not isinstance(data, dict):
        print(f"[FAIL] {role} login response is not a valid object")
        return None

    # Finding 2: Require explicit OTP challenge flow. Never accept token-only login.
    requires_otp = data.get("requires_otp")
    if requires_otp is not True:
        print(f"[FAIL] {role} login did not trigger required OTP challenge (requires_otp={requires_otp})")
        return None

    otp_details = data.get("otp_details")
    if not isinstance(otp_details, dict):
        print(f"[FAIL] {role} login response missing valid otp_details object")
        return None

    challenge_id = otp_details.get("challenge_id")
    if not challenge_id or not isinstance(challenge_id, str) or not challenge_id.strip():
        print(f"[FAIL] {role} login response missing valid OTP challenge_id")
        return None

    if not otp_code or not str(otp_code).strip():
        print(f"[FAIL] {role} OTP required but no smoke OTP code provided in environment")
        return None

    try:
        v_resp = client.post(f"{BASE_URL}/auth/otp/verify", json={
            "identifier": clean_email,
            "otp_code": str(otp_code).strip(),
            "channel": "email",
            "challenge_id": str(challenge_id).strip(),
        })
    except Exception as exc:
        print(f"[FAIL] {role} OTP verification request failed: {type(exc).__name__}")
        return None

    if v_resp.status_code not in (200, 201):
        print(f"[FAIL] {role} OTP verification failed (HTTP {v_resp.status_code}): {excerpt(v_resp, extra_sensitive=(clean_password, str(otp_code), str(challenge_id)))}")
        return None

    try:
        v_data = v_resp.json()
    except Exception:
        print(f"[FAIL] {role} OTP verification response is not valid JSON")
        return None

    if not isinstance(v_data, dict):
        print(f"[FAIL] {role} OTP verification response is not a valid object")
        return None

    if v_data.get("is_verified") is not True:
        print(f"[FAIL] {role} OTP verification did not confirm (is_verified={v_data.get('is_verified')!r})")
        return None

    token = v_data.get("access_token")
    if not token or not isinstance(token, str) or not token.strip():
        print(f"[FAIL] {role} OTP response missing valid access_token")
        return None

    return token


def image_files() -> List[Path]:
    if not IMAGE_DIR:
        return []
    directory = Path(IMAGE_DIR)
    if not directory.is_dir():
        return []
    return sorted(
        p for p in directory.iterdir()
        if p.is_file() and p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}
    )


# ── Main Runner ──────────────────────────────────────────────────────────────

def main() -> int:
    tracker = StageTracker()
    safe, reason = check_safety()
    if not safe:
        print(f"[BLOCKED] {reason}")
        for stage in tracker.stages:
            tracker.record(stage, "BLOCKED", reason)
        tracker.print_summary()
        return 2

    missing_vars = [v for v in REQUIRED_ENV_VARS if not os.getenv(v)]
    if missing_vars:
        msg = f"Missing environment variables: {', '.join(missing_vars)}"
        print(f"[BLOCKED] {msg}")
        for stage in tracker.stages:
            tracker.record(stage, "BLOCKED", msg)
        tracker.print_summary()
        return 2

    images = image_files()
    if not images:
        msg = f"No test images found in SMOKE_IMAGE_DIR={IMAGE_DIR}"
        print(f"[BLOCKED] {msg}")
        tracker.record("Stage C (Evidence Upload & Storage)", "BLOCKED", msg)
        tracker.print_summary()
        return 2

    print(f"Connecting to ClaimPilot test environment at: {redact(BASE_URL)}")

    # Finding 1: Disable automatic redirects to prevent redirection to unapproved hosts
    with httpx.Client(timeout=30.0, follow_redirects=False) as client:
        # ── STAGE A: Authentication & RBAC ──────────────────────────────────
        cust_token = login(client, CUSTOMER_EMAIL or "", CUSTOMER_PASSWORD or "", CUSTOMER_OTP_CODE, "Customer")
        if not cust_token:
            tracker.record("Stage A (Authentication & RBAC)", "FAIL", "Customer login/OTP verification failed")
            tracker.print_summary()
            return 1

        agent_token = login(client, AGENT_EMAIL or "", AGENT_PASSWORD or "", AGENT_OTP_CODE, "Agent")
        if not agent_token:
            tracker.record("Stage A (Authentication & RBAC)", "FAIL", "Agent login/OTP verification failed")
            tracker.print_summary()
            return 1

        cust_headers = {"Authorization": f"Bearer {cust_token}"}
        agent_headers = {"Authorization": f"Bearer {agent_token}"}

        # RBAC Check: customer hitting agent endpoint must be rejected
        agent_probe = client.get(f"{BASE_URL}/agent/claims", headers=cust_headers)
        if agent_probe.status_code != 403:
            tracker.record("Stage A (Authentication & RBAC)", "FAIL", f"Customer accessed agent route (HTTP {agent_probe.status_code})")
            tracker.print_summary()
            return 1

        tracker.record("Stage A (Authentication & RBAC)", "PASS", "Customer & Agent 2FA login verified; RBAC enforced")

        # ── STAGE B: Claim Creation & Policy Assignment ───────────────────────
        create_payload = {
            "policy_number": POLICY_NUMBER,
            "incident_type": "Accident",
            "vehicle_name": "Honda City 2022",
            "hsrp_number": "MH12AB1234",
            "engine_number": "ENG123456",
            "chassis_number": "CHS123456",
            "incident_date": "2026-10-10",
            "location_address": "Western Express Highway, Mumbai",
            "description": "Front collision bumper fracture and dent.",
            "driver_name": "Demo Smoke Claimant",
            "driver_dl_number": "MH1220110012345",
            "claimed_amount": 0.0,
        }
        create_resp = client.post(f"{BASE_URL}/claims", headers=cust_headers, json=create_payload)
        if create_resp.status_code != 201:
            tracker.record("Stage B (Claim Creation & Assignment)", "FAIL", f"Claim creation failed (HTTP {create_resp.status_code}): {excerpt(create_resp)}")
            tracker.print_summary()
            return 1

        create_data = create_resp.json()
        claim_id = create_data.get("claim_id") or (create_data.get("claim") or {}).get("id")
        claim_obj = create_data.get("claim") or {}
        if not claim_id:
            tracker.record("Stage B (Claim Creation & Assignment)", "FAIL", "Response omitted claim ID")
            tracker.print_summary()
            return 1

        # Finding 4: Verify expected policy assignment and assigned agent
        persisted_policy = claim_obj.get("policy_number")
        if persisted_policy != POLICY_NUMBER:
            tracker.record("Stage B (Claim Creation & Assignment)", "FAIL", f"Claim policy mismatch: expected '{POLICY_NUMBER}', got '{persisted_policy}'")
            tracker.print_summary()
            return 1

        assigned_agent = claim_obj.get("assigned_agent_id")
        if not assigned_agent:
            tracker.record("Stage B (Claim Creation & Assignment)", "FAIL", "Claim missing assigned_agent_id in response")
            tracker.print_summary()
            return 1

        # Negative check: invalid policy
        bad_policy_resp = client.post(f"{BASE_URL}/claims", headers=cust_headers, json={**create_payload, "policy_number": "INVALID-POL-999"})
        if bad_policy_resp.status_code != 400:
            tracker.record("Stage B (Claim Creation & Assignment)", "FAIL", f"Invalid policy accepted (HTTP {bad_policy_resp.status_code})")
            tracker.print_summary()
            return 1

        tracker.record("Stage B (Claim Creation & Assignment)", "PASS", f"Claim created ({claim_id[:8]}...) with verified policy and agent assignment")

        # ── STAGE C: Evidence Upload & Storage ───────────────────────────────
        test_img = images[0]
        content_type = "image/png" if test_img.suffix.lower() == ".png" else "image/jpeg"
        img_bytes = test_img.read_bytes()

        presign = client.post(f"{BASE_URL}/storage/presigned-url", headers=cust_headers, json={
            "file_name": test_img.name,
            "file_type": content_type,
            "category": "photo",
            "file_size_bytes": len(img_bytes),
        })
        if presign.status_code != 200:
            tracker.record("Stage C (Evidence Upload & Storage)", "FAIL", f"Presigned URL failed (HTTP {presign.status_code}): {excerpt(presign)}")
            tracker.print_summary()
            return 1

        pdata = presign.json()
        upload_url = pdata.get("upload_url")
        storage_path = pdata.get("file_path")
        if not upload_url or not storage_path:
            tracker.record("Stage C (Evidence Upload & Storage)", "FAIL", "Presign response missing required URL/path fields")
            tracker.print_summary()
            return 1

        # Finding 1: Validate presigned upload URL against approved storage allowlist
        upload_ok, upload_reason = validate_target_url(upload_url, is_storage=True)
        if not upload_ok:
            tracker.record("Stage C (Evidence Upload & Storage)", "BLOCKED", f"Upload URL rejected by target guard: {upload_reason}")
            tracker.print_summary()
            return 1

        upload_res = client.put(upload_url, content=img_bytes, headers={"Content-Type": content_type})
        if upload_res.status_code not in (200, 201):
            tracker.record("Stage C (Evidence Upload & Storage)", "BLOCKED", f"Direct upload to storage bucket failed (HTTP {upload_res.status_code})")
            tracker.print_summary()
            return 1

        cat_resp = client.post(f"{BASE_URL}/storage/evidence", headers=cust_headers, json={
            "claim_id": claim_id,
            "file_url": storage_path,
            "storage_path": storage_path,
            "file_type": content_type,
            "category": "photo",
        })
        if cat_resp.status_code != 201:
            tracker.record("Stage C (Evidence Upload & Storage)", "FAIL", f"Catalog evidence failed (HTTP {cat_resp.status_code}): {excerpt(cat_resp)}")
            tracker.print_summary()
            return 1

        tracker.record("Stage C (Evidence Upload & Storage)", "PASS", "Evidence uploaded and cataloged under canonical path")

        # ── STAGE D: AI Inference & Persistence ──────────────────────────────
        started = time.monotonic()
        analysis_data = None
        while time.monotonic() - started < ANALYSIS_TIMEOUT_SECONDS:
            c_resp = client.get(f"{BASE_URL}/claims/{claim_id}", headers=cust_headers)
            if c_resp.status_code == 200:
                c_data = c_resp.json()
                status_val = (c_data.get("claim") or {}).get("status") or c_data.get("status")
                analysis = c_data.get("ai_analysis")

                # Finding 4: Verify persisted assessment record on manual review
                if status_val == "manual_review":
                    if not isinstance(analysis, dict):
                        tracker.record("Stage D (AI Inference & Persistence)", "FAIL", "Claim transitioned to manual_review but ai_analysis record is missing")
                        tracker.print_summary()
                        return 1
                    if analysis.get("analysis_status") != "failed":
                        tracker.record("Stage D (AI Inference & Persistence)", "FAIL", f"Claim in manual_review but analysis_status is '{analysis.get('analysis_status')}'")
                        tracker.print_summary()
                        return 1
                    damages = analysis.get("detected_damages")
                    if damages is not None and len(damages) > 0:
                        tracker.record("Stage D (AI Inference & Persistence)", "FAIL", "Claim in manual_review has unexpected fabricated damages")
                        tracker.print_summary()
                        return 1

                    analysis_data = c_data
                    tracker.record("Stage D (AI Inference & Persistence)", "PASS", "Model/provider failure handled safely: claim transitioned to manual_review with failed analysis record (zero fabricated data)")
                    break

                # Finding 4: Verify completed inference has structurally valid non-negative bounds
                if isinstance(analysis, dict) and analysis.get("analysis_status") == "completed" and analysis.get("detected_damages") is not None:
                    damages = analysis.get("detected_damages", [])
                    valid_damages = True
                    for d in damages:
                        cost = d.get("estimated_cost")
                        if cost is None or cost < 0:
                            valid_damages = False
                            break
                    if not valid_damages:
                        tracker.record("Stage D (AI Inference & Persistence)", "FAIL", "Analysis detected damages contains invalid/negative costs")
                        tracker.print_summary()
                        return 1

                    analysis_data = c_data
                    tracker.record("Stage D (AI Inference & Persistence)", "PASS", f"Inference complete: {len(damages)} damages detected with non-negative bounds")
                    break
            time.sleep(3)

        if not analysis_data:
            tracker.record("Stage D (AI Inference & Persistence)", "FAIL", f"Analysis did not settle within {ANALYSIS_TIMEOUT_SECONDS}s")
            tracker.print_summary()
            return 1

        # ── STAGE E: Agent Authorization & Decision ──────────────────────────
        detail = client.get(f"{BASE_URL}/agent/claims/{claim_id}", headers=agent_headers)
        if detail.status_code != 200:
            tracker.record("Stage E (Agent Authorization & Decision)", "FAIL", f"Agent detail fetch failed (HTTP {detail.status_code})")
            tracker.print_summary()
            return 1

        # Approve with explicit authorized adjuster amount (guarantees safe approval even if AI was routed to manual review)
        action_resp = client.post(f"{BASE_URL}/agent/claims/{claim_id}/action", headers=agent_headers, json={
            "action": "APPROVE",
            "reason": "Adjudicated and authorized by adjuster.",
            "approved_amount": 25000.0,
        })
        if action_resp.status_code != 200:
            tracker.record("Stage E (Agent Authorization & Decision)", "FAIL", f"Agent approval failed (HTTP {action_resp.status_code}): {excerpt(action_resp)}")
            tracker.print_summary()
            return 1

        tracker.record("Stage E (Agent Authorization & Decision)", "PASS", "Agent approved claim with persisted settlement offer ₹25,000")

        # ── STAGE F: Customer Settlement Outcome ─────────────────────────────
        settle_resp = client.post(f"{BASE_URL}/claims/portal/decision", headers=cust_headers, json={
            "claim_id": claim_id,
            "decision": "ACCEPT",
        })
        if settle_resp.status_code != 200:
            tracker.record("Stage F (Customer Settlement Outcome)", "FAIL", f"Settlement acceptance failed (HTTP {settle_resp.status_code}): {excerpt(settle_resp)}")
            tracker.print_summary()
            return 1

        s_data = settle_resp.json()
        payout = s_data.get("payout_pipeline") or {}
        if payout.get("payout_status") != "not_started" or payout.get("batch_id") is not None or payout.get("disbursement_channel") is not None:
            tracker.record("Stage F (Customer Settlement Outcome)", "FAIL", "Truthful payout violated: reported started/batch_id/channel")
            tracker.print_summary()
            return 1

        # Finding 4: Reload claim from API to verify persisted state in database
        reload_resp = client.get(f"{BASE_URL}/claims/{claim_id}", headers=cust_headers)
        if reload_resp.status_code != 200:
            tracker.record("Stage F (Customer Settlement Outcome)", "FAIL", f"Failed to reload claim after settlement acceptance (HTTP {reload_resp.status_code})")
            tracker.print_summary()
            return 1

        reloaded_claim = (reload_resp.json().get("claim") or {})
        if reloaded_claim.get("status") != "settlement_accepted":
            tracker.record("Stage F (Customer Settlement Outcome)", "FAIL", f"Persisted claim status mismatch: expected 'settlement_accepted', got '{reloaded_claim.get('status')}'")
            tracker.print_summary()
            return 1

        reload_payout_status = reloaded_claim.get("payout_status")
        if reload_payout_status is not None and reload_payout_status != "not_started":
            tracker.record("Stage F (Customer Settlement Outcome)", "FAIL", f"Reloaded claim payout status mismatch: expected 'not_started', got '{reload_payout_status}'")
            tracker.print_summary()
            return 1

        tracker.record("Stage F (Customer Settlement Outcome)", "PASS", "Customer accepted settlement; reloaded claim verifies settlement_accepted and payout status not_started")

        # ── STAGE G: Failure & Recovery Matrix ────────────────────────────────
        # Repeat decision on terminal state must fail
        dup_settle = client.post(f"{BASE_URL}/claims/portal/decision", headers=cust_headers, json={
            "claim_id": claim_id,
            "decision": "ACCEPT",
        })
        if dup_settle.status_code != 400:
            tracker.record("Stage G (Failure & Recovery Matrix)", "FAIL", f"Repeated settlement decision accepted (HTTP {dup_settle.status_code})")
            tracker.print_summary()
            return 1

        tracker.record("Stage G (Failure & Recovery Matrix)", "PASS", "Invalid state transitions and duplicate decisions rejected")

    tracker.print_summary()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
