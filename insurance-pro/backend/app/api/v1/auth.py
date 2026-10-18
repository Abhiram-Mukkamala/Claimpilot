from fastapi import APIRouter, HTTPException, status, Depends, BackgroundTasks, Request
from typing import Dict, Any
import logging
from app.db.supabase import db, supabase_public
from app.core.security import get_current_user
from app.core.request_logging import log_route_exception
from app.schemas.claim import UserRegisterRequest, OtpSendRequest, OtpChannel
from app.api.v1.auth_otp import issue_otp

logger = logging.getLogger("claimpilot.auth")
router = APIRouter(prefix="/auth", tags=["Authentication & Profiles"])


@router.post("/login", response_model=Dict[str, Any])
async def login_user(payload: Dict[str, Any], background_tasks: BackgroundTasks, request: Request):
    """
    Step 1 of 2FA Login:
    Validate email + password against Supabase Auth.
    If valid, dispatch an OTP to email and mandate OTP verification before logging in.
    """
    email = (payload.get("email") or "").lower().strip()
    password = payload.get("password") or ""

    if not email or not password:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"message": "Email and password are required"}
        )

    # Validate the password before creating the login OTP challenge.
    try:
        # Never perform end-user password sign-in on the shared service-role client.
        auth_res = supabase_public.auth.sign_in_with_password({
            "email": email,
            "password": password,
        })
        supabase_user = auth_res.user
        if not supabase_user:
            raise Exception("Invalid credentials")
        logger.info("event=auth.login outcome=credentials_verified user_id=%s", supabase_user.id)
        
    except Exception as auth_err:
        logger.warning("event=auth.login outcome=failure")
        request_id = log_route_exception(logger, request, "auth.login.failed", auth_err)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"message": "Invalid email or password", "error": f"Request ID: {request_id}"}
        )

    # The purpose- and user-bound OTP challenge is issued only after password auth.
    otp_response = await issue_otp(
        payload=OtpSendRequest(identifier=email, channel=OtpChannel.email),
        background_tasks=background_tasks,
        purpose="login",
        authenticated_user_id=str(supabase_user.id),
    )

    return {
        "message": "Password accepted. An email verification challenge was recorded; enter the code once it arrives.",
        "requires_otp": True,
        "email": email,
        "otp_details": otp_response
    }


@router.post("/register", response_model=Dict[str, Any], status_code=status.HTTP_202_ACCEPTED)
async def register_user(payload: UserRegisterRequest, background_tasks: BackgroundTasks, request: Request):
    email = payload.email.lower().strip()
    try:
        existing = await db.select("profiles", params={"email": f"eq.{email}"}, single=True)
    except Exception as db_err:
        request_id = log_route_exception(logger, request, "auth.register.profile_lookup_failed", db_err)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"message": "Unable to start registration verification.", "error": f"Request ID: {request_id}"},
        ) from db_err
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"message": "An account with this email address already exists.", "email": email}
        )

    otp_response = await issue_otp(
        payload=OtpSendRequest(identifier=email, channel=OtpChannel.email),
        background_tasks=background_tasks,
        purpose="signup",
    )
    logger.info("event=auth.register outcome=verification_dispatched")
    return {
        "message": "Verification challenge created. Enter the emailed code once it arrives to finish registration.",
        "requires_otp": True,
        "otp_details": otp_response,
    }


@router.get("/me", response_model=Dict[str, Any])
async def get_current_user_profile(user: Dict[str, Any] = Depends(get_current_user)):
    user_id = user["user_id"]
    profile = await db.select("profiles", params={"id": f"eq.{user_id}"}, single=True)
    if not profile:
        return {
            "id": user_id,
            "email": user.get("email"),
            "role": user.get("role", "customer"),
            "full_name": user.get("raw_payload", {}).get("name", "User")
        }
    return profile
