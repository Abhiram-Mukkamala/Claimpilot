"""Capture redacted ClaimPilot API response contracts for human review.

The script performs network calls only when all SMOKE_* variables are present.
Use ``python capture_contract.py`` with no variables for an offline dry run.
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
OUTPUT_DIR = Path(__file__).resolve().parents[2] / "docs" / "api_contract"
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def redact(value: Any, key: str = "") -> Any:
    sensitive = re.compile(
        r"token|password|email|phone|name|signed.?url|storage.?path|file.?path|authorization",
        re.IGNORECASE,
    )
    if sensitive.search(key) and value is not None:
        return f"<REDACTED:{key.lower() or 'sensitive'}>"
    if isinstance(value, dict):
        return {str(item_key): redact(item, str(item_key)) for item_key, item in value.items()}
    if isinstance(value, list):
        return [redact(item, key) for item in value]
    if isinstance(value, str):
        value = re.sub(r"https?://\S+", "<REDACTED:url>", value)
        value = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "<REDACTED:email>", value)
        return value
    return value


def response_payload(response: httpx.Response) -> dict[str, Any]:
    try:
        body: Any = response.json()
    except (ValueError, TypeError):
        body = {"text": response.text}
    return {"status": response.status_code, "body": redact(body)}


def images() -> list[Path]:
    directory = Path(os.getenv("SMOKE_IMAGE_DIR", ""))
    if not directory.is_dir():
        return []
    return sorted(path for path in directory.iterdir() if path.suffix.lower() in IMAGE_EXTENSIONS)


def save_contract(name: str, response: httpx.Response) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / f"{name}.json").write_text(
        json.dumps(response_payload(response), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def save_payload(name: str, payload: Any) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / f"{name}.json").write_text(
        json.dumps({"body": redact(payload)}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def type_name(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return type(value).__name__


def summarize_fields(value: Any, prefix: str = "") -> list[str]:
    if not isinstance(value, dict):
        return [f"{prefix or '$'}: {type_name(value)}"]
    lines: list[str] = []
    for key, item in sorted(value.items()):
        path = f"{prefix}.{key}" if prefix else key
        if item is None:
            lines.append(f"- `{path}`: null")
        else:
            lines.append(f"- `{path}`: {type_name(item)}")
            if isinstance(item, dict):
                lines.extend(summarize_fields(item, path))
    return lines


def extract_claim_id(response: httpx.Response) -> str | None:
    data = response.json()
    return data.get("claim_id") or (data.get("claim") or {}).get("id")


def capture() -> int:
    missing = [name for name in REQUIRED_VARS if not os.getenv(name)]
    if missing:
        print(f"Missing required environment variable(s): {', '.join(missing)}")
        return 1
    image_list = images()
    if not image_list:
        print("SMOKE_IMAGE_DIR contains no supported image files")
        return 1

    captured: dict[str, dict[str, Any]] = {}
    with httpx.Client(timeout=30.0, follow_redirects=True) as client:
        customer_login = client.post(
            f"{BASE_URL}/auth/login",
            json={
                "email": os.environ["SMOKE_CUSTOMER_EMAIL"],
                "password": os.environ["SMOKE_CUSTOMER_PASSWORD"],
            },
        )
        save_contract("login_customer", customer_login)
        captured["POST /auth/login (customer)"] = response_payload(customer_login)
        customer_token = customer_login.json().get("access_token")
        if not customer_token:
            print("Customer login did not return an access token")
            return 1
        customer_headers = {"Authorization": f"Bearer {customer_token}"}

        bad_password = client.post(
            f"{BASE_URL}/auth/login",
            json={"email": os.environ["SMOKE_CUSTOMER_EMAIL"], "password": "deliberately-invalid"},
        )
        save_contract("login_bad_password", bad_password)
        captured["POST /auth/login (bad password)"] = response_payload(bad_password)

        create = client.post(
            f"{BASE_URL}/claims",
            headers=customer_headers,
            json={
                "policy_number": "DEMO-POL-001",
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
        save_contract("create_claim", create)
        captured["POST /claims"] = response_payload(create)
        claim_id = extract_claim_id(create)
        if not claim_id:
            print("Claim creation did not return a claim ID")
            return 1

        image = image_list[0]
        presign = client.post(
            f"{BASE_URL}/storage/presigned-url",
            headers=customer_headers,
            json={
                "file_name": image.name,
                "file_type": "image/png" if image.suffix.lower() == ".png" else "image/jpeg",
                "category": "photo",
                "file_size_bytes": image.stat().st_size,
            },
        )
        uploaded = client.put(
            presign.json().get("upload_url", ""),
            content=image.read_bytes(),
            headers={"Content-Type": "image/png" if image.suffix.lower() == ".png" else "image/jpeg"},
        )
        evidence = client.post(
            f"{BASE_URL}/storage/evidence",
            headers=customer_headers,
            json={
                "claim_id": claim_id,
                "file_url": presign.json().get("public_url"),
                "storage_path": presign.json().get("file_path"),
                "file_type": "image/png" if image.suffix.lower() == ".png" else "image/jpeg",
                "category": "photo",
            },
        )
        save_contract("storage_evidence", evidence)
        captured["POST /storage/evidence"] = response_payload(evidence)
        if uploaded.status_code not in {200, 201} or evidence.status_code not in {200, 201}:
            print("Evidence upload did not complete")
            return 1

        deadline = time.monotonic() + 120
        claim_detail = client.get(f"{BASE_URL}/claims/{claim_id}", headers=customer_headers)
        while time.monotonic() < deadline:
            if claim_detail.status_code == 200 and claim_detail.json().get("ai_analysis") is not None:
                break
            time.sleep(3)
            claim_detail = client.get(f"{BASE_URL}/claims/{claim_id}", headers=customer_headers)
        save_contract("claim_detail_customer", claim_detail)
        captured["GET /claims/:id"] = response_payload(claim_detail)
        analysis = claim_detail.json().get("ai_analysis") or {}
        save_payload("damage_analysis", analysis.get("detected_damages"))
        save_payload("fraud_analysis", {
            "fraud_score": analysis.get("fraud_score"),
            "risk_level": analysis.get("risk_level"),
            "fraud_flags": analysis.get("fraud_flags"),
        })
        save_payload("advanced_analysis", analysis.get("advanced_analysis"))
        captured["damage analysis payload"] = {
            "status": claim_detail.status_code,
            "body": redact(analysis.get("detected_damages")),
        }
        captured["fraud analysis payload"] = {
            "status": claim_detail.status_code,
            "body": redact({
                "fraud_score": analysis.get("fraud_score"),
                "risk_level": analysis.get("risk_level"),
                "fraud_flags": analysis.get("fraud_flags"),
            }),
        }
        captured["advanced analysis payload"] = {
            "status": claim_detail.status_code,
            "body": redact(analysis.get("advanced_analysis")),
        }

        claim_list = client.get(f"{BASE_URL}/claims", headers=customer_headers)
        save_contract("claims_customer", claim_list)
        captured["GET /claims"] = response_payload(claim_list)

        unknown = client.get(f"{BASE_URL}/claims/00000000-0000-0000-0000-000000000000", headers=customer_headers)
        save_contract("claim_unknown", unknown)
        captured["GET /claims/:unknown (404)"] = response_payload(unknown)

        agent_login = client.post(
            f"{BASE_URL}/auth/login",
            json={
                "email": os.environ["SMOKE_AGENT_EMAIL"],
                "password": os.environ["SMOKE_AGENT_PASSWORD"],
            },
        )
        save_contract("login_agent", agent_login)
        captured["POST /auth/login (agent)"] = response_payload(agent_login)
        agent_token = agent_login.json().get("access_token")
        if not agent_token:
            print("Agent login did not return an access token")
            return 1
        agent_headers = {"Authorization": f"Bearer {agent_token}"}
        agent_claims = client.get(f"{BASE_URL}/agent/claims", headers=agent_headers)
        save_contract("agent_claims", agent_claims)
        captured["GET /agent/claims"] = response_payload(agent_claims)
        agent_detail = client.get(f"{BASE_URL}/agent/claims/{claim_id}", headers=agent_headers)
        save_contract("agent_claim_detail", agent_detail)
        captured["GET /agent/claims/:id"] = response_payload(agent_detail)

    summary: list[str] = [
        "# API Contract Summary",
        "",
        "All response values were redacted before writing. A human must skim generated files for leftover personal data before committing.",
        "",
    ]
    for endpoint, payload in captured.items():
        summary.extend([f"## {endpoint}", "", f"- HTTP status: `{payload['status']}`"])
        summary.extend(summarize_fields(payload.get("body")))
        summary.append("")
    (OUTPUT_DIR / "SUMMARY.md").write_text("\n".join(summary), encoding="utf-8")
    print(f"Saved redacted API contracts under {OUTPUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(capture())
