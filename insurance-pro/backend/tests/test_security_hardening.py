import asyncio
import base64
import json
import os
import secrets
import time

import pytest

for _name in (
    "SUPABASE_URL",
    "SUPABASE_ANON_KEY",
    "SUPABASE_SERVICE_ROLE_KEY",
    "JWT_SECRET",
):
    os.environ[_name] = secrets.token_urlsafe(32)

from fastapi import Depends, FastAPI, HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from fastapi.testclient import TestClient
from jose import jwt

from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_claim_action_token,
    decode_claim_action_token,
    get_current_user,
    require_roles,
)
from app.schemas.claim import ClaimCreate


def _credentials(token: str) -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


def _assert_unauthorized(token: str) -> None:
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(get_current_user(_credentials(token)))
    assert exc_info.value.status_code == 401


def _unsigned_token(payload: dict) -> str:
    def encode_part(value: dict) -> str:
        encoded = base64.urlsafe_b64encode(json.dumps(value).encode()).decode()
        return encoded.rstrip("=")

    return f"{encode_part({'alg': 'none', 'typ': 'JWT'})}.{encode_part(payload)}."


@pytest.fixture(autouse=True)
def use_ephemeral_jwt_settings(monkeypatch):
    monkeypatch.setattr(settings, "JWT_SECRET", secrets.token_urlsafe(32))
    monkeypatch.setattr(settings, "JWT_ALGORITHM", "HS256")


def test_forged_token_signed_with_wrong_secret_is_unauthorized():
    token = jwt.encode(
        {
            "sub": "customer-id",
            "role": "customer",
            "token_type": "access",
            "purpose": "access",
            "exp": int(time.time()) + 300,
        },
        secrets.token_urlsafe(32),
        algorithm="HS256",
    )

    _assert_unauthorized(token)


def test_unsigned_none_algorithm_token_is_unauthorized():
    token = _unsigned_token(
        {
            "sub": "customer-id",
            "role": "customer",
            "token_type": "access",
            "purpose": "access",
            "exp": int(time.time()) + 300,
        }
    )

    _assert_unauthorized(token)


def test_expired_token_is_unauthorized():
    token = jwt.encode(
        {
            "sub": "customer-id",
            "role": "customer",
            "token_type": "access",
            "purpose": "access",
            "exp": int(time.time()) - 1,
        },
        settings.JWT_SECRET,
        algorithm=settings.JWT_ALGORITHM,
    )

    _assert_unauthorized(token)


def test_customer_token_cannot_reach_agent_route():
    app = FastAPI()

    @app.get("/agent-only")
    async def agent_only(_user=Depends(require_roles(["agent", "admin"]))):
        return {"ok": True}

    token = create_access_token({"sub": "customer-id", "role": "customer"})
    response = TestClient(app).get(
        "/agent-only", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 403


def test_claim_action_token_is_claim_and_action_bound_and_not_a_login_token():
    token = create_claim_action_token("claim-123", "evidence_reupload")
    payload = decode_claim_action_token(token, "claim-123", "evidence_reupload")

    assert payload["claim_id"] == "claim-123"
    assert payload["purpose"] == "evidence_reupload"
    assert payload["token_type"] == "claim_action"
    assert payload["exp"] <= int(time.time()) + 31 * 60
    _assert_unauthorized(token)

    with pytest.raises(HTTPException) as exc_info:
        decode_claim_action_token(token, "another-claim", "evidence_reupload")
    assert exc_info.value.status_code == 401

    with pytest.raises(HTTPException) as exc_info:
        decode_claim_action_token(token, "claim-123", "settlement_confirmation")
    assert exc_info.value.status_code == 401


def test_policy_number_rejects_postgrest_filter_syntax():
    assert ClaimCreate.sanitize_policy_number(" pol-123 ") == "POL-123"
    with pytest.raises(ValueError):
        ClaimCreate.sanitize_policy_number("POL-123,or.(id.eq.anything)")
