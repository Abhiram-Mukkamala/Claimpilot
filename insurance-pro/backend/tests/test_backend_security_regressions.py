import asyncio
import importlib
import importlib.util
import logging
import os
import sys
from datetime import date
from pathlib import Path
from types import ModuleType, SimpleNamespace

from fastapi import FastAPI, HTTPException
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

from app.core.config import Settings, settings
from app.schemas.claim import ClaimCreate


def _load_main_module():
    """Reload the real FastAPI application and its configured routers."""
    return importlib.reload(importlib.import_module("app.main"))


def _load_claim_routes():
    """Load claims.py with inert database/auth dependencies for a direct route test."""
    fake_database = ModuleType("app.db.supabase")
    fake_database.db = None
    fake_security = ModuleType("app.core.security")
    fake_security.get_current_user = lambda: None
    replacements = {
        "app.db.supabase": fake_database,
        "app.core.security": fake_security,
    }
    absent = object()
    originals = {name: sys.modules.get(name, absent) for name in replacements}
    sys.modules.update(replacements)
    try:
        module_name = "_claimpilot_claim_routes_security_regressions"
        spec = importlib.util.spec_from_file_location(
            module_name,
            BACKEND / "app" / "api" / "v1" / "claims.py",
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


def test_allowed_origins_are_read_from_environment(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://unit-test.invalid")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "dummy-anon-key")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "dummy-service-role-key")
    monkeypatch.setenv("JWT_SECRET", "dummy-jwt-signing-secret")
    monkeypatch.setenv(
        "ALLOWED_ORIGINS",
        "https://approved.example, http://localhost:5173, *",
    )

    configured = Settings(_env_file=None)

    assert configured.allowed_origin_list == [
        "https://approved.example",
        "http://localhost:5173",
    ]


def test_default_allowlist_contains_only_local_frontend(monkeypatch):
    monkeypatch.delenv("ALLOWED_ORIGINS", raising=False)

    configured = Settings(_env_file=None)

    assert configured.allowed_origin_list == ["http://localhost:5173"]


def test_cors_allows_configured_origin_and_rejects_unapproved_origin(monkeypatch):
    monkeypatch.setattr(
        settings,
        "ALLOWED_ORIGINS",
        "https://approved.example,http://localhost:5173",
    )
    main_module = _load_main_module()
    client = TestClient(main_module.app)

    allowed = client.options(
        "/health",
        headers={
            "Origin": "https://approved.example",
            "Access-Control-Request-Method": "GET",
        },
    )
    disallowed = client.options(
        "/health",
        headers={
            "Origin": "https://unapproved.example",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert allowed.status_code == 200
    assert allowed.headers["access-control-allow-origin"] == "https://approved.example"
    assert disallowed.status_code == 400
    assert "access-control-allow-origin" not in disallowed.headers


def test_unhandled_exception_response_is_sanitized_and_correlatable(caplog):
    main_module = _load_main_module()
    test_app = FastAPI()
    test_app.add_exception_handler(Exception, main_module.generic_exception_handler)
    sensitive_detail = "INTERNAL-DETAIL-CANARY"

    @test_app.get("/raise-error")
    async def raise_error():
        raise RuntimeError(sensitive_detail)

    with caplog.at_level(logging.ERROR, logger="claimpilot.api"):
        response = TestClient(test_app, raise_server_exceptions=False).get("/raise-error")

    assert response.status_code == 500
    body = response.json()
    assert set(body) == {"success", "status_code", "detail"}
    assert set(body["detail"]) == {"message", "error"}
    assert body["detail"]["message"] == "An unexpected internal server error occurred."
    assert body["detail"]["error"].startswith("Request ID: ")
    request_id = body["detail"]["error"].removeprefix("Request ID: ")
    assert len(request_id) == 32
    assert sensitive_detail not in response.text
    assert "error_type=RuntimeError" in caplog.text
    assert sensitive_detail not in caplog.text
    assert request_id in caplog.text


def test_deprecated_cors_origins_emits_one_startup_warning(monkeypatch, caplog):
    monkeypatch.setattr(settings, "ALLOWED_ORIGINS", "https://approved.example")
    monkeypatch.setenv("CORS_ORIGINS", "https://ignored.example")
    main_module = _load_main_module()

    with caplog.at_level(logging.WARNING, logger="claimpilot.api"):
        asyncio.run(main_module.warn_deprecated_cors_origins())

    warning_lines = [line for line in caplog.text.splitlines() if "event=config.deprecated_setting" in line]
    assert len(warning_lines) == 1
    assert "setting=CORS_ORIGINS" in warning_lines[0]
    assert "replacement=ALLOWED_ORIGINS" in warning_lines[0]
    assert "ignored.example" not in warning_lines[0]
    response = TestClient(main_module.app).options(
        "/health",
        headers={
            "Origin": "https://ignored.example",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert "access-control-allow-origin" not in response.headers


def test_claim_route_logs_events_without_customer_or_storage_secrets(caplog, capsys):
    claim_routes = _load_claim_routes()

    class FakeDatabase:
        async def select(self, table, **_kwargs):
            if table == "agent_policies":
                return {"agent_id": "AGENT-CANARY-91"}
            if table == "profiles":
                return {"full_name": "PROFILE-CUSTOMER-CANARY"}
            if table == "policies":
                return None
            raise AssertionError(f"Unexpected table {table}")

        async def insert(self, _table, data):
            return data

    claim_routes.db = FakeDatabase()
    payload = ClaimCreate(
        incident_type="Accident",
        vehicle_name="VEHICLE-CANARY-91",
        policy_number="POLICY-CANARY-91",
        hsrp_number="HSRP-CANARY-91",
        engine_number="ENGINE-CANARY-91",
        chassis_number="CHASSIS-CANARY-91",
        incident_date=date.today(),
        location_address="123 TEST CANARY ROAD",
        description="CLAIM-DESCRIPTION-CANARY",
        driver_name="CUSTOMER-CANARY-91",
        driver_dl_number="XX0000000000000",
    )
    user = {
        "user_id": "USER-CANARY-91",
        "role": "customer",
        "access_token": "TOKEN-CANARY-91",
        "signed_storage_url": "https://storage.example.test/object?token=SIGNED-URL-CANARY-91",
    }

    with caplog.at_level(logging.INFO, logger="claimpilot.claims"):
        asyncio.run(
            claim_routes.create_claim(
                payload,
                request=SimpleNamespace(state=SimpleNamespace()),
                user=user,
            )
        )

    captured = capsys.readouterr()
    output_and_logs = caplog.text + captured.out + captured.err
    for sensitive_value in (
        "AGENT-CANARY-91",
        "PROFILE-CUSTOMER-CANARY",
        "POLICY-CANARY-91",
        "VEHICLE-CANARY-91",
        "CLAIM-DESCRIPTION-CANARY",
        "CUSTOMER-CANARY-91",
        "USER-CANARY-91",
        "TOKEN-CANARY-91",
        "SIGNED-URL-CANARY-91",
    ):
        assert sensitive_value not in output_and_logs
    assert "event=claim.create.started" in caplog.text
    assert "event=claim.create.record_inserted" in caplog.text


def test_claim_route_exception_detail_is_sanitized_and_correlated(caplog):
    claim_routes = _load_claim_routes()

    class BrokenDatabase:
        async def select(self, table, **_kwargs):
            if table == "agent_policies":
                return {"agent_id": "agent-id"}
            if table == "profiles":
                return {"id": "agent-id"}
            if table == "policies":
                return None
            raise AssertionError(f"Unexpected table {table}")

        async def insert(self, _table, _data):
            raise RuntimeError("DATABASE-DETAIL-CANARY")

    claim_routes.db = BrokenDatabase()
    payload = ClaimCreate(
        incident_type="Accident",
        vehicle_name="Vehicle",
        policy_number="POLICY-123",
        hsrp_number="HSRP-123",
        engine_number="ENGINE-123",
        chassis_number="CHASSIS-123",
        incident_date=date.today(),
        location_address="Test location",
        description="Test narrative",
        driver_name="Test customer",
        driver_dl_number="XX0000000000000",
    )
    request = SimpleNamespace(state=SimpleNamespace())

    with caplog.at_level(logging.ERROR, logger="claimpilot.claims"):
        with pytest.raises(HTTPException) as exc_info:
                asyncio.run(claim_routes.create_claim(payload, request=request, user={"user_id": "user-id", "role": "customer"}))

    detail = exc_info.value.detail
    assert set(detail) == {"success", "message", "error"}
    assert detail["error"].startswith("Request ID: ")
    request_id = detail["error"].removeprefix("Request ID: ")
    assert request_id in caplog.text
    assert "error_type=RuntimeError" in caplog.text
    assert "DATABASE-DETAIL-CANARY" not in caplog.text
    assert "DATABASE-DETAIL-CANARY" not in str(detail)


def test_email_service_logs_no_recipient_subject_or_message_data(caplog, monkeypatch):
    from app.services.email import _dispatch_email

    monkeypatch.delenv("SENDGRID_API_KEY", raising=False)
    sensitive_values = (
        "customer@example.invalid",
        "CLAIM-CANARY-17",
        "SIGNED-TOKEN-CANARY-29",
        "NARRATIVE-CANARY-43",
    )
    with caplog.at_level(logging.INFO, logger="claimpilot.email"):
        asyncio.run(
            _dispatch_email(
                sensitive_values[0],
                f"Subject {sensitive_values[1]}",
                f"HTML {sensitive_values[2]}",
                f"Text {sensitive_values[3]}",
            )
        )

    for value in sensitive_values:
        assert value not in caplog.text
    assert "event=email.mock_dispatch outcome=completed" in caplog.text
