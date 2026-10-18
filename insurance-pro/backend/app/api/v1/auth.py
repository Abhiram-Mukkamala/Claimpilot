import re
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
    Validate email or 10-digit phone number + password against Supabase Auth / profile.
    If valid, dispatch an OTP and mandate OTP verification before logging in.
    """
    raw_identifier = (payload.get("identifier") or payload.get("email") or payload.get("phone") or "").strip()
    password = payload.get("password") or ""

    if not raw_identifier or not password:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"message": "Invalid email/phone or password"}
        )

    is_email = "@" in raw_identifier
    if is_email:
        email = raw_identifier.lower()
        target_channel = OtpChannel.email
        otp_identifier = email
    else:
        # Validate 10-digit phone number
        digits = re.sub(r"\D", "", raw_identifier)
        if len(digits) < 10:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"message": "Invalid email/phone or password"}
            )
        national_10 = digits[-10:]

        profile = None
        candidates = [
            raw_identifier,
            national_10,
            f"+91{national_10}",
            f"+91 {national_10}",
            f"+91-{national_10}",
        ]
        for candidate in candidates:
            try:
                profile = await db.select("profiles", params={"phone_number": f"eq.{candidate}"}, single=True)
                if profile and isinstance(profile, dict) and profile.get("id"):
                    break
            except Exception:
                pass

        if not profile or not isinstance(profile, dict) or not profile.get("id"):
            try:
                matches = await db.select("profiles", params={"phone_number": f"ilike.%{national_10}%", "limit": "1"})
                if isinstance(matches, list) and len(matches) > 0 and matches[0].get("id"):
                    profile = matches[0]
            except Exception:
                pass

        if not profile or not isinstance(profile, dict) or not profile.get("id"):
            logger.warning("event=auth.login outcome=phone_not_found")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"message": "Invalid email/phone or password"}
            )

        email = (profile.get("email") or "").lower().strip()
        if not email:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"message": "Invalid email/phone or password"}
            )

        phone_target = profile.get("phone_number") or raw_identifier
        sms_allowed = False
        try:
            import app.api.v1.auth_otp as auth_otp_module
            sms_checker = getattr(auth_otp_module, "_otp_delivery_configured", None)
            sms_configured = sms_checker(OtpChannel.sms) if callable(sms_checker) else False
            env = getattr(auth_otp_module, "_environment", "development")
            fixed_code = getattr(auth_otp_module, "_dev_fixed_code", None)
            sms_allowed = sms_configured or (env in {"development", "test"} and fixed_code is not None)
        except Exception:
            sms_allowed = True

        if sms_allowed:
            target_channel = OtpChannel.sms
            otp_identifier = phone_target
        else:
            target_channel = OtpChannel.email
            otp_identifier = email

    # Validate the password before creating the login OTP challenge.
    try:
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
            detail={"message": "Invalid email/phone or password", "error": f"Request ID: {request_id}"}
        )

    # The purpose- and user-bound OTP challenge is issued only after password auth.
    otp_response = await issue_otp(
        payload=OtpSendRequest(identifier=otp_identifier, channel=target_channel),
        background_tasks=background_tasks,
        purpose="login",
        authenticated_user_id=str(supabase_user.id),
    )

    channel_name = "email" if target_channel == OtpChannel.email else "SMS"
    return {
        "message": f"Password accepted. A verification challenge was dispatched via {channel_name}; enter the code once it arrives.",
        "requires_otp": True,
        "email": email,
        "identifier": otp_identifier,
        "channel": target_channel.value,
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
