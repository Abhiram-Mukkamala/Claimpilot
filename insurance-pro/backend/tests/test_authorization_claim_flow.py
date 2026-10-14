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
        raise AssertionError(f"Unexpected table {table}")

    async def insert(self, table, data):
        self.inserted.append((table, data.copy()))
        return data

    async def update(self, _table, _filters, data):
        return [data]


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


def test_agent_cannot_submit_customer_settlement_decision(monkeypatch):
    database = FakeDatabase()
    client = _client(monkeypatch, {"user_id": "agent-1", "role": "agent"}, database)

    response = client.post(
        "/api/v1/claims/portal/decision",
        json={"claim_id": CLAIM_ID, "decision": "ACCEPT"},
    )

    assert response.status_code == 403


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
    assert evidence["file_url"].endswith("document.jpg")
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
                return Response(200, {"requires_otp": True})
            return Response(200, {"access_token": "access-token-canary"})

    client = Client()
    token = smoke.login(client, "customer@example.invalid", "password-canary", otp_code, "Customer")
    captured = capsys.readouterr()

    assert token == "access-token-canary"
    assert client.calls[1][0].endswith("/auth/otp/verify")
    assert client.calls[1][1]["otp_code"] == otp_code
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
                return Response(200, {"requires_otp": True})
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
                "otp_code": "184205",
                "channel": "email",
                "attempts": 0,
                "is_verified": False,
                "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat(),
            }
            self.profile = {"id": "customer-1", "role": "customer", "email": "customer@example.invalid"}

        async def select(self, table, **_kwargs):
            if table == "otp_verifications":
                return [self.otp] if not self.otp["is_verified"] else []
            if table == "profiles":
                return self.profile
            raise AssertionError(f"Unexpected table {table}")

        async def update(self, table, filters, data):
            if table == "otp_verifications":
                if self.otp["is_verified"] or filters.get("is_verified") != "eq.false":
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
            OtpVerifyRequest(identifier="customer@example.invalid", otp_code="184205")
        )
    )
    assert first.access_token == "test-access-token"
    with pytest.raises(HTTPException) as replay_error:
        asyncio.run(
            otp_module.verify_otp(
                OtpVerifyRequest(identifier="customer@example.invalid", otp_code="184205")
            )
        )
    assert replay_error.value.status_code == 400

    expired_database = ReplayDatabase()
    expired_database.otp["expires_at"] = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
    otp_module.db = expired_database
    with pytest.raises(HTTPException) as expiry_error:
        asyncio.run(
            otp_module.verify_otp(
                OtpVerifyRequest(identifier="customer@example.invalid", otp_code="184205")
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
                OtpVerifyRequest(identifier="customer@example.invalid", otp_code="000000")
            )
        )
    assert attempts_error.value.status_code == 429
