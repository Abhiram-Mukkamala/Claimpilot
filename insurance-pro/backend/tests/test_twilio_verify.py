import asyncio
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from fastapi import BackgroundTasks, HTTPException

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

from app.api.v1 import auth, auth_otp
from app.core.config import settings
from app.schemas.claim import OtpChannel, OtpSendRequest, OtpVerifyRequest, UserMetadata


class FakeTwilioDb:
    def __init__(self, existing_profile=None):
        self.existing_profile = existing_profile
        self.verifications = []
        self.updates = []

    async def select(self, table, params=None, single=False):
        if table == "profiles":
            return self.existing_profile
        if table == "otp_verifications":
            if params and "order" in params:
                matching = [v for v in self.verifications if not v.get("is_verified")]
                return matching[:1] if matching else []
            return []
        return None

    async def insert(self, table, data):
        if table == "otp_verifications":
            self.verifications.append(dict(data))
            return data
        return data

    async def update(self, table, filters=None, data=None):
        if table == "otp_verifications":
            self.updates.append({"filters": filters, "data": data})
            for v in self.verifications:
                v.update(data)
            return [data]
        return [data]


@pytest.fixture(autouse=True)
def configure_twilio_env(monkeypatch):
    monkeypatch.setattr(settings, "TWILIO_ACCOUNT_SID", "ACtest1234567890")
    monkeypatch.setattr(settings, "TWILIO_AUTH_TOKEN", "authtesttoken123")
    monkeypatch.setattr(settings, "TWILIO_VERIFY_SERVICE_SID", "VAtestverifyservice123")
    monkeypatch.setattr(auth_otp, "_dev_fixed_code", None)
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setattr(auth_otp, "_environment", "production")


def test_twilio_verify_configured_check():
    """Verify that _otp_delivery_configured and _is_twilio_verify_active recognize Twilio Verify settings."""
    assert auth_otp._otp_delivery_configured(OtpChannel.sms) is True
    assert auth_otp._is_twilio_verify_active(OtpChannel.sms) is True
    assert auth_otp._is_twilio_verify_active(OtpChannel.email) is False


def test_e164_phone_formatting():
    """Verify phone formatting produces standard E.164 strings."""
    assert auth_otp._format_e164_phone("+14155552671") == "+14155552671"
    assert auth_otp._format_e164_phone("9876543210") == "+919876543210"
    assert auth_otp._format_e164_phone("+919876543210") == "+919876543210"
    assert auth_otp._format_e164_phone("14155552671") == "+14155552671"


@pytest.mark.asyncio
async def test_twilio_verify_sending_success(monkeypatch):
    """Test successful OTP dispatch via Twilio Verify Verifications API."""
    db = FakeTwilioDb()
    monkeypatch.setattr(auth_otp, "db", db)

    mock_resp = httpx.Response(
        201,
        json={"sid": "VE123456", "status": "pending", "to": "+919876543210", "channel": "sms"},
        request=httpx.Request("POST", "https://verify.twilio.com/v2/Services/VAtest/Verifications"),
    )

    recorded_requests = []

    async def mock_post(client_self, url, **kwargs):
        recorded_requests.append((str(url), kwargs))
        return mock_resp

    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)

    payload = OtpSendRequest(identifier="9876543210", channel=OtpChannel.sms)
    background = BackgroundTasks()

    resp = await auth_otp.issue_otp(payload, background, purpose="signup")

    assert resp.channel == "sms"
    assert resp.identifier == "9876543210"
    assert resp.challenge_id is not None
    assert len(recorded_requests) == 1
    assert "Verifications" in recorded_requests[0][0]
    assert recorded_requests[0][1]["data"]["To"] == "+919876543210"
    assert recorded_requests[0][1]["data"]["Channel"] == "sms"

    # Verify challenge saved with 'VERIFY' token satisfying VARCHAR(6) constraint
    assert len(db.verifications) == 1
    assert db.verifications[0]["otp_code"] == "VERIFY"
    assert db.verifications[0]["channel"] == "sms"


@pytest.mark.asyncio
async def test_twilio_verify_sending_invalid_phone_error(monkeypatch):
    """Test provider rejection on invalid phone number raises HTTP 400."""
    db = FakeTwilioDb()
    monkeypatch.setattr(auth_otp, "db", db)

    mock_resp = httpx.Response(
        400,
        json={"code": 60200, "message": "Invalid parameter: To"},
        request=httpx.Request("POST", "https://verify.twilio.com/v2/Services/VAtest/Verifications"),
    )

    async def mock_post(client_self, url, **kwargs):
        return mock_resp

    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)

    payload = OtpSendRequest(identifier="invalid-number", channel=OtpChannel.sms)
    background = BackgroundTasks()

    with pytest.raises(HTTPException) as exc_info:
        await auth_otp.issue_otp(payload, background, purpose="signup")

    assert exc_info.value.status_code == 400
    assert "Invalid phone number format" in exc_info.value.detail


@pytest.mark.asyncio
async def test_twilio_verify_sending_provider_error(monkeypatch):
    """Test Twilio provider 500 error on sending raises HTTP 503."""
    db = FakeTwilioDb()
    monkeypatch.setattr(auth_otp, "db", db)

    mock_resp = httpx.Response(
        500,
        text="Internal Server Error",
        request=httpx.Request("POST", "https://verify.twilio.com/v2/Services/VAtest/Verifications"),
    )

    async def mock_post(client_self, url, **kwargs):
        return mock_resp

    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)

    payload = OtpSendRequest(identifier="9876543210", channel=OtpChannel.sms)
    background = BackgroundTasks()

    with pytest.raises(HTTPException) as exc_info:
        await auth_otp.issue_otp(payload, background, purpose="signup")

    assert exc_info.value.status_code == 503
    assert "SMS delivery provider error" in exc_info.value.detail


@pytest.mark.asyncio
async def test_twilio_verify_approved_verification(monkeypatch):
    """Test verification check approved by Twilio establishes session successfully."""
    now = datetime.now(timezone.utc)
    challenge_id = "test-challenge-uuid-1"
    db = FakeTwilioDb()
    db.verifications.append({
        "id": challenge_id,
        "identifier": "9876543210",
        "otp_code": "VERIFY",
        "channel": "sms",
        "purpose": "signup",
        "user_id": None,
        "attempts": 0,
        "is_verified": False,
        "expires_at": (now + timedelta(minutes=10)).isoformat(),
        "created_at": now.isoformat(),
    })
    monkeypatch.setattr(auth_otp, "db", db)

    # Mock Twilio check returning approved
    mock_resp = httpx.Response(
        200,
        json={"sid": "VE123", "status": "approved", "valid": True},
        headers={"content-type": "application/json"},
        request=httpx.Request("POST", "https://verify.twilio.com/v2/Services/VAtest/VerificationCheck"),
    )

    async def mock_post(client_self, url, **kwargs):
        return mock_resp

    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)

    # Mock supabase_admin auth creation and table insert
    created_user = SimpleNamespace(id="new-customer-uuid")
    monkeypatch.setattr(
        auth_otp.supabase_admin.auth.admin,
        "create_user",
        lambda _params: SimpleNamespace(user=created_user),
    )

    table_mock = SimpleNamespace(
        upsert=lambda _data: SimpleNamespace(execute=lambda: None),
        insert=lambda _data: SimpleNamespace(execute=lambda: None),
    )
    monkeypatch.setattr(auth_otp.supabase_admin, "table", lambda _name: table_mock)

    payload = OtpVerifyRequest(
        identifier="9876543210",
        otp_code="123456",
        channel=OtpChannel.sms,
        challenge_id=challenge_id,
        metadata=UserMetadata(
            full_name="Twilio Verified Customer",
            phone_number="9876543210",
            dob="1995-05-15",
            password="secure-password-123",
        ),
    )

    resp = await auth_otp.verify_otp(payload)

    assert resp.is_verified is True
    assert resp.access_token is not None
    assert resp.token_type == "bearer"
    assert resp.user["phone_number"] == "9876543210"
    assert resp.user["is_phone_verified"] is True
    assert any(u["data"].get("is_verified") is True for u in db.updates)


@pytest.mark.asyncio
async def test_twilio_verify_rejected_code(monkeypatch):
    """Test wrong code rejected by Twilio increments attempts and returns HTTP 400."""
    now = datetime.now(timezone.utc)
    challenge_id = "test-challenge-uuid-2"
    db = FakeTwilioDb()
    db.verifications.append({
        "id": challenge_id,
        "identifier": "9876543210",
        "otp_code": "VERIFY",
        "channel": "sms",
        "purpose": "signup",
        "user_id": None,
        "attempts": 0,
        "is_verified": False,
        "expires_at": (now + timedelta(minutes=10)).isoformat(),
        "created_at": now.isoformat(),
    })
    monkeypatch.setattr(auth_otp, "db", db)

    mock_resp = httpx.Response(
        200,
        json={"sid": "VE123", "status": "pending", "valid": False},
        headers={"content-type": "application/json"},
        request=httpx.Request("POST", "https://verify.twilio.com/v2/Services/VAtest/VerificationCheck"),
    )

    async def mock_post(client_self, url, **kwargs):
        return mock_resp

    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)

    payload = OtpVerifyRequest(
        identifier="9876543210",
        otp_code="000000",
        channel=OtpChannel.sms,
        challenge_id=challenge_id,
        metadata=UserMetadata(
            full_name="Twilio Customer",
            phone_number="9876543210",
            dob="1995-05-15",
            password="secure-password-123",
        ),
    )

    with pytest.raises(HTTPException) as exc_info:
        await auth_otp.verify_otp(payload)

    assert exc_info.value.status_code == 400
    assert "Invalid verification code" in exc_info.value.detail
    assert any(u["data"].get("attempts") == 1 for u in db.updates)


@pytest.mark.asyncio
async def test_twilio_verify_expired_code(monkeypatch):
    """Test expired code (Twilio 404 resource not found) returns HTTP 400 expired message."""
    now = datetime.now(timezone.utc)
    challenge_id = "test-challenge-uuid-3"
    db = FakeTwilioDb()
    db.verifications.append({
        "id": challenge_id,
        "identifier": "9876543210",
        "otp_code": "VERIFY",
        "channel": "sms",
        "purpose": "signup",
        "user_id": None,
        "attempts": 0,
        "is_verified": False,
        "expires_at": (now + timedelta(minutes=10)).isoformat(),
        "created_at": now.isoformat(),
    })
    monkeypatch.setattr(auth_otp, "db", db)

    mock_resp = httpx.Response(
        404,
        json={"code": 20404, "message": "The requested resource was not found"},
        headers={"content-type": "application/json"},
        request=httpx.Request("POST", "https://verify.twilio.com/v2/Services/VAtest/VerificationCheck"),
    )

    async def mock_post(client_self, url, **kwargs):
        return mock_resp

    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)

    payload = OtpVerifyRequest(
        identifier="9876543210",
        otp_code="123456",
        channel=OtpChannel.sms,
        challenge_id=challenge_id,
        metadata=UserMetadata(
            full_name="Twilio Customer",
            phone_number="9876543210",
            dob="1995-05-15",
            password="secure-password-123",
        ),
    )

    with pytest.raises(HTTPException) as exc_info:
        await auth_otp.verify_otp(payload)

    assert exc_info.value.status_code == 400
    assert "Verification code has expired" in exc_info.value.detail


@pytest.mark.asyncio
async def test_twilio_verify_provider_check_error(monkeypatch):
    """Test provider error during verification check raises HTTP 503."""
    now = datetime.now(timezone.utc)
    challenge_id = "test-challenge-uuid-4"
    db = FakeTwilioDb()
    db.verifications.append({
        "id": challenge_id,
        "identifier": "9876543210",
        "otp_code": "VERIFY",
        "channel": "sms",
        "purpose": "signup",
        "user_id": None,
        "attempts": 0,
        "is_verified": False,
        "expires_at": (now + timedelta(minutes=10)).isoformat(),
        "created_at": now.isoformat(),
    })
    monkeypatch.setattr(auth_otp, "db", db)

    mock_resp = httpx.Response(
        500,
        text="Internal Server Error",
        request=httpx.Request("POST", "https://verify.twilio.com/v2/Services/VAtest/VerificationCheck"),
    )

    async def mock_post(client_self, url, **kwargs):
        return mock_resp

    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)

    payload = OtpVerifyRequest(
        identifier="9876543210",
        otp_code="123456",
        channel=OtpChannel.sms,
        challenge_id=challenge_id,
        metadata=UserMetadata(
            full_name="Twilio Customer",
            phone_number="9876543210",
            dob="1995-05-15",
            password="secure-password-123",
        ),
    )

    with pytest.raises(HTTPException) as exc_info:
        await auth_otp.verify_otp(payload)

    assert exc_info.value.status_code == 503
    assert "SMS verification provider unavailable" in exc_info.value.detail
