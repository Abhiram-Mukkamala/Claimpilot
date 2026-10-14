"""ClaimPilot demo smoke test.

Configuration is provided only through SMOKE_* environment variables.
This script does not print credentials, tokens, signed URLs, or response bodies.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any

import httpx


REQUIRED_VARS = (
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
POLICY_NUMBER = "DEMO-POL-001"
ANALYSIS_TIMEOUT_SECONDS = 120


def _configured_sensitive_values() -> tuple[str, ...]:
    return tuple(
        value
        for value in (
            CUSTOMER_EMAIL,
            CUSTOMER_PASSWORD,
            AGENT_EMAIL,
            AGENT_PASSWORD,
            CUSTOMER_OTP_CODE,
            AGENT_OTP_CODE,
        )
        if value
    )


def redact(value: Any) -> Any:
    """Redact sensitive values while preserving response structure."""
    if isinstance(value, dict):
        sensitive = re.compile(
            r"token|password|email|phone|name|otp|verification.?code|identifier|url|storage.?path|file.?path|authorization",
            re.IGNORECASE,
        )
        return {
            str(key): f"<REDACTED:{str(key).lower()}>"
            if sensitive.search(str(key)) and item is not None
            else redact(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, str):
        value = re.sub(r"https?://\S+", "<REDACTED:url>", value)
        value = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "<REDACTED:email>", value)
        value = re.sub(r"(?i)(bearer\s+|access_token[\"']?\s*[:=]\s*[\"']?)[^,\s\"'}]+", r"\1<REDACTED:token>", value)
        value = re.sub(r"(?i)(password[\"']?\s*[:=]\s*[\"']?)[^,\s\"'}]+", r"\1<REDACTED:password>", value)
        for sensitive_value in _configured_sensitive_values():
            value = value.replace(sensitive_value, "[redacted]")
        return value
    return value


def excerpt(response: httpx.Response) -> str:
    try:
        body = redact(response.json())
        text = json.dumps(body, separators=(",", ":"))
    except (ValueError, TypeError):
        text = redact(response.text)
    return text[:240]


def check(name: str, passed: bool, response: httpx.Response | None = None, detail: str = "") -> bool:
    if passed:
        print(f"[PASS] {name}")
        return True
    suffix = f" | {detail}" if detail else ""
    if response is not None:
        suffix += f" | HTTP {response.status_code} | {excerpt(response)}"
    print(f"[FAIL] {name}{suffix}")
    return False


def request_ok(name: str, response: httpx.Response, expected: set[int]) -> bool:
    return check(
        name,
        response.status_code in expected,
        response=response if response.status_code not in expected else None,
    )


def login(client: httpx.Client, email: str, password: str, otp_code: str | None, role: str) -> str | None:
    response = client.post(
        f"{BASE_URL}/auth/login",
        json={"email": email, "password": password},
    )
    if response.status_code not in {200, 201}:
        check(f"{role} login", False, response=response)
        return None
    data = response.json()
    token = data.get("access_token")
    if data.get("requires_otp"):
        if not otp_code:
            check(f"{role} OTP verification", False, response=response, detail="OTP code was not configured")
            return None
        verification = client.post(
            f"{BASE_URL}/auth/otp/verify",
            json={"identifier": email, "otp_code": otp_code, "channel": "email"},
        )
        if verification.status_code not in {200, 201}:
            check(f"{role} OTP verification", False, response=verification)
            return None
        token = verification.json().get("access_token")
        check(f"{role} OTP verification", bool(token), response=verification if not token else None)
        return token
    check(f"{role} login", bool(token), response=response if not token else None)
    return token


def image_files() -> list[Path]:
    if not IMAGE_DIR:
        return []
    directory = Path(IMAGE_DIR)
    if not directory.is_dir():
        return []
    return sorted(
        path for path in directory.iterdir()
        if path.is_file() and path.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}
    )


def create_claim(client: httpx.Client, headers: dict[str, str]) -> httpx.Response:
    return client.post(
        f"{BASE_URL}/claims",
        headers=headers,
        json={
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
        },
    )


def upload_image(
    client: httpx.Client,
    headers: dict[str, str],
    claim_id: str,
    image: Path,
) -> bool:
    content_type = "image/png" if image.suffix.lower() == ".png" else "image/jpeg"
    image_bytes = image.read_bytes()
    presign = client.post(
        f"{BASE_URL}/storage/presigned-url",
        headers=headers,
        json={
            "file_name": image.name,
            "file_type": content_type,
            "category": "photo",
            "file_size_bytes": len(image_bytes),
        },
    )
    if not request_ok("Request evidence upload URL", presign, {200}):
        return False
    data = presign.json()
    upload_url = data.get("upload_url")
    public_url = data.get("public_url")
    storage_path = data.get("file_path")
    if not all(isinstance(value, str) and value for value in (upload_url, public_url, storage_path)):
        return check("Evidence upload URL response fields", False, response=presign)
    uploaded = client.put(upload_url, content=image_bytes, headers={"Content-Type": content_type})
    if not request_ok("Upload evidence image", uploaded, {200, 201}):
        return False
    catalog = client.post(
        f"{BASE_URL}/storage/evidence",
        headers=headers,
        json={
            "claim_id": claim_id,
            "file_url": public_url,
            "storage_path": storage_path,
            "file_type": content_type,
            "category": "photo",
        },
    )
    return request_ok("Catalog evidence image", catalog, {200, 201})


def claim_id_from(response: httpx.Response) -> str | None:
    data = response.json()
    claim = data.get("claim") or {}
    return data.get("claim_id") or claim.get("id")


def poll_analysis(
    client: httpx.Client,
    headers: dict[str, str],
    claim_id: str,
    check_name: str,
) -> dict[str, Any] | None:
    started = time.monotonic()
    while time.monotonic() - started < ANALYSIS_TIMEOUT_SECONDS:
        response = client.get(f"{BASE_URL}/claims/{claim_id}", headers=headers)
        if response.status_code == 200:
            data = response.json()
            analysis = data.get("ai_analysis")
            if isinstance(analysis, dict) and analysis.get("detected_damages") is not None:
                check(check_name, True)
                return data
        time.sleep(3)
    check(check_name, False, detail=f"analysis did not complete within {ANALYSIS_TIMEOUT_SECONDS}s")
    return None


def has_real_bbox(analysis: dict[str, Any]) -> bool:
    damages = analysis.get("detected_damages")
    if not isinstance(damages, list):
        return False
    for damage in damages:
        if not isinstance(damage, dict):
            continue
        bbox = damage.get("bbox") or damage.get("bounding_box")
        if isinstance(bbox, (list, tuple)) and len(bbox) >= 4:
            try:
                if all(float(value) >= 0 for value in bbox):
                    return True
            except (TypeError, ValueError):
                continue
        if isinstance(bbox, dict) and all(key in bbox for key in ("x", "y", "width", "height")):
            return True
    return False


def has_duplicate_flag(data: dict[str, Any]) -> bool:
    analysis = data.get("ai_analysis") or {}
    claim = data.get("claim") or {}
    values = [
        analysis.get("fraud_flags"),
        analysis.get("fraud_indicators"),
        claim.get("fraud_flags"),
        claim.get("fraud_indicator"),
        claim.get("risk_level"),
    ]
    text = json.dumps(values).lower()
    return any(marker in text for marker in ("duplicate", "phash", "p_hash", "reused", "fraud"))


def main() -> int:
    missing = [name for name in REQUIRED_VARS if not os.getenv(name)]
    if missing:
        print(f"[FAIL] Missing required environment variable(s): {', '.join(missing)}")
        return 1
    if not CUSTOMER_OTP_CODE or not AGENT_OTP_CODE:
        print("[FAIL] Missing required environment variable(s): SMOKE_OTP_CODE or role-specific smoke OTP codes")
        return 1

    files = image_files()
    if not files:
        print("[FAIL] SMOKE_IMAGE_DIR contains no supported image files")
        return 1

    results: list[bool] = []
    with httpx.Client(timeout=30.0, follow_redirects=True) as client:
        customer_token = login(client, CUSTOMER_EMAIL or "", CUSTOMER_PASSWORD or "", CUSTOMER_OTP_CODE, "Customer")
        if not customer_token:
            return 1
        customer_headers = {"Authorization": f"Bearer {customer_token}"}

        create = create_claim(client, customer_headers)
        results.append(request_ok("Create claim against DEMO-POL-001", create, {201}))
        if not results[-1]:
            return 1
        first_claim_id = claim_id_from(create)
        results.append(check("Create claim response contains claim ID", bool(first_claim_id), response=create))
        if not first_claim_id:
            return 1

        for image in files:
            results.append(upload_image(client, customer_headers, first_claim_id, image))
        if not all(results[-len(files):]):
            return 1

        first_data = poll_analysis(client, customer_headers, first_claim_id, "Poll first claim analysis (120s)")
        if first_data is None:
            return 1
        first_analysis = first_data.get("ai_analysis") or {}
        results.append(check("Analysis is not marked mock", first_analysis.get("mock") is not True))
        results.append(check("Analysis contains a real damage bbox", has_real_bbox(first_analysis)))

        duplicate_create = create_claim(client, customer_headers)
        results.append(request_ok("Create second claim for duplicate-image check", duplicate_create, {201}))
        if not results[-1]:
            return 1
        duplicate_claim_id = claim_id_from(duplicate_create)
        results.append(check("Second claim response contains claim ID", bool(duplicate_claim_id), response=duplicate_create))
        if not duplicate_claim_id:
            return 1
        results.append(upload_image(client, customer_headers, duplicate_claim_id, files[0]))
        duplicate_data = poll_analysis(
            client,
            customer_headers,
            duplicate_claim_id,
            "Poll duplicate claim analysis (120s)",
        )
        results.append(
            check(
                "Duplicate image produces pHash/fraud flag",
                duplicate_data is not None and has_duplicate_flag(duplicate_data),
                detail="no duplicate, pHash, reused-image, or fraud marker returned",
            )
        )

        agent_token = login(client, AGENT_EMAIL or "", AGENT_PASSWORD or "", AGENT_OTP_CODE, "Agent")
        if not agent_token:
            return 1
        agent_headers = {"Authorization": f"Bearer {agent_token}"}
        queue = client.get(f"{BASE_URL}/agent/claims", headers=agent_headers)
        results.append(request_ok("Agent fetch claims", queue, {200}))
        detail = client.get(f"{BASE_URL}/agent/claims/{first_claim_id}", headers=agent_headers)
        results.append(request_ok("Agent fetch claim detail", detail, {200}))
        if detail.status_code == 200:
            action = client.post(
                f"{BASE_URL}/agent/claims/{first_claim_id}/action",
                headers=agent_headers,
                json={"action": "REQUEST_INFO", "requested_items": ["damage_photos"]},
            )
            results.append(request_ok("Agent decision", action, {200}))
        else:
            results.append(False)

    passed = sum(results)
    print(f"SUMMARY: {passed}/{len(results)} checks passed")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
