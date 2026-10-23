import asyncio
import importlib.util
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import ModuleType, SimpleNamespace

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.testclient import TestClient
import pytest


BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))
for name, value in {
    "SUPABASE_URL": "https://unit-test.invalid",
    "SUPABASE_ANON_KEY": "dummy-anon-key",
    "SUPABASE_SERVICE_ROLE_KEY": "dummy-service-role-key",
    "JWT_SECRET": "dummy-jwt-signing-secret",
}.items():
    os.environ[name] = value

from app.api.v1 import agent, claims, storage
from app.core.security import get_current_user, create_claim_action_token
from app.schemas.claim import ClaimEvidenceCreate


CLAIM_ID = "4ec5e2a7-8f59-4c76-9114-6c4af849ae1a"


class FakeDatabase:
    def __init__(self):
        self.claim = {
            "id": CLAIM_ID,
            "claim_number": "CLM-2026-12345",
            "user_id": "customer-1",
            "assigned_agent_id": "agent-1",
            "status": "pending_review",
            "requested_info_notes": [],
        }
        self.evidence = []
        self.analysis = {"claim_id": CLAIM_ID, "detected_damages": []}
        self.select_calls = []
        self.inserted = []
        self.signed_read_paths = []
        self.upload_paths = []

    async def select(self, table, params=None, single=False):
        params = params or {}
        self.select_calls.append((table, params.copy()))
        if table == "claims":
            found = params.get("id") == f"eq.{CLAIM_ID}" or params.get("claim_number") == f"eq.{self.claim['claim_number']}"
            return self.claim if found and single else ([self.claim] if found else [])
        if table == "claim_evidence":
            return self.evidence
        if table == "claim_ai_analysis":
            return self.analysis if single else [self.analysis]
        if table == "profiles":
            return {"id": "customer-1", "role": "customer"} if single else [{"id": "customer-1"}]
        if table in ("agent_policies", "policies"):
            return {"policy_number": params.get("policy_number", "").replace("eq.", ""), "agent_id": "agent-1", "assigned_agent_id": "agent-1"} if single else []
        raise AssertionError(f"Unexpected table {table}")

    async def insert(self, table, data):
        self.inserted.append((table, data.copy()))
        return data

    async def update(self, table, filters, data):
        if table == "claims":
            self.claim.update(data)
        return [{"id": CLAIM_ID, **data}]

    async def create_signed_read_url(self, bucket, file_path, expires_in=300):
        self.signed_read_paths.append((bucket, file_path, expires_in))
        return {"signed_url": f"https://unit-test.invalid/private/{file_path}?token=read-only-test-token"}

    async def create_signed_upload_url(self, bucket, file_path, expires_in=900):
        self.upload_paths.append((bucket, file_path, expires_in))
        return {"signed_url": f"https://unit-test.invalid/upload/{file_path}?token=upload-test-token"}


def _client(monkeypatch, user, database):
    monkeypatch.setattr(claims, "db", database)
    monkeypatch.setattr(storage, "db", database)
    monkeypatch.setattr(agent, "db", database)
    app = FastAPI()
    app.include_router(claims.router, prefix="/api/v1")
    app.include_router(storage.router, prefix="/api/v1")
    app.include_router(agent.router, prefix="/api/v1")
    app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app)


def test_customer_cannot_read_another_customers_claim_analysis_or_evidence(monkeypatch):
    database = FakeDatabase()
    client = _client(monkeypatch, {"user_id": "customer-2", "role": "customer"}, database)

    claim_response = client.get(f"/api/v1/claims/{CLAIM_ID}")
    analysis_response = client.get(f"/api/v1/claims/{CLAIM_ID}/ai-analysis")
    evidence_response = client.post(
        "/api/v1/storage/evidence",
        json={
            "claim_id": CLAIM_ID,
            "file_url": "https://unit-test.invalid/storage/v1/object/public/claim-evidence/evidence/dl_front/customer-2/file.jpg",
            "storage_path": "untrusted/path",
            "file_type": "image/jpeg",
            "category": "dl_front",
        },
    )

    assert claim_response.status_code == 403
    assert analysis_response.status_code == 403
    assert evidence_response.status_code == 403
    assert not any(table == "claim_evidence" for table, _ in database.select_calls)
    assert not any(table == "claim_ai_analysis" for table, _ in database.select_calls)


def test_customer_routes_reject_agent_and_agent_routes_reject_customer(monkeypatch):
    database = FakeDatabase()
    agent_as_customer = _client(monkeypatch, {"user_id": "agent-1", "role": "agent"}, database)
    assert agent_as_customer.get(f"/api/v1/claims/{CLAIM_ID}").status_code == 403
    claim_create = agent_as_customer.post(
        "/api/v1/claims",
        json={
            "incident_type": "Accident",
            "vehicle_name": "Honda City",
            "policy_number": "POL-123",
            "hsrp_number": "MH12AB1234",
            "engine_number": "ENG123456",
            "chassis_number": "CHS123456",
            "incident_date": "2025-10-10",
            "location_address": "Test Road, Mumbai",
            "description": "Front collision damage.",
            "driver_name": "Test Policyholder",
            "driver_dl_number": "MH1220180012345",
        },
    )
    assert claim_create.status_code == 403

    customer_as_agent = _client(monkeypatch, {"user_id": "customer-1", "role": "customer"}, database)
    assert customer_as_agent.get("/api/v1/agent/claims").status_code == 403


def test_upload_authorization_returns_private_path_in_legacy_url_field(monkeypatch):
    from app.schemas.claim import PresignedUploadUrlRequest

    database = FakeDatabase()
    client = _client(monkeypatch, {"user_id": "customer-1", "role": "customer"}, database)

    response = client.post(
        "/api/v1/storage/presigned-url",
        json={
            "file_name": "damage photo.png",
            "file_type": "image/png",
            "category": "photo",
            "file_size_bytes": 123,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["file_path"].startswith("evidence/photo/customer-1/")
    assert body["public_url"] == body["file_path"]
    assert "/object/public/" not in body["public_url"]
    assert database.upload_paths[0][1] == body["file_path"]


def test_agent_can_only_read_and_act_on_assigned_claims(monkeypatch):
    database = FakeDatabase()
    client = _client(monkeypatch, {"user_id": "agent-2", "role": "agent"}, database)

    queue = client.get("/api/v1/agent/claims")
    detail = client.get(f"/api/v1/agent/claims/{CLAIM_ID}")
    action = client.post(
        f"/api/v1/agent/claims/{CLAIM_ID}/action",
        json={"action": "REQUEST_INFO", "requested_items": ["damage_photos"]},
    )

    assert queue.status_code == 200
    assert database.select_calls[0][1]["assigned_agent_id"] == "eq.agent-2"
    assert detail.status_code == 403
    assert action.status_code == 403
    assert database.signed_read_paths == []


def test_assigned_agent_receives_only_short_lived_private_evidence_url(monkeypatch):
    database = FakeDatabase()
    database.evidence = [{
        "id": "evidence-1",
        "claim_id": CLAIM_ID,
        "category": "photo",
        "file_url": "evidence/photo/customer-1/photo.png",
        "storage_path": "evidence/photo/customer-1/photo.png",
    }]
    database.analysis["image_url"] = "evidence/photo/customer-1/photo.png"
    client = _client(monkeypatch, {"user_id": "agent-1", "role": "agent"}, database)

    response = client.get(f"/api/v1/agent/claims/{CLAIM_ID}")

    assert response.status_code == 200
    evidence = response.json()["evidence"][0]
    assert evidence["file_url"].startswith("https://unit-test.invalid/private/")
    assert evidence["storage_path"] == ""
    assert response.json()["ai_analysis"]["image_url"] == evidence["file_url"]
    assert database.signed_read_paths == [("claim-evidence", "evidence/photo/customer-1/photo.png", 300)]


def test_customer_from_another_claim_cannot_obtain_evidence_read_url(monkeypatch):
    database = FakeDatabase()
    database.evidence = [{
        "id": "evidence-1",
        "claim_id": CLAIM_ID,
        "category": "photo",
        "file_url": "evidence/photo/customer-1/photo.png",
        "storage_path": "evidence/photo/customer-1/photo.png",
    }]
    client = _client(monkeypatch, {"user_id": "customer-2", "role": "customer"}, database)

    response = client.get(f"/api/v1/claims/{CLAIM_ID}")

    assert response.status_code == 403
    assert database.signed_read_paths == []


def test_customer_analysis_route_returns_authorized_signed_image_url(monkeypatch):
    database = FakeDatabase()
    database.analysis["image_url"] = "evidence/photo/customer-1/photo.png"
    database.evidence = [{
        "id": "evidence-1",
        "claim_id": CLAIM_ID,
        "category": "photo",
        "file_url": "evidence/photo/customer-1/photo.png",
        "storage_path": "evidence/photo/customer-1/photo.png",
    }]
    client = _client(monkeypatch, {"user_id": "customer-1", "role": "customer"}, database)

    response = client.get(f"/api/v1/claims/{CLAIM_ID}/ai-analysis")

    assert response.status_code == 200
    assert response.json()["image_url"].startswith("https://unit-test.invalid/private/")
    assert database.signed_read_paths == [("claim-evidence", "evidence/photo/customer-1/photo.png", 300)]


def test_agent_approval_without_analysis_or_explicit_amount_fails_safely(monkeypatch):
    database = FakeDatabase()
    database.analysis = None
    client = _client(monkeypatch, {"user_id": "agent-1", "role": "agent"}, database)

    response = client.post(
        f"/api/v1/agent/claims/{CLAIM_ID}/action",
        json={"action": "APPROVE"},
    )

    assert response.status_code == 400
    assert "Cannot approve claim without a valid settlement estimate" in response.json()["detail"]["message"]
    assert response.json()["detail"]["status"] == "manual_review_required"


def test_agent_approval_with_missing_or_zero_cost_bounds_fails_safely(monkeypatch):
    database = FakeDatabase()
    database.analysis = {
        "claim_id": CLAIM_ID,
        "estimated_cost_min": 0.0,
        "estimated_cost_max": 0.0,
    }
    client = _client(monkeypatch, {"user_id": "agent-1", "role": "agent"}, database)

    response = client.post(
        f"/api/v1/agent/claims/{CLAIM_ID}/action",
        json={"action": "APPROVE"},
    )

    assert response.status_code == 400
    assert "Cannot approve claim without a valid settlement estimate" in response.json()["detail"]["message"]


def test_agent_approval_succeeds_with_persisted_ai_estimates(monkeypatch):
    database = FakeDatabase()
    database.analysis = {
        "claim_id": CLAIM_ID,
        "estimated_cost_min": 6500.0,
        "estimated_cost_max": 11500.0,
    }
    client = _client(monkeypatch, {"user_id": "agent-1", "role": "agent"}, database)

    response = client.post(
        f"/api/v1/agent/claims/{CLAIM_ID}/action",
        json={"action": "APPROVE"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert body["new_status"] == "agent_approved"
    assert body["estimated_bounds"] == {"min": 6500.0, "max": 11500.0}
    assert database.claim["approved_amount"] == 11500.0


def test_agent_approval_succeeds_with_explicit_approved_amount_even_if_ai_missing(monkeypatch):
    database = FakeDatabase()
    database.analysis = None
    client = _client(monkeypatch, {"user_id": "agent-1", "role": "agent"}, database)

    response = client.post(
        f"/api/v1/agent/claims/{CLAIM_ID}/action",
        json={"action": "APPROVE", "approved_amount": 14500.0, "custom_notes": "Manual adjuster estimate"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert body["new_status"] == "agent_approved"
    assert body["estimated_bounds"] == {"min": 14500.0, "max": 14500.0}
    assert database.claim["approved_amount"] == 14500.0


def test_agent_cannot_submit_customer_settlement_decision(monkeypatch):
    database = FakeDatabase()
    client = _client(monkeypatch, {"user_id": "agent-1", "role": "agent"}, database)

    response = client.post(
        "/api/v1/claims/portal/decision",
        json={"claim_id": CLAIM_ID, "decision": "ACCEPT"},
    )

    assert response.status_code == 403


def test_customer_acceptance_records_decision_without_claiming_payout(monkeypatch):
    database = FakeDatabase()
    database.claim["status"] = "agent_approved"
    database.analysis = {
        "claim_id": CLAIM_ID,
        "estimated_cost_min": 12500.0,
        "estimated_cost_max": 18500.0,
    }
    client = _client(monkeypatch, {"user_id": "customer-1", "role": "customer"}, database)

    response = client.post(
        "/api/v1/claims/portal/decision",
        json={"claim_id": CLAIM_ID, "decision": "ACCEPT"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert body["new_status"] == "settlement_accepted"
    assert body["payout_pipeline"] == {
        "payout_status": "not_started",
        "batch_id": None,
        "disbursement_channel": None,
        "estimated_settlement_hours": None,
    }
    assert "No payout has been initiated" in body["message"]
    assert "amount" not in body


def test_customer_dispute_records_decision_and_escalates_to_agent(monkeypatch):
    database = FakeDatabase()
    database.claim["status"] = "agent_approved"
    client = _client(monkeypatch, {"user_id": "customer-1", "role": "customer"}, database)

    response = client.post(
        "/api/v1/claims/portal/decision",
        json={"claim_id": CLAIM_ID, "decision": "DISPUTE", "dispute_notes": "Estimated cost is insufficient"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "disputed"
    assert body["new_status"] == "disputed"
    assert body["priority"] == "HIGH_PRIORITY_REQUEUE"
    assert "modal_trigger" in body
    assert "disputed" in body["message"].lower()


def test_customer_settlement_database_failure_is_not_reported_as_success(monkeypatch):
    database = FakeDatabase()
    database.claim["status"] = "agent_approved"

    async def fail_update(table, filters, data):
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(database, "update", fail_update)
    client = _client(monkeypatch, {"user_id": "customer-1", "role": "customer"}, database)

    response = client.post(
        "/api/v1/claims/portal/decision",
        json={"claim_id": CLAIM_ID, "decision": "ACCEPT"},
    )

    assert response.status_code == 500
    assert response.json()["detail"]["message"] == "Failed to update claim status to settlement_accepted"
    assert "payout_pipeline" not in response.json()


def test_customer_dispute_database_failure_is_not_reported_as_success(monkeypatch):
    database = FakeDatabase()
    database.claim["status"] = "agent_approved"

    async def fail_update(table, filters, data):
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(database, "update", fail_update)
    client = _client(monkeypatch, {"user_id": "customer-1", "role": "customer"}, database)

    response = client.post(
        "/api/v1/claims/portal/decision",
        json={"claim_id": CLAIM_ID, "decision": "DISPUTE"},
    )

    assert response.status_code == 500
    assert response.json()["detail"]["message"] == "Failed to flag claim as disputed"


def test_customer_settlement_empty_update_is_not_reported_as_success(monkeypatch):
    database = FakeDatabase()
    database.claim["status"] = "agent_approved"

    async def update_no_rows(table, filters, data):
        return []

    monkeypatch.setattr(database, "update", update_no_rows)
    client = _client(monkeypatch, {"user_id": "customer-1", "role": "customer"}, database)

    response = client.post(
        "/api/v1/claims/portal/decision",
        json={"claim_id": CLAIM_ID, "decision": "ACCEPT"},
    )

    assert response.status_code == 409
    assert "not applied" in response.json()["detail"]["message"]
    assert "payout_pipeline" not in response.json()


def test_customer_dispute_empty_update_is_not_reported_as_success(monkeypatch):
    database = FakeDatabase()
    database.claim["status"] = "agent_approved"

    async def update_no_rows(table, filters, data):
        return []

    monkeypatch.setattr(database, "update", update_no_rows)
    client = _client(monkeypatch, {"user_id": "customer-1", "role": "customer"}, database)

    response = client.post(
        "/api/v1/claims/portal/decision",
        json={"claim_id": CLAIM_ID, "decision": "DISPUTE"},
    )

    assert response.status_code == 409
    assert "not applied" in response.json()["detail"]["message"]


def test_customer_settlement_non_list_update_is_not_reported_as_success(monkeypatch):
    database = FakeDatabase()
    database.claim["status"] = "agent_approved"

    async def update_non_list(table, filters, data):
        return {"id": CLAIM_ID, "status": "settlement_accepted"}

    monkeypatch.setattr(database, "update", update_non_list)
    client = _client(monkeypatch, {"user_id": "customer-1", "role": "customer"}, database)

    response = client.post(
        "/api/v1/claims/portal/decision",
        json={"claim_id": CLAIM_ID, "decision": "ACCEPT"},
    )

    assert response.status_code == 409
    assert "not applied" in response.json()["detail"]["message"]


def test_customer_settlement_unexpected_returned_id_is_not_reported_as_success(monkeypatch):
    database = FakeDatabase()
    database.claim["status"] = "agent_approved"

    async def update_wrong_id(table, filters, data):
        return [{"id": "completely-different-id", "status": "settlement_accepted"}]

    monkeypatch.setattr(database, "update", update_wrong_id)
    client = _client(monkeypatch, {"user_id": "customer-1", "role": "customer"}, database)

    response = client.post(
        "/api/v1/claims/portal/decision",
        json={"claim_id": CLAIM_ID, "decision": "ACCEPT"},
    )

    assert response.status_code == 409
    assert "not applied" in response.json()["detail"]["message"]


def test_customer_settlement_unexpected_returned_status_is_not_reported_as_success(monkeypatch):
    database = FakeDatabase()
    database.claim["status"] = "agent_approved"

    async def update_wrong_status(table, filters, data):
        return [{"id": CLAIM_ID, "status": "under_review"}]

    monkeypatch.setattr(database, "update", update_wrong_status)
    client = _client(monkeypatch, {"user_id": "customer-1", "role": "customer"}, database)

    response = client.post(
        "/api/v1/claims/portal/decision",
        json={"claim_id": CLAIM_ID, "decision": "ACCEPT"},
    )

    assert response.status_code == 409
    assert "not applied" in response.json()["detail"]["message"]


def test_customer_cannot_accept_another_customers_settlement(monkeypatch):
    database = FakeDatabase()
    database.claim["status"] = "agent_approved"
    client = _client(monkeypatch, {"user_id": "customer-2", "role": "customer"}, database)

    response = client.post(
        "/api/v1/claims/portal/decision",
        json={"claim_id": CLAIM_ID, "decision": "ACCEPT"},
    )

    assert response.status_code == 403


def test_admin_cannot_submit_customer_settlement_decision(monkeypatch):
    database = FakeDatabase()
    database.claim["status"] = "agent_approved"
    client = _client(monkeypatch, {"user_id": "admin-1", "role": "admin"}, database)

    response = client.post(
        "/api/v1/claims/portal/decision",
        json={"claim_id": CLAIM_ID, "decision": "ACCEPT"},
    )

    assert response.status_code == 403


def test_customer_settlement_rejects_invalid_source_state(monkeypatch):
    database = FakeDatabase()
    database.claim["status"] = "pending_review"
    client = _client(monkeypatch, {"user_id": "customer-1", "role": "customer"}, database)

    response = client.post(
        "/api/v1/claims/portal/decision",
        json={"claim_id": CLAIM_ID, "decision": "ACCEPT"},
    )

    assert response.status_code == 400
    assert "Illegal state transition" in response.json()["detail"]["message"]


def test_customer_duplicate_settlement_decision_is_rejected(monkeypatch):
    database = FakeDatabase()
    database.claim["status"] = "settlement_accepted"
    client = _client(monkeypatch, {"user_id": "customer-1", "role": "customer"}, database)

    response = client.post(
        "/api/v1/claims/portal/decision",
        json={"claim_id": CLAIM_ID, "decision": "ACCEPT"},
    )

    assert response.status_code == 400
    assert "Illegal state transition" in response.json()["detail"]["message"]

    database.claim["status"] = "disputed"
    response_dispute = client.post(
        "/api/v1/claims/portal/decision",
        json={"claim_id": CLAIM_ID, "decision": "DISPUTE"},
    )

    assert response_dispute.status_code == 400
    assert "Illegal state transition" in response_dispute.json()["detail"]["message"]


def test_evidence_catalog_uses_authorized_storage_path_and_real_claim_id(monkeypatch):
    database = FakeDatabase()
    client = _client(monkeypatch, {"user_id": "customer-1", "role": "customer"}, database)
    file_url = (
        "https://unit-test.invalid/storage/v1/object/public/claim-evidence/"
        "evidence/dl_front/customer-1/document.jpg?token=SIGNED-URL-CANARY"
    )

    response = client.post(
        "/api/v1/storage/evidence",
        json={
            "claim_id": "CLM-2026-12345",
            "file_url": file_url,
            "storage_path": "evidence/dl_front/attacker-supplied-path.jpg",
            "file_type": "image/jpeg",
            "category": "dl_front",
        },
    )

    assert response.status_code == 201
    table, evidence = database.inserted[0]
    assert table == "claim_evidence"
    assert evidence["claim_id"] == CLAIM_ID
    assert evidence["storage_path"] == "evidence/dl_front/customer-1/document.jpg"
    assert evidence["file_url"] == "evidence/dl_front/customer-1/document.jpg"
    assert "SIGNED-URL-CANARY" not in evidence["file_url"]


def test_customer_cannot_catalog_another_customers_storage_object(monkeypatch):
    database = FakeDatabase()
    client = _client(monkeypatch, {"user_id": "customer-1", "role": "customer"}, database)
    response = client.post(
        "/api/v1/storage/evidence",
        json={
            "claim_id": CLAIM_ID,
            "file_url": (
                "https://unit-test.invalid/storage/v1/object/public/claim-evidence/"
                "evidence/dl_front/customer-2/private.jpg"
            ),
            "storage_path": "evidence/dl_front/customer-1/forged.jpg",
            "file_type": "image/jpeg",
            "category": "dl_front",
        },
    )
    assert response.status_code == 403
    assert not database.inserted


def test_customer_cannot_catalog_storage_path_with_encoded_traversal(monkeypatch):
    database = FakeDatabase()
    client = _client(monkeypatch, {"user_id": "customer-1", "role": "customer"}, database)
    response = client.post(
        "/api/v1/storage/evidence",
        json={
            "claim_id": CLAIM_ID,
            "file_url": (
                "https://unit-test.invalid/storage/v1/object/public/claim-evidence/"
                "evidence/dl_front/customer-1/%2e%2e/customer-2/private.jpg"
            ),
            "storage_path": "evidence/dl_front/customer-1/private.jpg",
            "file_type": "image/jpeg",
            "category": "dl_front",
        },
    )
    assert response.status_code == 403
    assert not database.inserted


def test_smoke_login_completes_otp_flow_without_printing_code(monkeypatch, capsys):
    spec = importlib.util.spec_from_file_location("claimpilot_smoke_test", BACKEND / "smoke_test.py")
    smoke = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(smoke)
    otp_code = "OTP-CANARY-184205"
    monkeypatch.setattr(smoke, "BASE_URL", "https://api.example.invalid")
    monkeypatch.setattr(smoke, "CUSTOMER_OTP_CODE", otp_code)

    class Response:
        def __init__(self, status_code, data):
            self.status_code = status_code
            self._data = data

        def json(self):
            return self._data

    class Client:
        def __init__(self):
            self.calls = []

        def post(self, url, json):
            self.calls.append((url, json))
            if url.endswith("/auth/login"):
                return Response(200, {"requires_otp": True, "otp_details": {"challenge_id": "challenge-canary"}})
            return Response(200, {"access_token": "access-token-canary", "is_verified": True})

    client = Client()
    token = smoke.login(client, "customer@example.invalid", "password-canary", otp_code, "Customer")
    captured = capsys.readouterr()

    assert token == "access-token-canary"
    assert client.calls[1][0].endswith("/auth/otp/verify")
    assert client.calls[1][1]["otp_code"] == otp_code
    assert client.calls[1][1]["challenge_id"] == "challenge-canary"
    assert otp_code not in captured.out + captured.err


def test_smoke_login_redacts_otp_if_api_error_echoes_it(monkeypatch, capsys):
    spec = importlib.util.spec_from_file_location("claimpilot_smoke_error_test", BACKEND / "smoke_test.py")
    smoke = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(smoke)
    otp_code = "OTP-CANARY-290417"
    monkeypatch.setattr(smoke, "BASE_URL", "https://api.example.invalid")
    monkeypatch.setattr(smoke, "CUSTOMER_OTP_CODE", otp_code)

    class Response:
        def __init__(self, status_code, data):
            self.status_code = status_code
            self._data = data

        def json(self):
            return self._data

    class Client:
        def post(self, url, json):
            if url.endswith("/auth/login"):
                return Response(200, {"requires_otp": True, "otp_details": {"challenge_id": "challenge-canary"}})
            return Response(400, {"detail": f"Rejected code {otp_code}"})

    assert smoke.login(Client(), "customer@example.invalid", "password-canary", otp_code, "Customer") is None
    captured = capsys.readouterr()
    assert otp_code not in captured.out + captured.err


def test_claim_action_token_supports_and_enforces_configured_long_expiry():
    token = create_claim_action_token(CLAIM_ID, "evidence_reupload", expires_minutes=72 * 60)
    assert token
    with pytest.raises(ValueError):
        create_claim_action_token(CLAIM_ID, "evidence_reupload", expires_minutes=72 * 60 + 1)


def _load_otp_module(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.delenv("OTP_DEV_FIXED_CODE", raising=False)
    fake_db = ModuleType("app.db.supabase")
    fake_db.db = None
    fake_db.supabase_admin = None
    fake_email = ModuleType("app.services.email")

    async def dispatch_email(*_args, **_kwargs):
        return None

    fake_email._dispatch_email = dispatch_email
    replacements = {"app.db.supabase": fake_db, "app.services.email": fake_email}
    absent = object()
    originals = {name: sys.modules.get(name, absent) for name in replacements}
    sys.modules.update(replacements)
    try:
        spec = importlib.util.spec_from_file_location(
            "_claimpilot_auth_otp_authorization_test",
            BACKEND / "app" / "api" / "v1" / "auth_otp.py",
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    finally:
        for name, original in originals.items():
            if original is absent:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = original
    return module


def test_production_otp_fails_closed_without_delivery_provider(monkeypatch):
    from app.schemas.claim import OtpChannel, OtpSendRequest

    otp_module = _load_otp_module(monkeypatch)
    otp_module._environment = "production"
    otp_module._dev_fixed_code = None
    monkeypatch.setattr(otp_module.settings, "SENDGRID_API_KEY", None)
    monkeypatch.setattr(otp_module.settings, "SENDGRID_FROM_EMAIL", None)

    class DatabaseMustNotBeTouched:
        async def select(self, *_args, **_kwargs):
            pytest.fail("OTP must fail before writing a challenge without a provider")

    otp_module.db = DatabaseMustNotBeTouched()
    with pytest.raises(HTTPException) as error:
        asyncio.run(
            otp_module.issue_otp(
                OtpSendRequest(identifier="customer@example.invalid", channel=OtpChannel.email),
                BackgroundTasks(),
                purpose="signup",
            )
        )
    assert error.value.status_code == 503
    assert "delivery is not configured" in error.value.detail.lower()


def test_otp_send_rate_limit_and_verification_replay_protection(monkeypatch):
    from app.schemas.claim import OtpChannel, OtpSendRequest, OtpVerifyRequest

    otp_module = _load_otp_module(monkeypatch)

    class RateLimitedDatabase:
        async def select(self, table, **_kwargs):
            if table == "profiles":
                return None
            if table == "otp_verifications":
                return [{"id": str(index)} for index in range(3)]
            raise AssertionError(f"Unexpected table {table}")

        async def insert(self, *_args, **_kwargs):
            pytest.fail("Rate-limited OTP request must not be inserted")

    otp_module.db = RateLimitedDatabase()
    with pytest.raises(HTTPException) as rate_limit_error:
        asyncio.run(
            otp_module.send_otp(
                OtpSendRequest(identifier="customer@example.invalid", channel=OtpChannel.email),
                BackgroundTasks(),
            )
        )
    assert rate_limit_error.value.status_code == 429

    class ReplayDatabase:
        def __init__(self):
            self.otp = {
                "id": "otp-1",
                "identifier": "customer@example.invalid",
                "channel": "email",
                "purpose": "login",
                "user_id": "customer-1",
                "attempts": 0,
                "is_verified": False,
                "created_at": datetime.now(timezone.utc).isoformat(timespec="microseconds"),
                "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat(),
            }
            self.profile = {"id": "customer-1", "role": "customer", "email": "customer@example.invalid"}
            self.otp["otp_code"] = otp_module._otp_tag(
                "184205",
                identifier=self.otp["identifier"],
                channel="email",
                purpose="login",
                user_id=self.profile["id"],
                challenge_id="otp-1",
                created_at=otp_module._canonical_timestamp(self.otp["created_at"]),
            )
            self.update_filters = []

        async def select(self, table, **_kwargs):
            if table == "otp_verifications":
                params = _kwargs.get("params") or {}
                requested_id = params.get("id")
                if requested_id and requested_id != f"eq.{self.otp['id']}":
                    return []
                return [self.otp] if not self.otp["is_verified"] else []
            if table == "profiles":
                return self.profile
            raise AssertionError(f"Unexpected table {table}")

        async def update(self, table, filters, data):
            if table == "otp_verifications":
                self.update_filters.append(filters.copy())
                if self.otp["is_verified"] or filters.get("is_verified") != "eq.false":
                    return []
                if filters.get("attempts") != f"eq.{self.otp['attempts']}":
                    return []
                self.otp.update(data)
                return [self.otp.copy()]
            if table == "profiles":
                self.profile.update(data)
                return [self.profile.copy()]
            raise AssertionError(f"Unexpected table {table}")

    database = ReplayDatabase()
    otp_module.db = database
    otp_module.create_access_token = lambda _payload: "test-access-token"
    first = asyncio.run(
        otp_module.verify_otp(
            OtpVerifyRequest(identifier="customer@example.invalid", otp_code="184205", challenge_id="otp-1")
        )
    )
    assert first.access_token == "test-access-token"
    assert database.update_filters[0]["expires_at"].startswith("gt.")

    wrong_purpose_database = ReplayDatabase()
    wrong_purpose_database.otp["purpose"] = "signup"
    otp_module.db = wrong_purpose_database
    with pytest.raises(HTTPException) as purpose_error:
        asyncio.run(
            otp_module.verify_otp(
                OtpVerifyRequest(identifier="customer@example.invalid", otp_code="184205", challenge_id="otp-1")
            )
        )
    assert purpose_error.value.status_code == 400
    assert not wrong_purpose_database.otp["is_verified"]

    wrong_user_database = ReplayDatabase()
    wrong_user_database.otp["user_id"] = "another-customer"
    otp_module.db = wrong_user_database
    with pytest.raises(HTTPException) as user_binding_error:
        asyncio.run(
            otp_module.verify_otp(
                OtpVerifyRequest(identifier="customer@example.invalid", otp_code="184205", challenge_id="otp-1")
            )
        )
    assert user_binding_error.value.status_code == 400
    assert not wrong_user_database.otp["is_verified"]

    otp_module.db = database
    with pytest.raises(HTTPException) as replay_error:
        asyncio.run(
            otp_module.verify_otp(
                OtpVerifyRequest(identifier="customer@example.invalid", otp_code="184205", challenge_id="otp-1")
            )
        )
    assert replay_error.value.status_code == 400

    wrong_challenge_database = ReplayDatabase()
    otp_module.db = wrong_challenge_database
    with pytest.raises(HTTPException) as challenge_error:
        asyncio.run(otp_module.verify_otp(
            OtpVerifyRequest(
                identifier="customer@example.invalid",
                otp_code="184205",
                challenge_id="another-challenge",
            )
        ))
    assert challenge_error.value.status_code == 400

    expired_database = ReplayDatabase()
    expired_database.otp["expires_at"] = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
    otp_module.db = expired_database
    with pytest.raises(HTTPException) as expiry_error:
        asyncio.run(
            otp_module.verify_otp(
                OtpVerifyRequest(identifier="customer@example.invalid", otp_code="184205", challenge_id="otp-1")
            )
        )
    assert expiry_error.value.status_code == 400
    assert not expired_database.otp["is_verified"]

    locked_database = ReplayDatabase()
    locked_database.otp["attempts"] = otp_module.settings.MAX_OTP_ATTEMPTS
    otp_module.db = locked_database
    with pytest.raises(HTTPException) as attempts_error:
        asyncio.run(
            otp_module.verify_otp(
                OtpVerifyRequest(identifier="customer@example.invalid", otp_code="000000", challenge_id="otp-1")
            )
        )
    assert attempts_error.value.status_code == 429


def test_otp_send_rejects_registered_user_without_password_challenge(monkeypatch):
    from app.schemas.claim import OtpChannel, OtpSendRequest

    otp_module = _load_otp_module(monkeypatch)

    class ExistingUserDatabase:
        async def select(self, table, **_kwargs):
            assert table == "profiles"
            return {"id": "customer-1"}

        async def insert(self, *_args, **_kwargs):
            pytest.fail("Public resend must not create a login challenge")

    otp_module.db = ExistingUserDatabase()
    with pytest.raises(HTTPException) as error:
        asyncio.run(otp_module.send_otp(
            OtpSendRequest(identifier="customer@example.invalid", channel=OtpChannel.email),
            BackgroundTasks(),
        ))
    assert error.value.status_code == 409


def test_otp_resend_rate_limit_is_serialized_within_worker(monkeypatch):
    from app.schemas.claim import OtpChannel, OtpSendRequest

    otp_module = _load_otp_module(monkeypatch)

    class ConcurrentDatabase:
        def __init__(self):
            self.rows = []

        async def select(self, table, params=None, **_kwargs):
            if table == "profiles":
                return None
            assert table == "otp_verifications"
            await asyncio.sleep(0.002)
            return list(self.rows[: int(params.get("limit", "3"))])

        async def insert(self, table, data):
            assert table == "otp_verifications"
            self.rows.append(dict(data, id=str(len(self.rows) + 1)))

    database = ConcurrentDatabase()
    otp_module.db = database

    async def send_many():
        async def send_one():
            try:
                return await otp_module.send_otp(
                    OtpSendRequest(identifier="new@example.invalid", channel=OtpChannel.email),
                    BackgroundTasks(),
                )
            except HTTPException as exc:
                return exc

        return await asyncio.gather(*(send_one() for _ in range(5)))

    results = asyncio.run(send_many())
    assert sum(not isinstance(result, HTTPException) for result in results) == 3
    assert sum(isinstance(result, HTTPException) and result.status_code == 429 for result in results) == 2
    assert len(database.rows) == 3
    assert all(row["otp_code"].isdigit() and len(row["otp_code"]) == 6 for row in database.rows)


def test_signup_otp_creates_customer_only_after_verification_and_profile_failure_mints_no_session(monkeypatch):
    from app.schemas.claim import OtpVerifyRequest, UserMetadata

    otp_module = _load_otp_module(monkeypatch)
    code = "184205"
    created_at = datetime.now(timezone.utc).isoformat(timespec="microseconds")

    class SignupDatabase:
        def __init__(self):
            self.otp = {
                "id": "signup-challenge-1",
                "identifier": "new@example.invalid",
                "channel": "email",
                "purpose": "signup",
                "user_id": None,
                "otp_code": otp_module._otp_tag(
                    code,
                    identifier="new@example.invalid",
                    channel="email",
                    purpose="signup",
                    user_id="",
                    challenge_id="signup-challenge-1",
                    created_at=otp_module._canonical_timestamp(created_at),
                ),
                "attempts": 0,
                "is_verified": False,
                "created_at": created_at,
                "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat(),
            }

        async def select(self, table, **_kwargs):
            if table == "otp_verifications":
                return [self.otp] if not self.otp["is_verified"] else []
            if table == "profiles":
                return None
            raise AssertionError(table)

        async def update(self, table, filters, data):
            assert table == "otp_verifications"
            assert filters["expires_at"].startswith("gt.")
            if self.otp["is_verified"]:
                return []
            self.otp.update(data)
            return [self.otp.copy()]

    class FakeAuthAdmin:
        def __init__(self):
            self.created = []
            self.deleted = []

        def create_user(self, payload):
            self.created.append(payload)
            return SimpleNamespace(user=SimpleNamespace(id="new-customer-id"))

        def delete_user(self, user_id):
            self.deleted.append(user_id)

    class FailingProfileTable:
        def insert(self, profile):
            self.profile = profile
            return self

        def execute(self):
            raise RuntimeError("profile storage unavailable")

    admin = FakeAuthAdmin()
    table = FailingProfileTable()
    otp_module.db = SignupDatabase()
    otp_module.supabase_admin = SimpleNamespace(
        auth=SimpleNamespace(admin=admin),
        table=lambda _name: table,
    )
    issued = []
    otp_module.create_access_token = lambda payload: issued.append(payload) or "should-not-issue"
    request = OtpVerifyRequest(
        identifier="new@example.invalid",
        otp_code=code,
        challenge_id="signup-challenge-1",
        metadata=UserMetadata(
            full_name="New Customer",
            phone_number="+15555550123",
            dob="2000-01-01",
            password="safe-test-password",
        ),
    )

    with pytest.raises(HTTPException) as error:
        asyncio.run(otp_module.verify_otp(request))

    assert error.value.status_code == 503
    assert admin.created[0]["user_metadata"]["role"] == "customer"
    assert table.profile["role"] == "customer"
    assert admin.deleted == ["new-customer-id"]
    assert issued == []
    assert otp_module.db.otp["is_verified"] is True
    assert otp_module.db.otp["otp_code"] != code


def test_verified_signup_forces_customer_role_and_returns_session_only_after_persistence(monkeypatch):
    from app.schemas.claim import OtpVerifyRequest

    otp_module = _load_otp_module(monkeypatch)
    code = "184205"
    created_at = datetime.now(timezone.utc).isoformat(timespec="microseconds")
    challenge_id = "signup-success-challenge"

    class SignupDatabase:
        def __init__(self):
            self.otp = {
                "id": challenge_id,
                "identifier": "new@example.invalid",
                "channel": "email",
                "purpose": "signup",
                "user_id": None,
                "otp_code": otp_module._otp_tag(
                    code,
                    identifier="new@example.invalid",
                    channel="email",
                    purpose="signup",
                    user_id="",
                    challenge_id=challenge_id,
                    created_at=otp_module._canonical_timestamp(created_at),
                ),
                "attempts": 0,
                "is_verified": False,
                "created_at": created_at,
                "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat(),
            }

        async def select(self, table, **_kwargs):
            if table == "otp_verifications":
                return [self.otp] if not self.otp["is_verified"] else []
            if table == "profiles":
                return None
            raise AssertionError(table)

        async def update(self, table, filters, data):
            assert table == "otp_verifications"
            assert filters["id"] == f"eq.{challenge_id}"
            assert filters["expires_at"].startswith("gt.")
            self.otp.update(data)
            return [self.otp.copy()]

    created_auth_payloads = []
    inserted_profiles = []
    issued_tokens = []

    class FakeAuthAdmin:
        def create_user(self, payload):
            created_auth_payloads.append(payload)
            return SimpleNamespace(user=SimpleNamespace(id="new-customer-id"))

    class ProfileTable:
        def insert(self, profile):
            inserted_profiles.append(profile)
            return self

        def execute(self):
            return None

    otp_module.db = SignupDatabase()
    otp_module.supabase_admin = SimpleNamespace(
        auth=SimpleNamespace(admin=FakeAuthAdmin()),
        table=lambda _name: ProfileTable(),
    )
    otp_module.create_access_token = lambda payload: issued_tokens.append(payload) or "verified-session"
    request = OtpVerifyRequest(
        identifier="new@example.invalid",
        otp_code=code,
        challenge_id=challenge_id,
        metadata={
            "full_name": "New Customer",
            "phone_number": "+15555550123",
            "dob": "2000-01-01",
            "password": "safe-test-password",
            "role": "admin",
        },
    )

    result = asyncio.run(otp_module.verify_otp(request))

    assert created_auth_payloads[0]["user_metadata"]["role"] == "customer"
    assert inserted_profiles[0]["role"] == "customer"
    assert issued_tokens[0]["role"] == "customer"
    assert result.user["role"] == "customer"
    assert result.access_token == "verified-session"


def test_otp_insert_failure_does_not_schedule_delivery(monkeypatch):
    from app.schemas.claim import OtpChannel, OtpSendRequest

    otp_module = _load_otp_module(monkeypatch)

    class FailedInsertDatabase:
        async def select(self, table, **_kwargs):
            return None if table == "profiles" else []

        async def insert(self, *_args, **_kwargs):
            raise RuntimeError("database unavailable")

    otp_module.db = FailedInsertDatabase()
    tasks = BackgroundTasks()
    with pytest.raises(HTTPException) as error:
        asyncio.run(otp_module.send_otp(
            OtpSendRequest(identifier="new@example.invalid", channel=OtpChannel.email), tasks
        ))
    assert error.value.status_code == 503
    assert tasks.tasks == []
