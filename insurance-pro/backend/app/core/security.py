from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, List
from jose import jwt, JWTError
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.core.config import settings

security_bearer = HTTPBearer(auto_error=False)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Generate signed JWT token."""
    to_encode = data.copy()
    to_encode["token_type"] = "access"
    to_encode["purpose"] = "access"
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "iat": datetime.now(timezone.utc)})
    return jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


CLAIM_ACTIONS = {"settlement_confirmation", "evidence_reupload"}
MAX_CLAIM_ACTION_TOKEN_MINUTES = 72 * 60


def create_claim_action_token(claim_id: str, action: str, expires_minutes: int = 30) -> str:
    """Create tamper-proof single-purpose token for magic links in emails."""
    if action not in CLAIM_ACTIONS or not claim_id or not 1 <= expires_minutes <= MAX_CLAIM_ACTION_TOKEN_MINUTES:
        raise ValueError("Invalid claim action token parameters")
    expire = datetime.now(timezone.utc) + timedelta(minutes=expires_minutes)
    payload = {
        "sub": claim_id,
        "claim_id": claim_id,
        "token_type": "claim_action",
        "purpose": action,
        "exp": expire,
        "iat": datetime.now(timezone.utc)
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> Dict[str, Any]:
    """Decode and validate a JWT token signature and expiration."""
    algorithm = settings.JWT_ALGORITHM
    if not algorithm or algorithm.strip().lower() == "none":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        return jwt.decode(token, settings.JWT_SECRET, algorithms=[algorithm])
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


def decode_claim_action_token(token: str, claim_id: str, action: str) -> Dict[str, Any]:
    """Validate a claim-bound action link without treating it as a session."""
    payload = decode_token(token)
    if (
        action not in CLAIM_ACTIONS
        or payload.get("token_type") != "claim_action"
        or payload.get("purpose") != action
        or payload.get("claim_id") != claim_id
        or payload.get("sub") != claim_id
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid claim action token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return payload


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer)
) -> Dict[str, Any]:
    """
    Extract and validate authenticated user from Bearer Token.
    Returns user payload containing user_id, role, and email.
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"message": "Authorization credentials were not provided"},
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token = credentials.credentials
    try:
        payload = decode_token(token)
        if payload.get("token_type") != "access" or payload.get("purpose") != "access":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid access token")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    
    user_id: Optional[str] = payload.get("sub") or payload.get("id") or payload.get("user_id")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"message": "Token payload missing user identifier ('sub')"},
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    app_metadata = payload.get("app_metadata", {})
    user_metadata = payload.get("user_metadata", {})
    raw_role = (
        payload.get("role") 
        or app_metadata.get("role") 
        or user_metadata.get("role") 
        or "customer"
    )
    role = "customer" if raw_role == "authenticated" else raw_role
    email = payload.get("email") or user_metadata.get("email", "")

    return {
        "id": user_id,
        "user_id": user_id,
        "email": email,
        "role": role,
        "raw_payload": payload
    }


def require_roles(allowed_roles: List[str]):
    """Role-Based Access Control (RBAC) dependency factory."""
    async def role_checker(current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
        user_role = current_user.get("role")
        if user_role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "message": f"Operation not permitted. Required roles: {allowed_roles}",
                    "current_role": user_role
                }
            )
        return current_user
    return role_checker
