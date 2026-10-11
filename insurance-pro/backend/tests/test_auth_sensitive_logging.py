import asyncio
import importlib.util
import logging
import os
import sys
from datetime import date
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest
from fastapi import BackgroundTasks


BACKEND = Path(__file__).resolve().parents[1]
for name, value in {
    "SUPABASE_URL": "https://unit-test.invalid",
    "SUPABASE_ANON_KEY": "dummy-anon-key",
    "SUPABASE_SERVICE_ROLE_KEY": "dummy-service-role-key",
    "JWT_SECRET": "dummy-jwt-signing-secret",
}.items():
    os.environ[name] = value


def _load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_auth_module():
    fake_db_module = ModuleType("app.db.supabase")
    fake_db_module.db = object()
    fake_db_module.supabase_admin = object()
    fake_db_module.supabase_public = object()

    fake_api = ModuleType("app.api")
    fake_api.__path__ = [str(BACKEND / "app" / "api")]
    fake_v1 = ModuleType("app.api.v1")
    fake_v1.__path__ = [str(BACKEND / "app" / "api" / "v1")]
    fake_otp_module = ModuleType("app.api.v1.auth_otp")

    async def fake_send_otp(**_kwargs):
        return {"message": "sent"}

    fake_otp_module.send_otp = fake_send_otp
    replacements = {
        "app.db.supabase": fake_db_module,
        "app.api": fake_api,
        "app.api.v1": fake_v1,
        "app.api.v1.auth_otp": fake_otp_module,
    }
    absent = object()
    originals = {key: sys.modules.get(key, absent) for key in replacements}
    sys.modules.update(replacements)
    try:
        return _load_module(
            "_claimpilot_auth_sensitive_logging_test",
            BACKEND / "app" / "api" / "v1" / "auth.py",
        )
    finally:
        for key, original in originals.items():
            if original is absent:
                sys.modules.pop(key, None)
            else:
                sys.modules[key] = original


def _load_auth_otp_module(monkeypatch, environment, fixed_code):
    monkeypatch.setenv("ENVIRONMENT", environment)
    if fixed_code is None:
        monkeypatch.delenv("OTP_DEV_FIXED_CODE", raising=False)
    else:
        monkeypatch.setenv("OTP_DEV_FIXED_CODE", fixed_code)

    fake_db_module = ModuleType("app.db.supabase")
    fake_db_module.db = object()
    fake_db_module.supabase_admin = object()
    fake_email_module = ModuleType("app.services.email")

    async def fake_dispatch_email(*_args, **_kwargs):
        return None

    fake_email_module._dispatch_email = fake_dispatch_email
    replacements = {
        "app.db.supabase": fake_db_module,
        "app.services.email": fake_email_module,
    }
    absent = object()
    originals = {key: sys.modules.get(key, absent) for key in replacements}
    sys.modules.update(replacements)
    try:
        return _load_module(
            f"_claimpilot_auth_otp_test_{environment}_{fixed_code}",
            BACKEND / "app" / "api" / "v1" / "auth_otp.py",
        )
    finally:
        for key, original in originals.items():
            if original is absent:
                sys.modules.pop(key, None)
            else:
                sys.modules[key] = original


def test_login_and_registration_never_log_canary_password(monkeypatch, capsys, caplog):
    from app.schemas.claim import UserRegisterRequest

    auth_module = _load_auth_module()
    canary_password = "CANARY-password-8a913"
    created_user = SimpleNamespace(id="user-123")

    class FakeAuthAdmin:
        def create_user(self, _payload):
            return SimpleNamespace(user=created_user)

        def delete_user(self, _user_id):
            return None

    class FakeAuth:
        admin = FakeAuthAdmin()

        def sign_in_with_password(self, _payload):
            return SimpleNamespace(user=created_user)

    class FakeTable:
        def insert(self, _payload):
            return self

        def execute(self):
            return None

    class FakeDatabase:
        async def select(self, *_args, **_kwargs):
            return None

    auth_module.db = FakeDatabase()
    auth_module.supabase_admin = SimpleNamespace(auth=FakeAuth(), table=lambda _name: FakeTable())
    auth_module.create_access_token = lambda _payload: "fake-access-token"
    caplog.set_level(logging.INFO)

    asyncio.run(auth_module.login_user(
        {"email": "login@example.invalid", "password": canary_password},
        BackgroundTasks(),
    ))
    registration = UserRegisterRequest(
        full_name="Canary User",
        email="register@example.invalid",
        phone_number="+15555550123",
        dob=date(2000, 1, 1),
        password=canary_password,
    )
    asyncio.run(auth_module.register_user(registration))

    captured = capsys.readouterr()
    output_and_logs = captured.out + captured.err + caplog.text
    assert canary_password not in output_and_logs
    assert "event=auth.login" in caplog.text
    assert "event=auth.register" in caplog.text


def test_development_sms_uses_fixed_code_without_generating_random_code(monkeypatch):
    from app.schemas.claim import OtpChannel, OtpSendRequest

    auth_otp = _load_auth_otp_module(monkeypatch, "development", "184205")
    inserted = []

    class FakeDatabase:
        async def select(self, *_args, **_kwargs):
            return {"id": "user-123"}

        async def insert(self, table, data):
            assert table == "otp_verifications"
            inserted.append(data)

    auth_otp.db = FakeDatabase()
    monkeypatch.setattr(auth_otp.random, "randint", lambda *_args: pytest.fail("random OTP generated"))
    background_tasks = BackgroundTasks()
    result = asyncio.run(auth_otp.send_otp(
        OtpSendRequest(identifier="+15555550123", channel=OtpChannel.sms),
        background_tasks,
    ))

    assert result.channel == "sms"
    assert inserted[0]["otp_code"] == "184205"
    assert background_tasks.tasks[0].args[1] == "184205"


@pytest.mark.parametrize(
    ("environment", "fixed_code"),
    [("production", "184205"), ("development", "invalid")],
)
def test_fixed_otp_configuration_is_rejected_at_module_startup(monkeypatch, environment, fixed_code):
    with pytest.raises(RuntimeError):
        _load_auth_otp_module(monkeypatch, environment, fixed_code)
