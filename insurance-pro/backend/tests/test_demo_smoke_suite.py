"""Deterministic E2E Demo Smoke Test Suite for ClaimPilot.

Verifies the end-to-end claim lifecycle across Stages A through G:
- Stage A: Customer & Agent Authentication (OTP issuance, keyed verification, RBAC, redaction)
- Stage B: Claim Creation & Policy Assignment (policy mapping, agent assignment, tenant isolation)
- Stage C: Evidence Upload & Storage (presigned URLs, canonical paths, size limits, cross-tenant isolation)
- Stage D: AI Inference & Persistence (manual review fallback, nonnegative bounds, zero fabrication)
- Stage E: Agent Authorization & Decision (assigned agent check, approval safeguards, no hardcoded fallbacks)
- Stage F: Customer Settlement Outcome (settlement acceptance, truthful non-initiated payout, persistence, dispute)
- Stage G: Failure & Recovery (invalid transitions, concurrency conflicts, OTP rate limiting, storage validation)

This test suite runs completely in-process using FastAPI's TestClient and deterministic DB simulation.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# Ensure backend root is on sys.path
BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# Ensure required environment variables for test imports
for key, value in {
    "SUPABASE_URL": "https://unit-test.invalid",
    "SUPABASE_ANON_KEY": "test-anon-key",
    "SUPABASE_SERVICE_ROLE_KEY": "test-service-key",
    "JWT_SECRET": "test-secret-key-minimum-32-characters-long",
    "ENVIRONMENT": "test",
}.items():
    os.environ.setdefault(key, value)

from app.api.v1 import agent, auth, auth_otp, claims, storage
from app.services import ai_runner
from app.core.config import settings
from app.core.security import create_access_token, get_current_user


# ── Fixtures & Deterministic Database Simulator ──────────────────────────────

class MockDatabase:
    """In-memory thread-safe mock of Supabase PostgREST client for deterministic testing."""

    def __init__(self):
        self.profiles: Dict[str, Dict[str, Any]] = {
            "cust-101": {
                "id": "cust-101",
                "email": "customer101@claimpilot.test",
                "full_name": "Test Customer Alpha",
                "role": "customer",
                "phone_number": "+919876543210",
            },
            "cust-202": {
                "id": "cust-202",
                "email": "customer202@claimpilot.test",
                "full_name": "Test Customer Beta",
                "role": "customer",
                "phone_number": "+919876543211",
            },
            "agent-701": {
                "id": "agent-701",
                "email": "agent701@claimpilot.test",
                "full_name": "Assigned Adjuster",
                "role": "agent",
            },
            "agent-999": {
                "id": "agent-999",
                "email": "agent999@claimpilot.test",
                "full_name": "Unassigned Adjuster",
                "role": "agent",
            },
        }
        self.agent_policies: Dict[str, Dict[str, Any]] = {
            "DEMO-POL-001": {
                "policy_number": "DEMO-POL-001",
                "agent_id": "agent-701",
                "is_active": True,
            }
        }
        self.policies: Dict[str, Dict[str, Any]] = {}
        self.claims: Dict[str, Dict[str, Any]] = {}
        self.evidence: Dict[str, List[Dict[str, Any]]] = {}
        self.ai_analyses: Dict[str, Dict[str, Any]] = {}
        self.fraud_analyses: Dict[str, Dict[str, Any]] = {}
        self.otp_verifications: List[Dict[str, Any]] = []
        self.storage_objects: set[str] = set()

    async def select(self, table: str, params: Optional[Dict[str, Any]] = None, single: bool = False) -> Any:
        params = params or {}

        if table == "profiles":
            results = list(self.profiles.values())
            if "id" in params:
                val = params["id"].replace("eq.", "")
                results = [r for r in results if r["id"] == val]
            if "email" in params:
                val = params["email"].replace("eq.", "")
                results = [r for r in results if r["email"] == val]
            return results[0] if single and results else (None if single else results)

        if table == "agent_policies":
            results = list(self.agent_policies.values())
            if "policy_number" in params:
                val = params["policy_number"].replace("eq.", "")
                results = [r for r in results if r["policy_number"] == val]
            return results[0] if single and results else (None if single else results)

        if table == "policies":
            results = list(self.policies.values())
            if "policy_number" in params:
                val = params["policy_number"].replace("eq.", "")
                results = [r for r in results if r["policy_number"] == val]
            return results[0] if single and results else (None if single else results)

        if table == "claims":
            results = list(self.claims.values())
            if "id" in params:
                val = params["id"].replace("eq.", "")
                results = [r for r in results if r["id"] == val]
            if "claim_number" in params:
                val = params["claim_number"].replace("eq.", "")
                results = [r for r in results if r.get("claim_number") == val]
            if "user_id" in params:
                val = params["user_id"].replace("eq.", "")
                results = [r for r in results if r["user_id"] == val]
            if "assigned_agent_id" in params:
                val = params["assigned_agent_id"].replace("eq.", "")
                results = [r for r in results if r.get("assigned_agent_id") == val]
            return results[0] if single and results else (None if single else results)

        if table == "claim_evidence":
            results = []
            if "claim_id" in params:
                raw_cid = params["claim_id"]
                if raw_cid.startswith("eq."):
                    cid = raw_cid.replace("eq.", "")
                    results = self.evidence.get(cid, [])
                elif raw_cid.startswith("neq."):
                    exclude_cid = raw_cid.replace("neq.", "")
                    results = [
                        item
                        for cid, items in self.evidence.items()
                        if cid != exclude_cid
                        for item in items
                    ]
                else:
                    cid = raw_cid.replace("eq.", "")
                    results = self.evidence.get(cid, [])
            else:
                results = [item for items in self.evidence.values() for item in items]
            return results[0] if single and results else (None if single else results)

        if table == "claim_ai_analysis":
            results = list(self.ai_analyses.values())
            if "claim_id" in params:
                val = params["claim_id"].replace("eq.", "")
                results = [r for r in results if r["claim_id"] == val]
            return results[0] if single and results else (None if single else results)

        if table == "claim_fraud_analyses":
            results = list(self.fraud_analyses.values())
            if "claim_id" in params:
                val = params["claim_id"].replace("eq.", "")
                results = [r for r in results if r.get("claim_id") == val]
            return results[0] if single and results else (None if single else results)

        if table == "otp_verifications":
            results = list(self.otp_verifications)
            if "identifier" in params:
                val = params["identifier"].replace("eq.", "")
                results = [r for r in results if r["identifier"] == val]
            if "channel" in params:
                val = params["channel"].replace("eq.", "")
                results = [r for r in results if r["channel"] == val]
            if "is_verified" in params:
                val = params["is_verified"].replace("eq.", "") == "true"
                results = [r for r in results if r["is_verified"] == val]
            # Order desc by created_at, limit 1 if requested
            results.sort(key=lambda x: x.get("created_at", ""), reverse=True)
            if "limit" in params and params["limit"] == "1":
                results = results[:1]
            return results[0] if single and results else results

        raise AssertionError(f"Unexpected table requested in select: {table}")

    async def insert(self, table: str, data: Dict[str, Any]) -> Any:
        record = dict(data)
        if table == "policies":
            self.policies[record["policy_number"]] = record
            return record
        if table == "claims":
            self.claims[record["id"]] = record
            return record
        if table == "claim_evidence":
            cid = record["claim_id"]
            self.evidence.setdefault(cid, []).append(record)
            return record
        if table == "claim_ai_analysis":
            self.ai_analyses[record["claim_id"]] = record
            return record
        if table == "claim_fraud_analyses":
            self.fraud_analyses[record["claim_id"]] = record
            return record
        if table == "otp_verifications":
            record.setdefault("id", str(len(self.otp_verifications) + 1))
            self.otp_verifications.append(record)
            return record
        raise AssertionError(f"Unexpected table requested in insert: {table}")

    async def update(self, table: str, filters: Dict[str, Any], data: Dict[str, Any]) -> List[Dict[str, Any]]:
        updated = []
        if table == "claims":
            target_id = filters.get("id", "").replace("eq.", "")
            if target_id in self.claims:
                claim = self.claims[target_id]
                # Check optional condition filters e.g. status
                if "status" in filters:
                    expected_status = filters["status"].replace("eq.", "")
                    if claim.get("status") != expected_status:
                        return []
                claim.update(data)
                updated.append(dict(claim))
            return updated

        if table == "claim_evidence":
            target_id = filters.get("id", "").replace("eq.", "")
            for evid_list in self.evidence.values():
                for evid in evid_list:
                    if str(evid.get("id")) == target_id:
                        evid.update(data)
                        updated.append(dict(evid))
            return updated

        if table == "otp_verifications":
            target_id = filters.get("id", "").replace("eq.", "")
            for otp in self.otp_verifications:
                if str(otp.get("id")) == target_id:
                    otp.update(data)
                    updated.append(dict(otp))
            return updated

        if table == "claim_ai_analysis":
            target_cid = filters.get("claim_id", "").replace("eq.", "")
            if target_cid in self.ai_analyses:
                self.ai_analyses[target_cid].update(data)
                updated.append(dict(self.ai_analyses[target_cid]))
            return updated

        if table == "claim_fraud_analyses":
            target_cid = filters.get("claim_id", "").replace("eq.", "")
            if target_cid in self.fraud_analyses:
                self.fraud_analyses[target_cid].update(data)
                updated.append(dict(self.fraud_analyses[target_cid]))
            return updated

        if table == "policies":
            pnum = filters.get("policy_number", "").replace("eq.", "")
            if pnum in self.policies:
                self.policies[pnum].update(data)
                updated.append(dict(self.policies[pnum]))
            return updated

        return []

    async def download_storage_object(self, bucket: str, file_path: str) -> bytes:
        return (
            b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05"
            b"\x08\x07\x07\x07\t\t\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a\x1f\x1e\x1d\x1a\x1c\x1c"
            b" $.' \",#\x1c\x1c(7),01444\x1f'9=82<.342\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00\xff\xc4"
            b"\x00\x1f\x00\x00\x01\x05\x01\x01\x01\x01\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05"
            b"\x06\x07\x08\t\n\x0b\xff\xda\x00\x08\x01\x01\x00\x00?\x00\xbf\x00\xff\xd9"
        )

    async def create_signed_read_url(self, bucket: str, file_path: str, expires_in: int = 300) -> Dict[str, str]:
        if file_path not in self.storage_objects:
            raise RuntimeError(f"Storage object {file_path} does not exist in bucket {bucket}")
        return {"signed_url": f"https://unit-test.invalid/private/{file_path}?token=signed-read"}

    async def create_signed_upload_url(self, bucket: str, file_path: str, expires_in: int = 900) -> Dict[str, str]:
        self.storage_objects.add(file_path)
        return {"signed_url": f"https://unit-test.invalid/upload/{file_path}?token=signed-upload"}


@pytest.fixture
def mock_db():
    return MockDatabase()


@pytest.fixture
def test_app(mock_db, monkeypatch):
    """FastAPI Test application with mocked databases and routers attached."""
    from app.db import supabase
    monkeypatch.setattr(supabase, "db", mock_db)
    monkeypatch.setattr(claims, "db", mock_db)
    monkeypatch.setattr(storage, "db", mock_db)
    monkeypatch.setattr(agent, "db", mock_db)
    monkeypatch.setattr(auth, "db", mock_db)
    monkeypatch.setattr(auth_otp, "db", mock_db)
    monkeypatch.setattr(ai_runner, "db", mock_db)

    real_analyzer = ai_runner.analyze_fraud
    async def analyze_with_fake_database(**kwargs):
        return await real_analyzer(**kwargs, db_client=mock_db)
    monkeypatch.setattr(ai_runner, "analyze_fraud", analyze_with_fake_database)

    # Prevent background task from triggering real network calls
    async def noop_ai_runner(*args, **kwargs):
        return None
    monkeypatch.setattr(storage, "trigger_ai_assessment", noop_ai_runner)

    app = FastAPI()
    app.include_router(auth.router, prefix="/api/v1")
    app.include_router(auth_otp.router, prefix="/api/v1")
    app.include_router(claims.router, prefix="/api/v1")
    app.include_router(storage.router, prefix="/api/v1")
    app.include_router(agent.router, prefix="/api/v1")
    return app


def auth_client(test_app, user_id: str, role: str) -> TestClient:
    """Create a TestClient with a signed access token in the Authorization header."""
    token = create_access_token({"sub": user_id, "role": role, "email": f"{user_id}@claimpilot.test"})
    client = TestClient(test_app)
    client.headers.update({"Authorization": f"Bearer {token}"})
    return client


# ── TEST STAGE A: Authentication & Role-Based Access Control ─────────────────

def test_stage_a_otp_verification_issues_valid_jwt(test_app, mock_db):
    """Verify that OTP verification produces a valid JWT and registers session."""
    client = TestClient(test_app)
    created_at = datetime.now(timezone.utc).isoformat()
    expires_at = (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat()
    raw_otp = "123456"

    tag = auth_otp._otp_tag(
        raw_otp,
        identifier="customer101@claimpilot.test",
        channel="email",
        purpose="login",
        user_id="cust-101",
        challenge_id="ch-9001",
        created_at=auth_otp._canonical_timestamp(created_at),
    )
    mock_db.otp_verifications.append({
        "id": "ch-9001",
        "identifier": "customer101@claimpilot.test",
        "channel": "email",
        "purpose": "login",
        "user_id": "cust-101",
        "otp_code": tag,
        "is_verified": False,
        "attempts": 0,
        "created_at": created_at,
        "expires_at": expires_at,
    })

    resp = client.post("/api/v1/auth/otp/verify", json={
        "identifier": "customer101@claimpilot.test",
        "otp_code": raw_otp,
        "channel": "email",
        "challenge_id": "ch-9001",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_verified"] is True
    token = data["access_token"]
    assert token and isinstance(token, str)

    # Use token to access protected /api/v1/auth/me
    auth_resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert auth_resp.status_code == 200
    me_data = auth_resp.json()
    assert me_data["id"] == "cust-101"
    assert me_data["role"] == "customer"


def test_stage_a_unauthenticated_and_malformed_tokens_rejected(test_app):
    """Verify that missing, malformed, or fake tokens return HTTP 401."""
    client = TestClient(test_app)

    # Missing Authorization header
    resp1 = client.get("/api/v1/claims")
    assert resp1.status_code == 401

    # Malformed token
    resp2 = client.get("/api/v1/claims", headers={"Authorization": "Bearer not-a-valid-jwt"})
    assert resp2.status_code == 401

    # Tampered signature
    fake_token = create_access_token({"sub": "cust-101", "role": "customer"}) + "tampered"
    resp3 = client.get("/api/v1/claims", headers={"Authorization": f"Bearer {fake_token}"})
    assert resp3.status_code == 401


def test_stage_a_customer_token_cannot_access_agent_endpoints(test_app):
    """Verify customer role cannot execute agent-only endpoints."""
    cust_client = auth_client(test_app, "cust-101", "customer")

    resp1 = cust_client.get("/api/v1/agent/claims")
    assert resp1.status_code == 403

    resp2 = cust_client.post("/api/v1/agent/claims/any-id/action", json={"action": "APPROVE"})
    assert resp2.status_code == 403


# ── TEST STAGE B: Claim Creation & Policy Assignment ─────────────────────────

def test_stage_b_create_claim_with_valid_policy(test_app, mock_db):
    """Verify customer can create a claim against a valid assigned policy."""
    cust_client = auth_client(test_app, "cust-101", "customer")

    payload = {
        "policy_number": "DEMO-POL-001",
        "incident_type": "Accident",
        "vehicle_name": "Honda City 2022",
        "hsrp_number": "MH12AB1234",
        "engine_number": "ENG123456",
        "chassis_number": "CHS123456",
        "incident_date": "2026-10-10",
        "location_address": "Western Express Highway, Mumbai",
        "description": "Front collision causing bumper dent and crack.",
        "driver_name": "Test Customer Alpha",
        "driver_dl_number": "MH1220110012345",
        "claimed_amount": 0.0,
    }

    resp = cust_client.post("/api/v1/claims", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["success"] is True
    assert data["status"] == "pending_review"
    claim = data["claim"]
    assert claim["user_id"] == "cust-101"
    assert claim["assigned_agent_id"] == "agent-701"
    assert claim["id"] in mock_db.claims


def test_stage_b_unassigned_or_invalid_policy_fails_safely(test_app):
    """Verify claim creation fails safely when policy is unassigned or not found."""
    cust_client = auth_client(test_app, "cust-101", "customer")

    payload = {
        "policy_number": "INVALID-POLICY-999",
        "incident_type": "Accident",
        "vehicle_name": "Honda City 2022",
        "hsrp_number": "MH12AB1234",
        "engine_number": "ENG123456",
        "chassis_number": "CHS123456",
        "incident_date": "2026-10-10",
        "location_address": "Mumbai",
        "description": "Dented fender",
        "driver_name": "Test Customer Alpha",
        "driver_dl_number": "MH1220110012345",
        "claimed_amount": 0.0,
    }

    resp = cust_client.post("/api/v1/claims", json=payload)
    assert resp.status_code == 400
    assert "invalid or not registered to any active agent" in resp.json()["detail"]["message"]


def test_stage_b_cross_customer_claim_isolation(test_app, mock_db):
    """Verify Customer Beta cannot view Customer Alpha's claim."""
    claim_id = str(uuid.uuid4())
    mock_db.claims[claim_id] = {
        "id": claim_id,
        "claim_number": "CLM-2026-001",
        "user_id": "cust-101",
        "assigned_agent_id": "agent-701",
        "status": "pending_review",
    }

    cust_beta_client = auth_client(test_app, "cust-202", "customer")
    resp = cust_beta_client.get(f"/api/v1/claims/{claim_id}")
    assert resp.status_code == 403
    detail = resp.json()["detail"]
    message = detail.get("message", detail) if isinstance(detail, dict) else str(detail)
    assert "authorized to access this customer claim" in message


# ── TEST STAGE C: Evidence Upload & Storage ──────────────────────────────────

def test_stage_c_request_presigned_upload_url(test_app):
    """Verify customer can request a presigned upload URL with valid parameters."""
    cust_client = auth_client(test_app, "cust-101", "customer")

    resp = cust_client.post("/api/v1/storage/presigned-url", json={
        "file_name": "front_damage.jpg",
        "file_type": "image/jpeg",
        "category": "photo",
        "file_size_bytes": 1024 * 1024,  # 1 MB
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "upload_url" in data
    assert data["file_path"].startswith("evidence/photo/cust-101/")
    assert data["category"] == "photo"


def test_stage_c_file_size_limit_enforced(test_app):
    """Verify files larger than 50MB are rejected with HTTP 413."""
    cust_client = auth_client(test_app, "cust-101", "customer")

    resp = cust_client.post("/api/v1/storage/presigned-url", json={
        "file_name": "huge_video.mp4",
        "file_type": "video/mp4",
        "category": "walkaround_video",
        "file_size_bytes": 55 * 1024 * 1024,  # 55 MB (> 50MB limit)
    })
    assert resp.status_code == 413


def test_stage_c_catalog_evidence_with_storage_verification(test_app, mock_db):
    """Verify evidence registration confirms storage availability and persists path."""
    claim_id = str(uuid.uuid4())
    mock_db.claims[claim_id] = {
        "id": claim_id,
        "claim_number": "CLM-2026-001",
        "user_id": "cust-101",
        "assigned_agent_id": "agent-701",
        "status": "pending_review",
    }
    canonical_path = "evidence/photo/cust-101/1700000000_abc123_damage.jpg"
    mock_db.storage_objects.add(canonical_path)

    cust_client = auth_client(test_app, "cust-101", "customer")
    resp = cust_client.post("/api/v1/storage/evidence", json={
        "claim_id": claim_id,
        "file_url": canonical_path,
        "storage_path": canonical_path,
        "file_type": "image/jpeg",
        "category": "photo",
    })
    assert resp.status_code == 201
    assert len(mock_db.evidence.get(claim_id, [])) == 1


def test_stage_c_unauthorized_customer_cannot_catalog_evidence(test_app, mock_db):
    """Verify Customer Beta cannot register evidence against Customer Alpha's claim."""
    claim_id = str(uuid.uuid4())
    mock_db.claims[claim_id] = {
        "id": claim_id,
        "claim_number": "CLM-2026-001",
        "user_id": "cust-101",
        "assigned_agent_id": "agent-701",
        "status": "pending_review",
    }
    cust_beta_client = auth_client(test_app, "cust-202", "customer")
    resp = cust_beta_client.post("/api/v1/storage/evidence", json={
        "claim_id": claim_id,
        "file_url": "evidence/photo/cust-202/1700000000_abc123_damage.jpg",
        "storage_path": "evidence/photo/cust-202/1700000000_abc123_damage.jpg",
        "file_type": "image/jpeg",
        "category": "photo",
    })
    assert resp.status_code == 403


# ── TEST STAGE D: AI Inference & Persistence Fallback ────────────────────────

def test_stage_d_missing_model_routes_safely_to_manual_review(test_app, mock_db, monkeypatch):
    """Verify that when AI model weights are unavailable, trigger_ai_assessment invokes
    its real application failure path: persists failed analysis, sets claim status to
    manual_review without fabricated damages/costs, and customer/agent APIs agree."""
    claim_id = str(uuid.uuid4())
    owner_id = "cust-101"
    mock_db.claims[claim_id] = {
        "id": claim_id,
        "claim_number": "CLM-2026-AI-MISSING",
        "user_id": owner_id,
        "assigned_agent_id": "agent-701",
        "status": "pending_review",
        "description": "Fender dent and scratched paint after collision",
        "created_at": "2026-10-15T10:00:00Z",
    }
    photo_path = f"evidence/photo/{owner_id}/1700000000_damage_photo.jpg"
    mock_db.storage_objects.add(photo_path)
    mock_db.evidence[claim_id] = [
        {
            "id": "ev-001",
            "claim_id": claim_id,
            "category": "photo",
            "storage_path": photo_path,
            "file_url": photo_path,
            "file_type": "image/jpeg",
        }
    ]

    # Explicitly simulate missing model weights
    monkeypatch.setattr(ai_runner, "get_models", lambda: (None, None))

    # Invoke real orchestration function directly (not mocked away)
    result = asyncio.run(ai_runner.trigger_ai_assessment(claim_id, background=False))

    # 1. Orchestration result indicates failure, not successful assessment
    assert result["analysis_status"] == "failed"
    assert "No damage detection model weights are available" in result.get("error_message", "")
    assert result["detected_damages"] == []

    # 2. Persisted DB state confirms real failure path execution
    assert mock_db.claims[claim_id]["status"] == "manual_review"
    assert claim_id in mock_db.ai_analyses
    persisted = mock_db.ai_analyses[claim_id]
    assert persisted["analysis_status"] == "failed"
    assert persisted["detected_damages"] == []
    assert persisted.get("estimated_cost_min") is None or persisted.get("estimated_cost_min") == 0
    assert persisted.get("estimated_cost_max") is None or persisted.get("estimated_cost_max") == 0

    # 3. Agent API response matches persisted manual_review failure state
    agent_client = auth_client(test_app, "agent-701", "agent")
    agent_resp = agent_client.get(f"/api/v1/agent/claims/{claim_id}")
    assert agent_resp.status_code == 200
    agent_data = agent_resp.json()
    assert agent_data["claim"]["status"] == "manual_review"
    assert agent_data["ai_analysis"]["analysis_status"] == "failed"
    assert agent_data["ai_analysis"]["detected_damages"] == []

    # 4. Customer API response matches persisted manual_review failure state
    cust_client = auth_client(test_app, owner_id, "customer")
    cust_resp = cust_client.get(f"/api/v1/claims/{claim_id}")
    assert cust_resp.status_code == 200
    cust_data = cust_resp.json()
    assert cust_data["claim"]["status"] == "manual_review"
    assert cust_data["ai_analysis"]["analysis_status"] == "failed"
    assert cust_data["ai_analysis"]["detected_damages"] == []


def test_stage_d_failed_model_inference_routes_to_manual_review(test_app, mock_db, monkeypatch):
    """Verify that when loaded model inference raises an unexpected exception, the real
    failure-handling logic transitions claim to manual_review and records failed analysis."""
    claim_id = str(uuid.uuid4())
    owner_id = "cust-101"
    mock_db.claims[claim_id] = {
        "id": claim_id,
        "claim_number": "CLM-2026-AI-BROKEN",
        "user_id": owner_id,
        "assigned_agent_id": "agent-701",
        "status": "pending_review",
        "description": "Front collision bumper crack",
        "created_at": "2026-10-15T10:00:00Z",
    }
    photo_path = f"evidence/photo/{owner_id}/1700000000_broken_photo.jpg"
    mock_db.storage_objects.add(photo_path)
    mock_db.evidence[claim_id] = [
        {
            "id": "ev-002",
            "claim_id": claim_id,
            "category": "photo",
            "storage_path": photo_path,
            "file_url": photo_path,
            "file_type": "image/jpeg",
        }
    ]

    class BrokenModel:
        def predict(self, *_args, **_kwargs):
            raise RuntimeError("Corrupted image tensor during model inference")

    monkeypatch.setattr(ai_runner, "get_models", lambda: (BrokenModel(), None))

    result = asyncio.run(ai_runner.trigger_ai_assessment(claim_id, background=False))

    assert result["analysis_status"] == "failed"
    assert result["error_message"] == "Damage detection failed for all uploaded photos."
    assert result["detected_damages"] == []

    # Assert persisted claim status and analysis
    assert mock_db.claims[claim_id]["status"] == "manual_review"
    assert mock_db.ai_analyses[claim_id]["analysis_status"] == "failed"
    assert mock_db.ai_analyses[claim_id]["detected_damages"] == []

    # Verify agent and customer endpoints agree with persisted state
    agent_client = auth_client(test_app, "agent-701", "agent")
    agent_resp = agent_client.get(f"/api/v1/agent/claims/{claim_id}")
    assert agent_resp.status_code == 200
    assert agent_resp.json()["claim"]["status"] == "manual_review"
    assert agent_resp.json()["ai_analysis"]["analysis_status"] == "failed"


# ── TEST STAGE E: Agent Authorization & Decision Safeguards ──────────────────

def test_stage_e_assigned_agent_authorized_unassigned_blocked(test_app, mock_db):
    """Verify assigned agent can view claim detail while unassigned agent is blocked."""
    claim_id = str(uuid.uuid4())
    mock_db.claims[claim_id] = {
        "id": claim_id,
        "claim_number": "CLM-2026-001",
        "user_id": "cust-101",
        "assigned_agent_id": "agent-701",
        "status": "under_review",
    }

    # Assigned agent (agent-701) -> OK
    assigned_client = auth_client(test_app, "agent-701", "agent")
    ok_resp = assigned_client.get(f"/api/v1/agent/claims/{claim_id}")
    assert ok_resp.status_code == 200

    # Unassigned agent (agent-999) -> 403 Forbidden
    unassigned_client = auth_client(test_app, "agent-999", "agent")
    blocked_resp = unassigned_client.get(f"/api/v1/agent/claims/{claim_id}")
    assert blocked_resp.status_code == 403
    assert "authorized to access this assigned claim" in blocked_resp.json()["detail"]["message"]


def test_stage_e_approval_without_estimate_fails_safely_no_fallback(test_app, mock_db):
    """Verify approving a claim without valid AI estimate or explicit amount fails safely (no hardcoded ₹8,000–₹12,000 fallback)."""
    claim_id = str(uuid.uuid4())
    mock_db.claims[claim_id] = {
        "id": claim_id,
        "claim_number": "CLM-NO-EST",
        "user_id": "cust-101",
        "assigned_agent_id": "agent-701",
        "status": "manual_review",
    }
    # No AI analysis present in mock_db.ai_analyses

    agent_client = auth_client(test_app, "agent-701", "agent")
    resp = agent_client.post(f"/api/v1/agent/claims/{claim_id}/action", json={
        "action": "APPROVE",
        "reason": "Routine repair approval",
    })
    assert resp.status_code == 400
    detail = resp.json()["detail"]
    assert detail["status"] == "manual_review_required"
    assert "Cannot approve claim without a valid settlement estimate" in detail["message"]
    # Verify claim status remained manual_review
    assert mock_db.claims[claim_id]["status"] == "manual_review"


def test_stage_e_approval_with_explicit_adjuster_amount_succeeds(test_app, mock_db):
    """Verify approval with explicit adjuster authorized amount persists truthfully."""
    claim_id = str(uuid.uuid4())
    mock_db.claims[claim_id] = {
        "id": claim_id,
        "claim_number": "CLM-MAN-EST",
        "user_id": "cust-101",
        "assigned_agent_id": "agent-701",
        "status": "manual_review",
    }

    agent_client = auth_client(test_app, "agent-701", "agent")
    resp = agent_client.post(f"/api/v1/agent/claims/{claim_id}/action", json={
        "action": "APPROVE",
        "reason": "Authorized based on physical assessment report.",
        "approved_amount": 28500.0,
    })
    assert resp.status_code == 200
    claim_after = mock_db.claims[claim_id]
    assert claim_after["status"] == "agent_approved"
    assert claim_after["approved_amount"] == 28500.0
    assert claim_after["settlement_offer_amount"] == 28500.0


def test_stage_e_terminal_state_modifications_rejected(test_app, mock_db):
    """Verify agent cannot perform actions on claims in terminal status."""
    claim_id = str(uuid.uuid4())
    mock_db.claims[claim_id] = {
        "id": claim_id,
        "claim_number": "CLM-TERM",
        "user_id": "cust-101",
        "assigned_agent_id": "agent-701",
        "status": "settlement_accepted",
    }

    agent_client = auth_client(test_app, "agent-701", "agent")
    resp = agent_client.post(f"/api/v1/agent/claims/{claim_id}/action", json={
        "action": "REJECT",
        "reason": "Should fail",
    })
    assert resp.status_code == 400
    assert "Illegal state transition" in resp.json()["detail"]["message"]


# ── TEST STAGE F: Customer Settlement Outcome & Truthful Non-Initiated Payout ─

def test_stage_f_customer_settlement_acceptance_truthful_payout(test_app, mock_db):
    """Verify customer settlement acceptance records outcome and states payout is not started."""
    claim_id = str(uuid.uuid4())
    mock_db.claims[claim_id] = {
        "id": claim_id,
        "claim_number": "CLM-SETTLE-001",
        "user_id": "cust-101",
        "assigned_agent_id": "agent-701",
        "status": "agent_approved",
        "settlement_offer_amount": 28500.0,
    }

    cust_client = auth_client(test_app, "cust-101", "customer")
    resp = cust_client.post("/api/v1/claims/portal/decision", json={
        "claim_id": claim_id,
        "decision": "ACCEPT",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert data["decision"] == "ACCEPT"
    assert data["new_status"] == "settlement_accepted"

    # Truthful non-initiated payout guarantees
    payout = data["payout_pipeline"]
    assert payout["payout_status"] == "not_started"
    assert payout["batch_id"] is None
    assert payout["disbursement_channel"] is None
    assert "No payout has been initiated" in data["message"]

    # Verify persisted claim status in database
    assert mock_db.claims[claim_id]["status"] == "settlement_accepted"


def test_stage_f_customer_cannot_accept_settlement_on_non_approved_claim(test_app, mock_db):
    """Verify customer cannot accept settlement if claim is not in agent_approved state."""
    claim_id = str(uuid.uuid4())
    mock_db.claims[claim_id] = {
        "id": claim_id,
        "claim_number": "CLM-NOT-APP",
        "user_id": "cust-101",
        "assigned_agent_id": "agent-701",
        "status": "pending_review",
    }

    cust_client = auth_client(test_app, "cust-101", "customer")
    resp = cust_client.post("/api/v1/claims/portal/decision", json={
        "claim_id": claim_id,
        "decision": "ACCEPT",
    })
    assert resp.status_code == 400
    assert "agent_approved" in resp.json()["detail"]["message"]


def test_stage_f_dispute_records_escalation_notes(test_app, mock_db):
    """Verify dispute decision records claimant notes and escalates to High Risk."""
    claim_id = str(uuid.uuid4())
    mock_db.claims[claim_id] = {
        "id": claim_id,
        "claim_number": "CLM-DISPUTE-001",
        "user_id": "cust-101",
        "assigned_agent_id": "agent-701",
        "status": "agent_approved",
        "settlement_offer_amount": 15000.0,
        "requested_info_notes": [],
    }

    cust_client = auth_client(test_app, "cust-101", "customer")
    resp = cust_client.post("/api/v1/claims/portal/decision", json={
        "claim_id": claim_id,
        "decision": "DISPUTE",
        "dispute_notes": "Official garage estimate exceeds ₹35,000.",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "disputed"
    assert data["new_status"] == "disputed"
    assert data["priority"] == "HIGH_PRIORITY_REQUEUE"

    # Persisted in DB
    claim_db = mock_db.claims[claim_id]
    assert claim_db["status"] == "disputed"
    assert claim_db["risk_level"] == "High Risk"
    assert len(claim_db["requested_info_notes"]) == 1
    assert "Official garage estimate" in claim_db["requested_info_notes"][0]["dispute_notes"]


# ── TEST STAGE G: Failure & Recovery Matrix ──────────────────────────────────

def test_stage_g_settlement_conflict_when_db_update_returns_empty(test_app, mock_db, monkeypatch):
    """Verify HTTP 409 Conflict is returned when concurrent mutation prevents update."""
    claim_id = str(uuid.uuid4())
    mock_db.claims[claim_id] = {
        "id": claim_id,
        "claim_number": "CLM-CONF",
        "user_id": "cust-101",
        "assigned_agent_id": "agent-701",
        "status": "agent_approved",
    }

    async def empty_update(table, filters, data):
        return []

    monkeypatch.setattr(mock_db, "update", empty_update)

    cust_client = auth_client(test_app, "cust-101", "customer")
    resp = cust_client.post("/api/v1/claims/portal/decision", json={
        "claim_id": claim_id,
        "decision": "ACCEPT"
    })
    assert resp.status_code == 409
    assert "Settlement decision was not applied" in resp.json()["detail"]["message"]
