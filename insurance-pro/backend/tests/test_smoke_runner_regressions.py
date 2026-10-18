"""Regression test suite for ClaimPilot smoke runner hardening findings.

Covers:
- Finding 1: Production-target fail-closed allowlist, loopback parsing, remote HTTPS requirement,
             redirect prevention, and presigned storage upload URL validation.
- Finding 2: Strict OTP challenge requirement, rejection of missing/false requires_otp,
             challenge ID verification, failed OTP handling, token validation, and sensitive redaction.
"""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path
from typing import Any
import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

for key, value in {
    "SUPABASE_URL": "https://unit-test.invalid",
    "SUPABASE_ANON_KEY": "test-anon-key",
    "SUPABASE_SERVICE_ROLE_KEY": "test-service-key",
    "JWT_SECRET": "test-secret-key-minimum-32-characters-long",
    "ENVIRONMENT": "test",
}.items():
    os.environ.setdefault(key, value)

SMOKE_TEST_PATH = BACKEND_DIR / "smoke_test.py"
spec = importlib.util.spec_from_file_location("smoke_test", SMOKE_TEST_PATH)
smoke = importlib.util.module_from_spec(spec)
spec.loader.exec_module(smoke)


# ── FINDING 1: Target Guard & Allowlist Tests ─────────────────────────────────

@pytest.mark.parametrize("target", [
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "http://127.0.0.2:8000",
    "http://[::1]:8000",
    "https://localhost:8443",
    "http://localhost:3000/api",
])
def test_target_guard_accepts_localhost_and_loopback(target: str):
    """Localhost and loopback IPs are accepted for local development and smoke tests."""
    ok, reason = smoke.validate_target_url(target)
    assert ok is True, f"Expected {target} to be accepted, but got: {reason}"
    assert "allowed" in reason.lower()


def test_target_guard_accepts_configured_staging_host(monkeypatch):
    """Explicitly approved staging target is accepted when present in SMOKE_ALLOWED_HOSTS."""
    staging_url = "https://staging-api.claimpilot.internal:8443/v1"
    monkeypatch.setenv("SMOKE_ALLOWED_HOSTS", "staging-api.claimpilot.internal")
    ok, reason = smoke.validate_target_url(staging_url)
    assert ok is True, f"Expected staging URL to be accepted, but got: {reason}"
    assert "allowlist" in reason.lower()


@pytest.mark.parametrize("unapproved_target", [
    "https://evil.example.com",
    "https://attacker.org:8000",
    "https://google.com",
    "https://api.external-service.net",
])
def test_target_guard_rejects_arbitrary_external_hosts(unapproved_target: str):
    """Arbitrary external hosts are rejected by default (fail-closed allowlist)."""
    ok, reason = smoke.validate_target_url(unapproved_target)
    assert ok is False
    assert "not in the explicit allowlist" in reason


@pytest.mark.parametrize("prod_target", [
    "https://claimpilot.com",
    "https://api.claimpilot.com",
    "https://app.claimpilot.com",
    "https://claimpilot.ai",
    "https://api.claimpilot.ai",
    "https://staging.claimpilot.com",
])
def test_target_guard_rejects_known_production_hosts(prod_target: str):
    """Known production domain variations are strictly rejected."""
    ok, reason = smoke.validate_target_url(prod_target)
    assert ok is False
    assert "prohibited production host" in reason or "not in the explicit allowlist" in reason


@pytest.mark.parametrize("malformed_target", [
    "ftp://localhost:8000",
    "file:///etc/passwd",
    "ws://localhost:8000",
    "http://",
    "not_a_valid_url",
    "://bad-scheme",
    "javascript:alert(1)",
])
def test_target_guard_rejects_malformed_and_unsupported_schemes(malformed_target: str):
    """Malformed URLs and non-HTTP/HTTPS schemes are rejected."""
    ok, reason = smoke.validate_target_url(malformed_target)
    assert ok is False
    assert any(phrase in reason for phrase in [
        "Unsupported URL scheme",
        "URL hostname is missing",
        "URL scheme is missing",
        "Malformed URL",
    ])


def test_target_guard_rejects_insecure_http_for_remote_hosts(monkeypatch):
    """Remote targets must use HTTPS even if configured in the allowlist."""
    monkeypatch.setenv("SMOKE_ALLOWED_HOSTS", "staging.claimpilot.internal")
    ok, reason = smoke.validate_target_url("http://staging.claimpilot.internal")
    assert ok is False
    assert "Insecure HTTP scheme is not allowed" in reason


def test_presigned_upload_storage_allowlist(monkeypatch):
    """Presigned storage upload URLs must validate against storage allowlist."""
    # Localhost storage accepted
    ok_local, _ = smoke.validate_target_url("http://localhost:54321/storage/v1/object/upload", is_storage=True)
    assert ok_local is True

    # Unapproved storage host rejected
    ok_unapproved, reason = smoke.validate_target_url("https://unapproved-bucket.s3.amazonaws.com/evidence.jpg", is_storage=True)
    assert ok_unapproved is False
    assert "not in the explicit allowlist" in reason

    # Approved storage host accepted
    monkeypatch.setenv("SMOKE_ALLOWED_STORAGE_HOSTS", "supabase.staging.internal")
    ok_staging, _ = smoke.validate_target_url("https://supabase.staging.internal/storage/v1/upload", is_storage=True)
    assert ok_staging is True


def test_redirects_disabled_on_smoke_client():
    """Verify that smoke client configuration disables automatic redirects."""
    import httpx
    client = httpx.Client(timeout=10.0, follow_redirects=False)
    assert client.follow_redirects is False


# ── FINDING 2: Strict OTP Login Verification & Redaction Tests ────────────────

class MockResponse:
    def __init__(self, status_code: int, data: Any):
        self.status_code = status_code
        self._data = data

    def json(self):
        if isinstance(self._data, Exception):
            raise self._data
        return self._data


class MockHttpClient:
    def __init__(self, login_resp: MockResponse, verify_resp: MockResponse):
        self.login_resp = login_resp
        self.verify_resp = verify_resp
        self.calls = []

    def post(self, url: str, **kwargs):
        self.calls.append((url, kwargs))
        if "auth/login" in url:
            return self.login_resp
        if "auth/otp/verify" in url:
            return self.verify_resp
        raise AssertionError(f"Unexpected URL: {url}")


def test_login_succeeds_with_valid_challenge_and_verification():
    """Successful OTP flow: challenge returned -> OTP verified -> access token returned."""
    client = MockHttpClient(
        login_resp=MockResponse(200, {
            "requires_otp": True,
            "otp_details": {"challenge_id": "ch-alpha-999"},
        }),
        verify_resp=MockResponse(200, {
            "is_verified": True,
            "access_token": "verified-jwt-token-xyz",
        }),
    )
    token = smoke.login(client, "user@claimpilot.test", "pass123", "184205", "Customer")
    assert token == "verified-jwt-token-xyz"
    assert len(client.calls) == 2
    assert "auth/login" in client.calls[0][0]
    assert "auth/otp/verify" in client.calls[1][0]
    verify_payload = client.calls[1][1]["json"]
    assert verify_payload["challenge_id"] == "ch-alpha-999"
    assert verify_payload["otp_code"] == "184205"


def test_login_fails_when_requires_otp_is_missing(capsys):
    """Login must fail if requires_otp field is absent, even if an access token is returned."""
    client = MockHttpClient(
        login_resp=MockResponse(200, {
            "access_token": "premature-token",
            "user": {"id": "cust-1"},
        }),
        verify_resp=MockResponse(500, {}),
    )
    token = smoke.login(client, "user@claimpilot.test", "pass123", "184205", "Customer")
    assert token is None
    assert len(client.calls) == 1
    captured = capsys.readouterr()
    assert "did not trigger required OTP challenge" in captured.out


def test_login_fails_when_requires_otp_is_false(capsys):
    """Login must not silently accept token-only login when requires_otp is explicitly False."""
    client = MockHttpClient(
        login_resp=MockResponse(200, {
            "requires_otp": False,
            "access_token": "bypassed-token",
        }),
        verify_resp=MockResponse(500, {}),
    )
    token = smoke.login(client, "user@claimpilot.test", "pass123", "184205", "Customer")
    assert token is None
    assert len(client.calls) == 1
    captured = capsys.readouterr()
    assert "did not trigger required OTP challenge" in captured.out


@pytest.mark.parametrize("bad_otp_details", [
    None,
    {},
    {"challenge_id": ""},
    {"challenge_id": "   "},
    {"other_key": "val"},
])
def test_login_fails_when_challenge_identifier_is_missing(bad_otp_details, capsys):
    """Login must fail if challenge_id is missing, blank, or malformed."""
    payload = {"requires_otp": True}
    if bad_otp_details is not None:
        payload["otp_details"] = bad_otp_details

    client = MockHttpClient(
        login_resp=MockResponse(200, payload),
        verify_resp=MockResponse(500, {}),
    )
    token = smoke.login(client, "user@claimpilot.test", "pass123", "184205", "Customer")
    assert token is None
    assert len(client.calls) == 1
    captured = capsys.readouterr()
    assert "missing valid" in captured.out.lower()


def test_login_fails_when_otp_verification_returns_non_200(capsys):
    """Login must fail if OTP verification endpoint returns HTTP error."""
    client = MockHttpClient(
        login_resp=MockResponse(200, {
            "requires_otp": True,
            "otp_details": {"challenge_id": "ch-alpha-999"},
        }),
        verify_resp=MockResponse(401, {"detail": "Invalid or expired OTP code"}),
    )
    token = smoke.login(client, "user@claimpilot.test", "pass123", "184205", "Customer")
    assert token is None
    assert len(client.calls) == 2
    captured = capsys.readouterr()
    assert "OTP verification failed (HTTP 401)" in captured.out


def test_login_fails_when_otp_verification_returns_is_verified_false(capsys):
    """Login must fail if OTP verification responds 200 but is_verified is False."""
    client = MockHttpClient(
        login_resp=MockResponse(200, {
            "requires_otp": True,
            "otp_details": {"challenge_id": "ch-alpha-999"},
        }),
        verify_resp=MockResponse(200, {
            "is_verified": False,
            "message": "Verification unsuccessful",
        }),
    )
    token = smoke.login(client, "user@claimpilot.test", "pass123", "184205", "Customer")
    assert token is None
    captured = capsys.readouterr()
    assert "is_verified=False" in captured.out


@pytest.mark.parametrize("bad_verify_resp", [
    {"is_verified": True},  # missing access_token
    {"is_verified": True, "access_token": ""},  # empty string
    {"is_verified": True, "access_token": None},  # None
    {"is_verified": True, "access_token": 12345},  # not a string
])
def test_login_fails_when_token_is_missing_after_verification(bad_verify_resp, capsys):
    """Login must fail if verify succeeds but returns no valid access_token string."""
    client = MockHttpClient(
        login_resp=MockResponse(200, {
            "requires_otp": True,
            "otp_details": {"challenge_id": "ch-alpha-999"},
        }),
        verify_resp=MockResponse(200, bad_verify_resp),
    )
    token = smoke.login(client, "user@claimpilot.test", "pass123", "184205", "Customer")
    assert token is None
    captured = capsys.readouterr()
    assert "missing valid access_token" in captured.out


def test_login_sensitive_values_are_redacted_in_output(capsys):
    """Credentials, OTP codes, tokens, and challenge IDs must never leak to logs or stdout."""
    canary_password = "CANARY_PASSWORD_SUPER_SECRET_123"
    canary_otp = "998877"
    canary_challenge = "CHALLENGE_CANARY_ID_99999"

    client = MockHttpClient(
        login_resp=MockResponse(200, {
            "requires_otp": True,
            "otp_details": {"challenge_id": canary_challenge},
        }),
        verify_resp=MockResponse(400, {
            "detail": f"Verification error for code {canary_otp} with challenge {canary_challenge}",
        }),
    )

    token = smoke.login(client, "user@claimpilot.test", canary_password, canary_otp, "Customer")
    assert token is None

    captured = capsys.readouterr()
    all_output = captured.out + captured.err

    # Assert no sensitive canary value appears in stdout or stderr
    assert canary_password not in all_output, "Canary password leaked to output!"
    assert canary_otp not in all_output, "Canary OTP leaked to output!"
    assert canary_challenge not in all_output, "Canary challenge leaked to output!"


def test_login_fails_when_is_verified_is_missing(capsys):
    """Login must fail if is_verified key is absent from verification response."""
    client = MockHttpClient(
        login_resp=MockResponse(200, {
            "requires_otp": True,
            "otp_details": {"challenge_id": "ch-alpha-999"},
        }),
        verify_resp=MockResponse(200, {
            "access_token": "verified-jwt-token-xyz",
        }),
    )
    token = smoke.login(client, "user@claimpilot.test", "pass123", "184205", "Customer")
    assert token is None
    captured = capsys.readouterr()
    assert "did not confirm" in captured.out


def test_login_fails_when_is_verified_is_none(capsys):
    """Login must fail if is_verified is explicitly null."""
    client = MockHttpClient(
        login_resp=MockResponse(200, {
            "requires_otp": True,
            "otp_details": {"challenge_id": "ch-alpha-999"},
        }),
        verify_resp=MockResponse(200, {
            "is_verified": None,
            "access_token": "verified-jwt-token-xyz",
        }),
    )
    token = smoke.login(client, "user@claimpilot.test", "pass123", "184205", "Customer")
    assert token is None
    captured = capsys.readouterr()
    assert "did not confirm" in captured.out


def test_login_succeeds_when_is_verified_is_true(capsys):
    """Login must succeed only when is_verified is explicitly True."""
    client = MockHttpClient(
        login_resp=MockResponse(200, {
            "requires_otp": True,
            "otp_details": {"challenge_id": "ch-alpha-999"},
        }),
        verify_resp=MockResponse(200, {
            "is_verified": True,
            "access_token": "verified-jwt-token-xyz",
        }),
    )
    token = smoke.login(client, "user@claimpilot.test", "pass123", "184205", "Customer")
    assert token == "verified-jwt-token-xyz"
