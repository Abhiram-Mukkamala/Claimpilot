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

    async def fake_issue_otp(**_kwargs):
        return {"message": "sent"}

    fake_otp_module.issue_otp = fake_issue_otp
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
    auth_module.supabase_public = SimpleNamespace(auth=FakeAuth(), table=lambda _name: FakeTable())
    auth_module.create_access_token = lambda _payload: "fake-access-token"
    caplog.set_level(logging.INFO)

    asyncio.run(auth_module.login_user(
        {"email": "login@example.invalid", "password": canary_password},
        BackgroundTasks(),
        SimpleNamespace(state=SimpleNamespace()),
    ))
    registration = UserRegisterRequest(
        full_name="Canary User",
        email="register@example.invalid",
        phone_number="+15555550123",
        dob=date(2000, 1, 1),
        password=canary_password,
    )
    asyncio.run(auth_module.register_user(
        registration,
        BackgroundTasks(),
        SimpleNamespace(state=SimpleNamespace()),
    ))

    captured = capsys.readouterr()
    output_and_logs = captured.out + captured.err + caplog.text
    assert canary_password not in output_and_logs
    assert "event=auth.login" in caplog.text
    assert "event=auth.register" in caplog.text


def test_registration_ignores_client_supplied_privileged_role():
    from fastapi import BackgroundTasks
    from app.schemas.claim import UserRegisterRequest

    auth_module = _load_auth_module()

    class FakeDatabase:
        async def select(self, *_args, **_kwargs):
            return None

    auth_module.db = FakeDatabase()
    registration = UserRegisterRequest(
        full_name="Test Policyholder",
        email="customer@example.invalid",
        phone_number="+15555550123",
        dob=date(2000, 1, 1),
        password="safe-test-password",
        role="admin",
    )

    result = asyncio.run(auth_module.register_user(
        registration,
        BackgroundTasks(),
        SimpleNamespace(state=SimpleNamespace()),
    ))

    assert result["requires_otp"] is True
    assert "access_token" not in result


def test_login_issues_user_bound_otp_challenge_only_after_password_auth(monkeypatch):
    from fastapi import HTTPException

    auth_module = _load_auth_module()
    issued_challenges = []

    async def issue_otp(**kwargs):
        issued_challenges.append(kwargs)
        return {"challenge_id": "challenge-id"}

    class FakeAuth:
        def sign_in_with_password(self, _payload):
            return SimpleNamespace(user=SimpleNamespace(id="authenticated-user"))

    monkeypatch.setattr(auth_module, "issue_otp", issue_otp)
    auth_module.supabase_public = SimpleNamespace(auth=FakeAuth())
    result = asyncio.run(auth_module.login_user(
        {"email": "customer@example.invalid", "password": "test-password"},
        BackgroundTasks(),
        SimpleNamespace(state=SimpleNamespace()),
    ))

    assert result["requires_otp"] is True
    assert "access_token" not in result
    assert issued_challenges[0]["purpose"] == "login"
    assert issued_challenges[0]["authenticated_user_id"] == "authenticated-user"

    issued_challenges.clear()

    class FailedAuth:
        def sign_in_with_password(self, _payload):
            raise RuntimeError("credentials rejected")

    auth_module.supabase_public = SimpleNamespace(auth=FailedAuth())
    with pytest.raises(HTTPException) as error:
        asyncio.run(auth_module.login_user(
            {"email": "customer@example.invalid", "password": "wrong-password"},
            BackgroundTasks(),
            SimpleNamespace(state=SimpleNamespace()),
        ))
    assert error.value.status_code == 401
    assert issued_challenges == []


@pytest.mark.parametrize("environment", ["development", "test"])
@pytest.mark.parametrize("channel", ["email", "sms"])
def test_nonproduction_otp_uses_fixed_code_without_returning_it(monkeypatch, environment, channel):
    from app.schemas.claim import OtpChannel, OtpSendRequest

    auth_otp = _load_auth_otp_module(monkeypatch, environment, "184205")
    inserted = []

    class FakeDatabase:
        async def select(self, table, *_args, **_kwargs):
            if table == "profiles":
                return {"id": "user-123"}
            if table == "otp_verifications":
                return []
            raise AssertionError(f"Unexpected table {table}")

        async def insert(self, table, data):
            assert table == "otp_verifications"
            inserted.append(data)

    auth_otp.db = FakeDatabase()
    background_tasks = BackgroundTasks()
    result = asyncio.run(auth_otp.issue_otp(
        OtpSendRequest(
            identifier="customer@example.invalid" if channel == "email" else "+15555550123",
            channel=OtpChannel(channel),
        ),
        background_tasks,
        purpose="login",
        authenticated_user_id="user-123",
    ))

    assert result.channel == channel
    assert result.challenge_id
    assert not hasattr(result, "otp_code")
    assert "otp_code" not in result.model_dump()
    assert inserted[0]["otp_code"] != "184205"
    assert inserted[0]["purpose"] == "login"
    assert inserted[0]["user_id"] == "user-123"
    assert len(inserted[0]["otp_code"]) == 6
    assert inserted[0]["otp_code"].isdigit()
    assert background_tasks.tasks == []  # fixed-code mode must not pretend a message was sent


@pytest.mark.parametrize(
    ("environment", "fixed_code"),
    [("production", "184205"), ("development", "invalid")],
)
def test_fixed_otp_configuration_is_rejected_at_module_startup(monkeypatch, environment, fixed_code):
    with pytest.raises(RuntimeError):
        _load_auth_otp_module(monkeypatch, environment, fixed_code)


def _load_otp_with_capture_db(monkeypatch, purpose, profile_exists, authenticated_user_id=""):
    """Load auth_otp.py with a fake DB that captures OTP insert records."""
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.delenv("OTP_DEV_FIXED_CODE", raising=False)

    captured = {}

    class FakeDb:
        async def insert(self, table, data):
            captured["table"] = table
            captured["data"] = data
            return data

        async def select(self, table, params=None, single=False):
            if table == "profiles" and profile_exists:
                return {"id": "user-123", "email": "existing@example.invalid"}
            if table == "otp_verifications":
                return []
            return None

    fake_db_module = ModuleType("app.db.supabase")
    fake_db_module.db = FakeDb()
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
        otp_module = _load_module(
            f"_claimpilot_otp_capture_{purpose}_{profile_exists}",
            BACKEND / "app" / "api" / "v1" / "auth_otp.py",
        )
    finally:
        for key, original in originals.items():
            if original is absent:
                sys.modules.pop(key, None)
            else:
                sys.modules[key] = original
    return otp_module, captured


def test_otp_signup_records_purpose_signup_and_empty_user_id(monkeypatch):
    """Verify signup OTP challenge persists purpose='signup' and user_id=''."""
    otp_module, captured = _load_otp_with_capture_db(monkeypatch, "signup", False)

    from app.schemas.claim import OtpChannel, OtpSendRequest
    background = BackgroundTasks()
    asyncio.run(otp_module.issue_otp(
        OtpSendRequest(identifier="new@example.invalid", channel=OtpChannel.email),
        background,
        purpose="signup",
    ))
    assert captured["data"]["purpose"] == "signup"
    assert captured["data"]["user_id"] is None


def test_otp_login_records_purpose_login_and_user_id(monkeypatch):
    """Verify login OTP challenge persists purpose='login' and bound user_id."""
    otp_module, captured = _load_otp_with_capture_db(monkeypatch, "login", True, "user-123")

    from app.schemas.claim import OtpChannel, OtpSendRequest
    background = BackgroundTasks()
    asyncio.run(otp_module.issue_otp(
        OtpSendRequest(identifier="existing@example.invalid", channel=OtpChannel.email),
        background,
        purpose="login",
        authenticated_user_id="user-123",
    ))
    assert captured["data"]["purpose"] == "login"
    assert captured["data"]["user_id"] == "user-123"


def test_login_uses_supabase_public_not_admin(monkeypatch):
    """Verify password sign-in routes through supabase_public (isolated client),
    not the shared supabase_admin service-role client."""
    auth_module = _load_auth_module()
    calls = {"admin": 0, "public": 0}

    class FakeAuth:
        def sign_in_with_password(self, _payload):
            calls["public"] += 1
            return SimpleNamespace(user=SimpleNamespace(id="user-123"))

    auth_module.db = SimpleNamespace()
    auth_module.supabase_public = SimpleNamespace(auth=FakeAuth(), table=lambda _name: None)
    auth_module.supabase_admin = SimpleNamespace(auth=SimpleNamespace(
        sign_in_with_password=lambda _p: calls.__setitem__("admin", calls["admin"] + 1)
    ))
    auth_module.create_access_token = lambda _payload: "fake-token"

    asyncio.run(auth_module.login_user(
        {"email": "login@example.invalid", "password": "test-password"},
        BackgroundTasks(),
        SimpleNamespace(state=SimpleNamespace()),
    ))
    assert calls["public"] == 1
    assert calls["admin"] == 0
